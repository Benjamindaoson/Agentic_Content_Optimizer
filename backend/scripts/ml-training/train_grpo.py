"""
GRPO 训练脚本
使用 TRL 框架训练 Group Relative Policy Optimization
数据: TikTok-10M (预处理后)
"""

import os
import torch
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import polars as pl
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
)
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig, get_peft_model, TaskType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GRPOTrainingConfig:
    """GRPO 训练配置"""

    # 模型配置
    model_name: str = "Qwen/Qwen2.5-7B"
    sft_model_path: Optional[str] = "./models/qwen2.5-7b-sft/checkpoints/checkpoint-best"

    # 数据配置
    data_path: str = "./data/processed/tiktok-10m-processed.parquet"
    max_samples: int = 100000

    # GRPO 配置
    group_size: int = 8
    learning_rate: float = 1e-5
    batch_size: int = 8
    mini_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    num_epochs: int = 3
    temperature: float = 1.0
    clip_epsilon: float = 0.2

    # LoRA 配置
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05

    # 输出配置
    output_dir: str = "./models/qwen2.5-7b-grpo"
    logging_steps: int = 10
    save_steps: int = 500


class RewardModel:
    """
    改进的奖励模型 - 多维度互动信号 + Percentile Normalization
    基于 TikTok-10M 数据计算奖励
    """

    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.df = pl.read_parquet(self.data_path)

        # 预计算全局 percentile 用于归一化
        self._compute_global_percentiles()

        logger.info(f"Loaded {len(self.df)} records for reward calculation")

    def _compute_global_percentiles(self):
        """预计算全局 percentile 分布"""
        self.percentiles = {}

        # 为每个指标计算 percentile
        metrics = ["digg_count", "comment_count", "share_count", "play_count"]
        for metric in metrics:
            if metric in self.df.columns:
                self.percentiles[metric] = {
                    "p25": self.df[metric].quantile(0.25),
                    "p50": self.df[metric].quantile(0.50),
                    "p75": self.df[metric].quantile(0.75),
                    "p90": self.df[metric].quantile(0.90),
                    "p95": self.df[metric].quantile(0.95),
                }

    def _percentile_normalize(self, value: float, metric: str) -> float:
        """
        Percentile normalization - 比 z-score 更鲁棒
        返回 0-1 之间的归一化值
        """
        if metric not in self.percentiles:
            return 0.0

        p = self.percentiles[metric]

        # 使用 percentile 进行归一化
        if value <= p["p25"]:
            return 0.0
        elif value >= p["p95"]:
            return 1.0
        else:
            # 线性插值
            return (value - p["p25"]) / (p["p95"] - p["p25"])

    def calculate_reward(
        self,
        author_id: str,
        likes: int,
        comments: int,
        shares: int,
        play_count: int,
        collect_count: int = 0,
    ) -> float:
        """
        改进的奖励计算 - 多维度互动信号

        R = w1 * 完播率 + w2 * 评论率 + w3 * 收藏率 + w4 * 转发率

        使用 percentile normalization 而不是 baseline
        """

        # 1. 计算各维度的归一化分数
        like_score = self._percentile_normalize(likes, "digg_count")
        comment_score = self._percentile_normalize(comments, "comment_count")
        share_score = self._percentile_normalize(shares, "share_count")

        # 完播率估计（play_count 作为曝光代理）
        # 实际应该用 play_duration / video_duration
        engagement_rate = (likes + comments + shares) / max(play_count, 1)
        engagement_score = self._percentile_normalize(engagement_rate * 1000, "digg_count")

        # 2. 加权组合（根据业务重要性调整）
        reward = (
            0.3 * engagement_score +  # 完播/互动率最重要
            0.25 * like_score +        # 点赞
            0.25 * comment_score +     # 评论（深度互动）
            0.20 * share_score         # 转发（病毒传播）
        )

        return reward

    def calculate_reward_legacy(
        self,
        author_id: str,
        likes: int,
        play_count: int,
        geo_score: float = 0.0
    ) -> float:
        """
        旧版奖励计算（保留用于对比）
        R = 0.7 * R_adj + 0.3 * GEO_score
        """

        # 1. 获取作者的 baseline
        author_posts = self.df.filter(pl.col("author_id") == author_id)

        if len(author_posts) < 10:
            baseline = self.df["digg_count"].median()
        else:
            baseline = author_posts.sort("publish_time", descending=True).head(10)["digg_count"].median()

        # 2. 计算相对增益
        if baseline == 0:
            baseline = 1

        r_gain = (likes - baseline) / baseline

        # 3. 调整奖励（考虑曝光）
        r_adj = r_gain * torch.log(torch.tensor(1.0 + play_count)).item()

        # 4. 综合奖励
        reward = 0.7 * r_adj + 0.3 * geo_score

        return reward

    def calculate_batch_rewards(
        self,
        batch_data: List[Dict]
    ) -> List[float]:
        """批量计算奖励 - 使用改进的多维度方法"""
        rewards = []
        for item in batch_data:
            reward = self.calculate_reward(
                author_id=item["author_id"],
                likes=item.get("likes", item.get("digg_count", 0)),
                comments=item.get("comments", item.get("comment_count", 0)),
                shares=item.get("shares", item.get("share_count", 0)),
                play_count=item.get("play_count", 0),
                collect_count=item.get("collect_count", 0)
            )
            rewards.append(reward)

        return rewards


