"""
QLoRA SFT Trainer

生产级 SFT 训练器，支持：
- Qwen/Llama 模型
- 4-bit 量化
- LoRA adapter
- 多 GPU 训练
- 断点续训
"""

import os
import torch
from typing import Optional, Dict, Any, List
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer as TRLSFTTrainer
import logging

from .config import SFTConfig

logger = logging.getLogger(__name__)


class SFTTrainer:
    """SFT 训练器"""

    def __init__(self, config: SFTConfig):
        self.config = config
        self.model = None
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

        # 加载模型
        self.model = AutoModelForCausalLM.from_pretrained(
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
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.base_model,
            trust_remote_code=True,
        )
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "right"

        logger.info("模型和 tokenizer 加载完成")

    def setup_lora(self):
        """配置 LoRA"""
        logger.info("配置 LoRA adapter")

        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            target_modules=self.config.target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
        )

        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

        logger.info("LoRA 配置完成")

    def prepare_dataset(self, dataset: Dataset) -> Dataset:
        """准备数据集"""
        logger.info(f"准备数据集，样本数: {len(dataset)}")

        def formatting_func(example):
            """格式化样本"""
            messages = example.get("messages", [])

            # 构建对话文本
            text = ""
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")

                if role == "system":
                    text += f"<|im_start|>system\n{content}<|im_end|>\n"
                elif role == "user":
                    text += f"<|im_start|>user\n{content}<|im_end|>\n"
                elif role == "assistant":
                    text += f"<|im_start|>assistant\n{content}<|im_end|>\n"

            return {"text": text}

        # 格式化数据集
        formatted_dataset = dataset.map(
            formatting_func,
            remove_columns=dataset.column_names,
            desc="格式化数据集"
        )

        logger.info("数据集准备完成")
        return formatted_dataset

    def train(self, train_dataset: Dataset, eval_dataset: Optional[Dataset] = None):
        """开始训练"""
        logger.info("开始训练")

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
        )

        # 创建 trainer
        self.trainer = TRLSFTTrainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=self.tokenizer,
            max_seq_length=self.config.max_seq_length,
            packing=self.config.packing,
            dataset_text_field="text",
        )

        # 开始训练
        logger.info("训练开始...")
        self.trainer.train()

        logger.info("训练完成")

    def save_adapter(self, output_dir: Optional[str] = None):
        """保存 adapter"""
        if output_dir is None:
            output_dir = self.config.output_dir

        logger.info(f"保存 adapter 到: {output_dir}")

        # 保存 adapter
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        # 保存配置
        config_path = os.path.join(output_dir, "training_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(self.config.model_dump_json(indent=2))

        logger.info("Adapter 保存完成")

    def resume_from_checkpoint(self, checkpoint_dir: str):
        """从检查点恢复训练"""
        logger.info(f"从检查点恢复: {checkpoint_dir}")

        if self.trainer is None:
            raise ValueError("Trainer 未初始化，请先调用 train()")

        self.trainer.train(resume_from_checkpoint=checkpoint_dir)

        logger.info("恢复训练完成")

    @staticmethod
    def from_pretrained(adapter_path: str, base_model: Optional[str] = None):
        """从已保存的 adapter 加载"""
        from peft import PeftModel

        # 加载配置
        config_path = os.path.join(adapter_path, "training_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                import json
                config_dict = json.load(f)
                config = SFTConfig(**config_dict)
        else:
            if base_model is None:
                raise ValueError("未找到配置文件，请提供 base_model")
            config = SFTConfig(base_model=base_model, adapter_name="loaded", output_dir=adapter_path)

        # 加载基础模型
        model = AutoModelForCausalLM.from_pretrained(
            config.base_model,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        # 加载 adapter
        model = PeftModel.from_pretrained(model, adapter_path)

        # 加载 tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            adapter_path,
            trust_remote_code=True,
        )

        trainer = SFTTrainer(config)
        trainer.model = model
        trainer.tokenizer = tokenizer

        return trainer

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.7) -> str:
        """生成文本"""
        if self.model is None or self.tokenizer is None:
            raise ValueError("模型未加载")

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                top_k=50,
            )

        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # 移除输入部分
        generated_text = generated_text[len(prompt):]

        return generated_text.strip()
