"""
DPO Trainer

生产级 DPO 训练器，支持：
- 从 SFT adapter 继续训练
- 偏好对优化
- 多 GPU 训练
- 断点续训
"""

import os
import torch
from typing import Optional, Dict, Any
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
from trl import DPOTrainer as TRLDPOTrainer
import logging

from .config import DPOConfig

logger = logging.getLogger(__name__)


class DPOTrainer:
    """DPO 训练器"""

    def __init__(self, config: DPOConfig):
        self.config = config
        self.model = None
        self.ref_model = None
        self.tokenizer = None
        self.trainer = None

    def load_model(self):
        """加载模型和 tokenizer"""
        logger.info(f"加载模型: {self.config.base_model}")

        # 量化配置
        if self.config.use_4bit:
            compute_dtype = getattr(torch, self.config.bnb_4bit_compute_dtype)
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=self.config.bnb_4bit_quant_type,
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=self.config.use_nested_quant,
            )
        else:
            bnb_config = None

        # 如果 base_model 是 adapter，需要先加载基础模型
        if self.config.is_adapter:
            # 从 adapter 配置中读取基础模型
            import json
            adapter_config_path = os.path.join(self.config.base_model, "training_config.json")
            if os.path.exists(adapter_config_path):
                with open(adapter_config_path, "r") as f:
                    adapter_config = json.load(f)
                    base_model_name = adapter_config.get("base_model")
            else:
                # 尝试从 adapter_config.json 读取
                peft_config_path = os.path.join(self.config.base_model, "adapter_config.json")
                with open(peft_config_path, "r") as f:
                    peft_config = json.load(f)
                    base_model_name = peft_config.get("base_model_name_or_path")

            logger.info(f"从 adapter 加载，基础模型: {base_model_name}")

            # 加载基础模型
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if self.config.bf16 else torch.float16,
            )

            # 加载 SFT adapter
            self.model = PeftModel.from_pretrained(base_model, self.config.base_model)

            # Reference model（用于 DPO）
            ref_base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if self.config.bf16 else torch.float16,
            )
            self.ref_model = PeftModel.from_pretrained(ref_base_model, self.config.base_model)

        else:
            # 直接加载基础模型
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.base_model,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if self.config.bf16 else torch.float16,
            )

            # Reference model
            self.ref_model = AutoModelForCausalLM.from_pretrained(
                self.config.base_model,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if self.config.bf16 else torch.float16,
            )

        # 准备模型用于 k-bit 训练
        if self.config.use_4bit:
            self.model = prepare_model_for_kbit_training(self.model)

        # 加载 tokenizer
        tokenizer_path = self.config.base_model if self.config.is_adapter else self.config.base_model
        self.tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_path,
            trust_remote_code=True,
        )
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"  # DPO 使用 left padding

        logger.info("模型和 tokenizer 加载完成")

    def setup_lora(self):
        """配置 LoRA"""
        logger.info("配置 DPO LoRA adapter")

        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            target_modules=self.config.target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
        )

        # 如果已经是 PEFT 模型，添加新的 adapter
        if hasattr(self.model, "add_adapter"):
            self.model.add_adapter(self.config.adapter_name, lora_config)
            self.model.set_adapter(self.config.adapter_name)
        else:
            self.model = get_peft_model(self.model, lora_config)

        self.model.print_trainable_parameters()

        logger.info("LoRA 配置完成")

    def prepare_dataset(self, dataset: Dataset) -> Dataset:
        """准备 DPO 数据集"""
        logger.info(f"准备 DPO 数据集，样本数: {len(dataset)}")

        # DPO 数据集需要包含: prompt, chosen, rejected
        required_columns = ["prompt", "chosen", "rejected"]
        for col in required_columns:
            if col not in dataset.column_names:
                raise ValueError(f"数据集缺少必需列: {col}")

        logger.info("DPO 数据集准备完成")
        return dataset

    def train(self, train_dataset: Dataset, eval_dataset: Optional[Dataset] = None):
        """开始训练"""
        logger.info("开始 DPO 训练")

        # 加载模型
        if self.model is None:
            self.load_model()
            self.setup_lora()

        # 准备数据集
        train_dataset = self.prepare_dataset(train_dataset)
        if eval_dataset is not None:
            eval_dataset = self.prepare_dataset(eval_dataset)

        # 训练参数
        training_args = TrainingArguments(
            output_dir=self.config.output_dir,
            num_train_epochs=self.config.num_train_epochs,
            per_device_train_batch_size=self.config.per_device_train_batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            max_grad_norm=self.config.max_grad_norm,
            warmup_ratio=self.config.warmup_ratio,
            lr_scheduler_type=self.config.lr_scheduler_type,
            optim=self.config.optim,
            weight_decay=self.config.weight_decay,
            fp16=self.config.fp16,
            bf16=self.config.bf16,
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            save_total_limit=self.config.save_total_limit,
            gradient_checkpointing=self.config.gradient_checkpointing,
            report_to="tensorboard",
            run_name=self.config.adapter_name,
            remove_unused_columns=False,
        )

        # 创建 DPO trainer
        self.trainer = TRLDPOTrainer(
            model=self.model,
            ref_model=self.ref_model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=self.tokenizer,
            beta=self.config.beta,
            loss_type=self.config.loss_type,
            max_length=self.config.max_seq_length,
            max_prompt_length=self.config.max_prompt_length,
        )

        # 开始训练
        logger.info("DPO 训练开始...")
        self.trainer.train()

        logger.info("DPO 训练完成")

    def save_adapter(self, output_dir: Optional[str] = None):
        """保存 adapter"""
        if output_dir is None:
            output_dir = self.config.output_dir

        logger.info(f"保存 DPO adapter 到: {output_dir}")

        # 保存 adapter
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        # 保存配置
        config_path = os.path.join(output_dir, "training_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(self.config.model_dump_json(indent=2))

        logger.info("DPO Adapter 保存完成")

    def resume_from_checkpoint(self, checkpoint_dir: str):
        """从检查点恢复训练"""
        logger.info(f"从检查点恢复: {checkpoint_dir}")

        if self.trainer is None:
            raise ValueError("Trainer 未初始化，请先调用 train()")

        self.trainer.train(resume_from_checkpoint=checkpoint_dir)

        logger.info("恢复训练完成")

    @staticmethod
    def from_pretrained(adapter_path: str, base_model: Optional[str] = None):
        """从已保存的 DPO adapter 加载"""
        # 加载配置
        config_path = os.path.join(adapter_path, "training_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                import json
                config_dict = json.load(f)
                config = DPOConfig(**config_dict)
        else:
            if base_model is None:
                raise ValueError("未找到配置文件，请提供 base_model")
            config = DPOConfig(base_model=base_model, adapter_name="loaded", output_dir=adapter_path)

        # 加载模型
        if config.is_adapter:
            # 从 SFT adapter 加载
            import json
            peft_config_path = os.path.join(config.base_model, "adapter_config.json")
            with open(peft_config_path, "r") as f:
                peft_config = json.load(f)
                base_model_name = peft_config.get("base_model_name_or_path")

            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
            )

            # 加载 SFT adapter
            model = PeftModel.from_pretrained(base_model, config.base_model)

            # 加载 DPO adapter
            model.load_adapter(adapter_path, adapter_name="dpo")
            model.set_adapter("dpo")
        else:
            # 直接从基础模型加载
            base_model = AutoModelForCausalLM.from_pretrained(
                config.base_model,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
            )
            model = PeftModel.from_pretrained(base_model, adapter_path)

        # 加载 tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            adapter_path,
            trust_remote_code=True,
        )

        trainer = DPOTrainer(config)
        trainer.model = model
        trainer.tokenizer = tokenizer

        return trainer
