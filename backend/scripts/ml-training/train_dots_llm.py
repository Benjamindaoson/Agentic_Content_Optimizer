"""
Dots LLM Fine-tuning Script
针对 dots.llm1 (MoE 142B) 的 LoRA/QLoRA 微调

模型架构:
- MoE (Mixture of Experts)
- 总参数: 142B
- 激活参数: 14B
- 上下文: 32K tokens

微调策略:
1. QLoRA (推荐) - 4-bit 量化 + LoRA
2. LoRA - 16-bit + LoRA
3. 全参微调 (不推荐，成本太高)

训练目标:
- Writer Agent: 结构化内容生成 (Hook/Body/CTA)
- Director Agent: 策略规划和决策
"""

import os
import torch
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType
)
from datasets import load_dataset
import bitsandbytes as bnb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DotsFineTuningConfig:
    """Dots LLM 微调配置"""

    # 模型配置
    model_name: str = "rednote-hilab/dots.llm1.inst"
    model_cache_dir: Optional[str] = "./models/cache"

    # 数据配置
    train_data_path: str = "./data/processed/writer-agent-sft.jsonl"
    val_data_path: Optional[str] = None
    max_seq_length: int = 2048

    # LoRA 配置
    use_qlora: bool = True  # 使用 QLoRA (4-bit)
    lora_rank: int = 64  # MoE 模型建议更大的 rank
    lora_alpha: int = 128
    lora_dropout: float = 0.05
    lora_target_modules: list = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",  # Attention
        "gate_proj", "up_proj", "down_proj",      # FFN
        "gate"  # MoE gate (重要!)
    ])

    # 训练配置
    output_dir: str = "./models/dots-llm-writer-agent"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 1  # MoE 显存占用大
    per_device_eval_batch_size: int = 1
    gradient_accumulation_steps: int = 16  # 模拟更大的 batch size
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    # 优化器配置
    optim: str = "paged_adamw_8bit"  # 使用 8-bit Adam 节省显存

    # 保存配置
    save_strategy: str = "steps"
    save_steps: int = 500
    save_total_limit: int = 3
    logging_steps: int = 10

    # 评估配置
    evaluation_strategy: str = "steps"
    eval_steps: int = 500

    # 其他配置
    fp16: bool = False
    bf16: bool = True  # 使用 bf16 (如果 GPU 支持)
    gradient_checkpointing: bool = True  # 节省显存
    ddp_find_unused_parameters: bool = False


