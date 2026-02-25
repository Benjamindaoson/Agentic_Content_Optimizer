"""
DPO Trainer - Direct Preference Optimization 训练器

核心功能：
1. 基于偏好对进行模型微调
2. 使用 DPO 算法优化模型输出
3. 支持 LoRA 参数高效微调
4. 集成 MLflow 实验追踪

DPO 原理：
- 直接从偏好数据中学习
- 不需要显式的奖励模型
- 更稳定、更高效
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
import numpy as np

from app.data.data_engineering.synthetic_data_generator import PreferencePair
from app.mlops.mlflow_tracker import MLflowTracker

logger = logging.getLogger(__name__)


@dataclass
class DPOConfig:
    """DPO 训练配置"""
    model_name: str = "rednote-hilab/dots.llm1.inst"
    output_dir: str = "./models/dpo_finetuned"

    # LoRA 配置
    use_lora: bool = True
    lora_r: int = 8
    lora_alpha: int = 32
    lora_dropout: float = 0.1

    # 训练配置
    num_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 5e-5
    warmup_steps: int = 100
    max_length: int = 512

    # DPO 特定参数
    beta: float = 0.1  # DPO 温度参数

    # 优化配置
    gradient_accumulation_steps: int = 4
    fp16: bool = True
    logging_steps: int = 10
    save_steps: int = 100


class PreferenceDataset(Dataset):
    """偏好对数据集"""

    def __init__(
        self,
        preference_pairs: List[PreferencePair],
        tokenizer: AutoTokenizer,
        max_length: int = 512
    ):
        self.preference_pairs = preference_pairs
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.preference_pairs)

    def __getitem__(self, idx):
        pair = self.preference_pairs[idx]

        # 构建 prompt
        prompt = f"主题：{pair.topic}\n平台：{pair.platform}\n\n请生成吸引人的内容："

        # Tokenize chosen (更好的内容)
        chosen_text = prompt + pair.chosen_content
        chosen_encodings = self.tokenizer(
            chosen_text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        # Tokenize rejected (较差的内容)
        rejected_text = prompt + pair.rejected_content
        rejected_encodings = self.tokenizer(
            rejected_text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        return {
            "chosen_input_ids": chosen_encodings["input_ids"].squeeze(),
            "chosen_attention_mask": chosen_encodings["attention_mask"].squeeze(),
            "rejected_input_ids": rejected_encodings["input_ids"].squeeze(),
            "rejected_attention_mask": rejected_encodings["attention_mask"].squeeze(),
            "prompt": prompt
        }


class DPOTrainer:
    """
    DPO 训练器

    实现 Direct Preference Optimization 算法
    """

    def __init__(
        self,
        config: Optional[DPOConfig] = None,
        mlflow_tracker: Optional[MLflowTracker] = None
    ):
        """初始化 DPO 训练器

        Args:
            config: DPO 训练配置
            mlflow_tracker: MLflow 追踪器
        """
        self.config = config or DPOConfig()
        self.mlflow_tracker = mlflow_tracker

        self.model = None
        self.ref_model = None  # 参考模型（冻结）
        self.tokenizer = None

        logger.info(f"DPOTrainer initialized with config: {self.config}")

    def load_model(self):
        """加载模型和 tokenizer"""
        logger.info(f"Loading model: {self.config.model_name}")

        # 加载 tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            trust_remote_code=True
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 加载模型
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            torch_dtype=torch.float16 if self.config.fp16 else torch.float32,
            device_map="auto",
            trust_remote_code=True
        )

        # 加载参考模型（用于 DPO 计算）
        self.ref_model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            torch_dtype=torch.float16 if self.config.fp16 else torch.float32,
            device_map="auto",
            trust_remote_code=True
        )

        # 冻结参考模型
        for param in self.ref_model.parameters():
            param.requires_grad = False

        # 应用 LoRA
        if self.config.use_lora:
            logger.info("Applying LoRA configuration")

            lora_config = LoraConfig(
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
                lora_dropout=self.config.lora_dropout,
                bias="none",
                task_type=TaskType.CAUSAL_LM
            )

            self.model = prepare_model_for_kbit_training(self.model)
            self.model = get_peft_model(self.model, lora_config)

            # 打印可训练参数
            self.model.print_trainable_parameters()

        logger.info("Model loaded successfully")

    def compute_dpo_loss(
        self,
        chosen_logps: torch.Tensor,
        rejected_logps: torch.Tensor,
        ref_chosen_logps: torch.Tensor,
        ref_rejected_logps: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """计算 DPO 损失

        DPO 损失公式：
        L = -log(σ(β * (log π_θ(y_w|x) - log π_θ(y_l|x) - log π_ref(y_w|x) + log π_ref(y_l|x))))

        其中：
        - y_w: chosen (更好的输出)
        - y_l: rejected (较差的输出)
        - π_θ: 当前模型
        - π_ref: 参考模型
        - β: 温度参数
        - σ: sigmoid 函数

        Args:
            chosen_logps: 当前模型对 chosen 的 log 概率
            rejected_logps: 当前模型对 rejected 的 log 概率
            ref_chosen_logps: 参考模型对 chosen 的 log 概率
            ref_rejected_logps: 参考模型对 rejected 的 log 概率

        Returns:
            损失值和统计信息
        """
        # 计算 log 概率差异
        pi_logratios = chosen_logps - rejected_logps
        ref_logratios = ref_chosen_logps - ref_rejected_logps

        # DPO 损失
        logits = pi_logratios - ref_logratios
        loss = -F.logsigmoid(self.config.beta * logits).mean()

        # 统计信息
        chosen_rewards = self.config.beta * (chosen_logps - ref_chosen_logps).detach()
        rejected_rewards = self.config.beta * (rejected_logps - ref_rejected_logps).detach()

        stats = {
            "loss": loss.item(),
            "chosen_rewards": chosen_rewards.mean().item(),
            "rejected_rewards": rejected_rewards.mean().item(),
            "reward_margin": (chosen_rewards - rejected_rewards).mean().item(),
            "accuracy": (logits > 0).float().mean().item()
        }

        return loss, stats

    def get_batch_logps(
        self,
        model: AutoModelForCausalLM,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """计算批次的 log 概率

        Args:
            model: 模型
            input_ids: 输入 token IDs
            attention_mask: 注意力掩码

        Returns:
            Log 概率
        """
        with torch.no_grad() if model == self.ref_model else torch.enable_grad():
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                return_dict=True
            )
            logits = outputs.logits

            # 计算 log 概率
            log_probs = F.log_softmax(logits, dim=-1)

            # 获取每个 token 的 log 概率
            token_log_probs = torch.gather(
                log_probs[:, :-1, :],
                2,
                input_ids[:, 1:].unsqueeze(-1)
            ).squeeze(-1)

            # 应用 attention mask
            token_log_probs = token_log_probs * attention_mask[:, 1:]

            # 求和得到序列的 log 概率
            sequence_log_probs = token_log_probs.sum(dim=1)

            return sequence_log_probs

    def train(
        self,
        preference_pairs: List[PreferencePair],
        validation_pairs: Optional[List[PreferencePair]] = None
    ) -> Dict[str, Any]:
        """训练模型

        Args:
            preference_pairs: 训练偏好对
            validation_pairs: 验证偏好对

        Returns:
            训练结果
        """
        logger.info(f"Starting DPO training with {len(preference_pairs)} pairs")

        # 加载模型
        if self.model is None:
            self.load_model()

        # 创建数据集
        train_dataset = PreferenceDataset(
            preference_pairs,
            self.tokenizer,
            self.config.max_length
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True
        )

        # 优化器
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate
        )

        # 训练循环
        self.model.train()
        global_step = 0
        total_loss = 0

        # MLflow 追踪
        if self.mlflow_tracker:
            run_id = self.mlflow_tracker.start_run(
                experiment_name="dpo_training",
                run_name=f"dpo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            self.mlflow_tracker.log_params({
                "model_name": self.config.model_name,
                "num_epochs": self.config.num_epochs,
                "batch_size": self.config.batch_size,
                "learning_rate": self.config.learning_rate,
                "beta": self.config.beta,
                "use_lora": self.config.use_lora,
                "lora_r": self.config.lora_r if self.config.use_lora else None
            })

        for epoch in range(self.config.num_epochs):
            logger.info(f"Epoch {epoch + 1}/{self.config.num_epochs}")

            for batch_idx, batch in enumerate(train_loader):
                # 移动到设备
                chosen_input_ids = batch["chosen_input_ids"].to(self.model.device)
                chosen_attention_mask = batch["chosen_attention_mask"].to(self.model.device)
                rejected_input_ids = batch["rejected_input_ids"].to(self.model.device)
                rejected_attention_mask = batch["rejected_attention_mask"].to(self.model.device)

                # 计算 log 概率
                chosen_logps = self.get_batch_logps(
                    self.model,
                    chosen_input_ids,
                    chosen_attention_mask
                )

                rejected_logps = self.get_batch_logps(
                    self.model,
                    rejected_input_ids,
                    rejected_attention_mask
                )

                ref_chosen_logps = self.get_batch_logps(
                    self.ref_model,
                    chosen_input_ids,
                    chosen_attention_mask
                )

                ref_rejected_logps = self.get_batch_logps(
                    self.ref_model,
                    rejected_input_ids,
                    rejected_attention_mask
                )

                # 计算 DPO 损失
                loss, stats = self.compute_dpo_loss(
                    chosen_logps,
                    rejected_logps,
                    ref_chosen_logps,
                    ref_rejected_logps
                )

                # 反向传播
                loss.backward()

                # 梯度累积
                if (batch_idx + 1) % self.config.gradient_accumulation_steps == 0:
                    optimizer.step()
                    optimizer.zero_grad()
                    global_step += 1

                total_loss += loss.item()

                # 日志记录
                if global_step % self.config.logging_steps == 0:
                    avg_loss = total_loss / self.config.logging_steps
                    logger.info(
                        f"Step {global_step}: "
                        f"loss={avg_loss:.4f}, "
                        f"accuracy={stats['accuracy']:.4f}, "
                        f"reward_margin={stats['reward_margin']:.4f}"
                    )

                    if self.mlflow_tracker:
                        self.mlflow_tracker.log_metrics({
                            "train_loss": avg_loss,
                            "accuracy": stats['accuracy'],
                            "reward_margin": stats['reward_margin'],
                            "chosen_rewards": stats['chosen_rewards'],
                            "rejected_rewards": stats['rejected_rewards']
                        }, step=global_step)

                    total_loss = 0

                # 保存检查点
                if global_step % self.config.save_steps == 0:
                    self.save_model(f"{self.config.output_dir}/checkpoint-{global_step}")

        # 保存最终模型
        final_model_path = f"{self.config.output_dir}/final"
        self.save_model(final_model_path)

        # 结束 MLflow run
        if self.mlflow_tracker:
            self.mlflow_tracker.end_run()

        logger.info("DPO training completed")

        return {
            "model_path": final_model_path,
            "total_steps": global_step,
            "num_epochs": self.config.num_epochs
        }

    def save_model(self, output_dir: str):
        """保存模型

        Args:
            output_dir: 输出目录
        """
        logger.info(f"Saving model to {output_dir}")

        # 保存模型
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        logger.info("Model saved successfully")

    def load_finetuned_model(self, model_path: str):
        """加载微调后的模型

        Args:
            model_path: 模型路径
        """
        logger.info(f"Loading finetuned model from {model_path}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if self.config.fp16 else torch.float32,
            device_map="auto"
        )

        logger.info("Finetuned model loaded successfully")