class GRPODataset:
    """GRPO 训练数据集"""

    def __init__(
        self,
        data_path: str,
        tokenizer,
        max_samples: int = 100000,
        group_size: int = 8
    ):
        self.data_path = Path(data_path)
        self.tokenizer = tokenizer
        self.max_samples = max_samples
        self.group_size = group_size

        # 加载数据
        self.df = pl.read_parquet(self.data_path)

        if len(self.df) > max_samples:
            self.df = self.df.sample(n=max_samples, seed=42)

        logger.info(f"Loaded {len(self.df)} samples for GRPO training")

    def __len__(self):
        return len(self.df) // self.group_size

    def __getitem__(self, idx):
        """
        返回一个 group 的数据
        每个 group 包含 8 个样本
        """
        start_idx = idx * self.group_size
        end_idx = start_idx + self.group_size

        group_data = self.df[start_idx:end_idx]

        # 构建输入
        prompts = []
        for row in group_data.iter_rows(named=True):
            # 构建 prompt
            prompt = self._build_prompt(row)
            prompts.append(prompt)

        # Tokenize
        inputs = self.tokenizer(
            prompts,
            padding=True,
            truncation=True,
            max_length=2048,
            return_tensors="pt"
        )

        # 奖励（已预计算）
        rewards = group_data["adjusted_reward"].to_list()

        return {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
            "rewards": torch.tensor(rewards, dtype=torch.float32)
        }

    def _build_prompt(self, row: Dict) -> str:
        """构建 prompt"""
        # 提取 hashtags
        hashtags = row.get("hashtags", "")
        if isinstance(hashtags, list):
            hashtags = ", ".join(hashtags)

        prompt = f"""请根据以下信息生成一条短视频文案：

话题标签: {hashtags}
目标: 获得高互动率

请生成结构化文案（Hook + Body + CTA）：
"""
        return prompt


class GRPOTrainerWrapper:
    """GRPO 训练器封装"""

    def __init__(self, config: GRPOTrainingConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.tokenizer = None
        self.model = None
        self.reward_model = None
        self.dataset = None

    def setup(self):
        """初始化模型和数据"""
        logger.info("Setting up GRPO training...")

        # 1. 加载 tokenizer
        logger.info(f"Loading tokenizer from {self.config.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            trust_remote_code=True
        )
        self.tokenizer.pad_token = self.tokenizer.eos_token

        # 2. 加载模型
        if self.config.sft_model_path and Path(self.config.sft_model_path).exists():
            logger.info(f"Loading SFT model from {self.config.sft_model_path}")
            model_path = self.config.sft_model_path
        else:
            logger.info(f"Loading base model from {self.config.model_name}")
            model_path = self.config.model_name

        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )

        # 3. 添加 LoRA
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=self.config.lora_rank,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

        # 4. 初始化 Reward Model
        logger.info("Initializing Reward Model...")
        self.reward_model = RewardModel(data_path=self.config.data_path)

        # 5. 加载数据集
        logger.info("Loading dataset...")
        self.dataset = GRPODataset(
            data_path=self.config.data_path,
            tokenizer=self.tokenizer,
            max_samples=self.config.max_samples,
            group_size=self.config.group_size
        )

        logger.info("Setup completed!")

    def train(self):
        """开始训练"""
        logger.info("=" * 60)
        logger.info("Starting GRPO Training")
        logger.info("=" * 60)

        # GRPO 配置
        grpo_config = GRPOConfig(
            learning_rate=self.config.learning_rate,
            batch_size=self.config.batch_size,
            mini_batch_size=self.config.mini_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            num_train_epochs=self.config.num_epochs,
            temperature=self.config.temperature,
            clip_epsilon=self.config.clip_epsilon,
            group_size=self.config.group_size,
            normalize_rewards=True,  # GRPO 特有：相对奖励归一化
            output_dir=str(self.output_dir),
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            save_total_limit=3,
            bf16=True,
            report_to=["tensorboard", "wandb"],
            run_name="qwen2.5-7b-grpo-tiktok",
        )

        # 创建 Trainer
        trainer = GRPOTrainer(
            model=self.model,
            config=grpo_config,
            train_dataset=self.dataset,
            tokenizer=self.tokenizer,
        )

        # 开始训练
        logger.info("Training started...")
        trainer.train()

        # 保存模型
        logger.info("Saving model...")
        trainer.save_model(str(self.output_dir / "final"))

        logger.info("=" * 60)
        logger.info("Training completed!")
        logger.info("=" * 60)


def main():
    """主函数"""
    # 配置
    config = GRPOTrainingConfig(
        model_name="Qwen/Qwen2.5-7B",
        sft_model_path="./models/qwen2.5-7b-sft/checkpoints/checkpoint-best",
        data_path="./data/processed/tiktok-10m-processed.parquet",
        max_samples=100000,
        group_size=8,
        learning_rate=1e-5,
        batch_size=8,
        num_epochs=3,
        output_dir="./models/qwen2.5-7b-grpo"
    )

    # 创建训练器
    trainer = GRPOTrainerWrapper(config)

    # 初始化
    trainer.setup()

    # 训练
    trainer.train()


if __name__ == "__main__":
    main()