class DotsLLMFineTuner:
    """Dots LLM 微调器"""

    def __init__(self, config: DotsFineTuningConfig):
        self.config = config

        # 创建输出目录
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)

        # 保存配置
        self._save_config()

    def _save_config(self):
        """保存配置"""
        config_path = Path(self.config.output_dir) / "training_config.json"

        config_dict = {
            k: v for k, v in self.config.__dict__.items()
            if not k.startswith('_')
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Training config saved to {config_path}")

    def load_model_and_tokenizer(self):
        """
        加载模型和 tokenizer

        针对 MoE 模型的特殊处理:
        1. 使用 QLoRA (4-bit 量化)
        2. 准备模型用于 k-bit 训练
        3. 添加 LoRA 适配器
        """
        logger.info(f"Loading model: {self.config.model_name}")

        # 加载 tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            cache_dir=self.config.model_cache_dir,
            trust_remote_code=True
        )

        # 设置 pad token
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # 加载模型
        if self.config.use_qlora:
            # QLoRA: 4-bit 量化
            from transformers import BitsAndBytesConfig

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16
            )

            model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                cache_dir=self.config.model_cache_dir,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16
            )

            # 准备模型用于 k-bit 训练
            model = prepare_model_for_kbit_training(model)

        else:
            # 标准 LoRA: 16-bit
            model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                cache_dir=self.config.model_cache_dir,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16
            )

        # 配置 LoRA
        lora_config = LoraConfig(
            r=self.config.lora_rank,
            lora_alpha=self.config.lora_alpha,
            target_modules=self.config.lora_target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM
        )

        # 添加 LoRA 适配器
        model = get_peft_model(model, lora_config)

        # 打印可训练参数
        model.print_trainable_parameters()

        logger.info("Model and tokenizer loaded successfully")

        return model, tokenizer

    def load_dataset(self, tokenizer):
        """
        加载数据集

        数据格式 (JSONL):
        {
          "instruction": "生成一个健身内容的 Hook",
          "input": "目标受众: 健身新手, 平台: 小红书",
          "output": "🔥 30天从0到马甲线！新手必看..."
        }
        """
        logger.info(f"Loading dataset from {self.config.train_data_path}")

        # 加载训练数据
        train_dataset = load_dataset(
            'json',
            data_files=self.config.train_data_path,
            split='train'
        )

        # 加载验证数据 (如果有)
        val_dataset = None
        if self.config.val_data_path:
            val_dataset = load_dataset(
                'json',
                data_files=self.config.val_data_path,
                split='train'
            )

        # 预处理数据
        def preprocess_function(examples):
            """预处理函数"""
            prompts = []

            for instruction, input_text, output in zip(
                examples['instruction'],
                examples.get('input', [''] * len(examples['instruction'])),
                examples['output']
            ):
                # 构建提示词 (Alpaca 格式)
                if input_text:
                    prompt = f"""Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Input:
{input_text}

### Response:
{output}"""
                else:
                    prompt = f"""Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Response:
{output}"""

                prompts.append(prompt)

            # Tokenize
            tokenized = tokenizer(
                prompts,
                truncation=True,
                max_length=self.config.max_seq_length,
                padding="max_length",
                return_tensors="pt"
            )

            # 设置 labels (用于计算 loss)
            tokenized["labels"] = tokenized["input_ids"].clone()

            return tokenized

        # 应用预处理
        train_dataset = train_dataset.map(
            preprocess_function,
            batched=True,
            remove_columns=train_dataset.column_names
        )

        if val_dataset:
            val_dataset = val_dataset.map(
                preprocess_function,
                batched=True,
                remove_columns=val_dataset.column_names
            )

        logger.info(f"Dataset loaded: {len(train_dataset)} training samples")

        return train_dataset, val_dataset

    def train(self):
        """开始训练"""
        # 1. 加载模型和 tokenizer
        model, tokenizer = self.load_model_and_tokenizer()

        # 2. 加载数据集
        train_dataset, val_dataset = self.load_dataset(tokenizer)

        # 3. 配置训练参数
        training_args = TrainingArguments(
            output_dir=self.config.output_dir,
            num_train_epochs=self.config.num_train_epochs,
            per_device_train_batch_size=self.config.per_device_train_batch_size,
            per_device_eval_batch_size=self.config.per_device_eval_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            warmup_ratio=self.config.warmup_ratio,
            lr_scheduler_type=self.config.lr_scheduler_type,
            weight_decay=self.config.weight_decay,
            max_grad_norm=self.config.max_grad_norm,
            optim=self.config.optim,
            save_strategy=self.config.save_strategy,
            save_steps=self.config.save_steps,
            save_total_limit=self.config.save_total_limit,
            logging_steps=self.config.logging_steps,
            evaluation_strategy=self.config.evaluation_strategy,
            eval_steps=self.config.eval_steps if val_dataset else None,
            fp16=self.config.fp16,
            bf16=self.config.bf16,
            gradient_checkpointing=self.config.gradient_checkpointing,
            ddp_find_unused_parameters=self.config.ddp_find_unused_parameters,
            report_to=["tensorboard"],
            load_best_model_at_end=True if val_dataset else False,
            metric_for_best_model="eval_loss" if val_dataset else None
        )

        # 4. 创建 Trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            tokenizer=tokenizer,
            data_collator=DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=False
            )
        )

        # 5. 开始训练
        logger.info("Starting training...")
        trainer.train()

        # 6. 保存最终模型
        logger.info("Saving final model...")
        trainer.save_model(self.config.output_dir)
        tokenizer.save_pretrained(self.config.output_dir)

        logger.info(f"Training completed! Model saved to {self.config.output_dir}")

    def merge_and_save(self, output_path: str):
        """
        合并 LoRA 权重到基础模型并保存

        Args:
            output_path: 输出路径
        """
        logger.info("Merging LoRA weights...")

        # 加载微调后的模型
        from peft import PeftModel

        base_model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True
        )

        model = PeftModel.from_pretrained(
            base_model,
            self.config.output_dir
        )

        # 合并权重
        model = model.merge_and_unload()

        # 保存
        model.save_pretrained(output_path)

        # 保存 tokenizer
        tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        tokenizer.save_pretrained(output_path)

        logger.info(f"Merged model saved to {output_path}")


def main():
    """主函数"""
    # 配置
    config = DotsFineTuningConfig(
        model_name="rednote-hilab/dots.llm1.inst",
        train_data_path="./data/processed/writer-agent-sft.jsonl",
        output_dir="./models/dots-llm-writer-agent",
        num_train_epochs=3,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        use_qlora=True,
        lora_rank=64,
        lora_alpha=128
    )

    # 创建微调器
    finetuner = DotsLLMFineTuner(config)

    # 开始训练
    finetuner.train()

    # (可选) 合并权重
    # finetuner.merge_and_save("./models/dots-llm-writer-agent-merged")


if __name__ == "__main__":
    main()
