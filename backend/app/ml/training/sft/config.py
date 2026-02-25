"""
SFT Training Configuration
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SFTConfig(BaseModel):
    """SFT 训练配置"""

    # 模型配置
    base_model: str = Field(default="Qwen/Qwen2.5-7B-Instruct", description="基础模型")
    adapter_name: str = Field(..., description="Adapter 名称")

    # LoRA 配置
    lora_r: int = Field(default=64, description="LoRA rank")
    lora_alpha: int = Field(default=128, description="LoRA alpha")
    lora_dropout: float = Field(default=0.05, description="LoRA dropout")
    target_modules: list[str] = Field(
        default=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        description="目标模块"
    )

    # 量化配置
    use_4bit: bool = Field(default=True, description="使用 4-bit 量化")
    bnb_4bit_compute_dtype: str = Field(default="bfloat16", description="计算数据类型")
    bnb_4bit_quant_type: str = Field(default="nf4", description="量化类型")
    use_nested_quant: bool = Field(default=True, description="使用嵌套量化")

    # 训练配置
    output_dir: str = Field(..., description="输出目录")
    num_train_epochs: int = Field(default=3, description="训练轮数")
    per_device_train_batch_size: int = Field(default=4, description="每设备批次大小")
    gradient_accumulation_steps: int = Field(default=4, description="梯度累积步数")
    learning_rate: float = Field(default=2e-4, description="学习率")
    max_grad_norm: float = Field(default=0.3, description="最大梯度范数")
    warmup_ratio: float = Field(default=0.03, description="预热比例")
    lr_scheduler_type: str = Field(default="cosine", description="学习率调度器")

    # 优化器配置
    optim: str = Field(default="paged_adamw_32bit", description="优化器")
    weight_decay: float = Field(default=0.001, description="权重衰减")

    # 保存配置
    save_steps: int = Field(default=500, description="保存步数")
    save_total_limit: int = Field(default=3, description="保存总数限制")
    logging_steps: int = Field(default=10, description="日志步数")

    # 数据配置
    max_seq_length: int = Field(default=2048, description="最大序列长度")
    packing: bool = Field(default=False, description="是否打包")

    # 其他配置
    fp16: bool = Field(default=False, description="使用 FP16")
    bf16: bool = Field(default=True, description="使用 BF16")
    gradient_checkpointing: bool = Field(default=True, description="梯度检查点")

    # 平台特定配置
    platform: Optional[str] = Field(default=None, description="平台")
    persona: Optional[str] = Field(default=None, description="人设")
    niche: Optional[str] = Field(default=None, description="领域")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "base_model": "Qwen/Qwen2.5-7B-Instruct",
                "adapter_name": "xiaohongshu_student_v1",
                "output_dir": "./outputs/sft/xiaohongshu_student_v1",
                "num_train_epochs": 3,
                "per_device_train_batch_size": 4,
                "learning_rate": 2e-4,
                "platform": "xiaohongshu",
                "persona": "学生党",
                "niche": "AI工具"
            }
        }
