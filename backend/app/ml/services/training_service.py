"""
Training Service

统一的训练服务，管理 SFT 和 DPO 训练流程
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from datasets import Dataset
import logging
import time

from ..training.sft import SFTTrainer, SFTConfig
from ..training.dpo import DPOTrainer, DPOConfig
from ..training.dataset_builder import DatasetBuilder
from ..models.adapter_registry import AdapterRegistry
from ..eval.evaluator import Evaluator

logger = logging.getLogger(__name__)


class TrainingService:
    """训练服务"""

    def __init__(self, db: Session):
        self.db = db
        self.dataset_builder = DatasetBuilder(db)
        self.registry = AdapterRegistry(db)
        self.evaluator = Evaluator(self.registry)

    def train_sft(
        self,
        platform: str,
        adapter_name: str,
        base_model: str = "Qwen/Qwen2.5-7B-Instruct",
        persona: Optional[str] = None,
        niche: Optional[str] = None,
        days: int = 30,
        min_engagement_score: float = 0.01,
        max_samples: Optional[int] = None,
        num_train_epochs: int = 3,
        per_device_train_batch_size: int = 4,
        learning_rate: float = 2e-4,
        output_dir: Optional[str] = None,
        eval_split: float = 0.1,
        **kwargs
    ) -> Dict[str, Any]:
        """训练 SFT adapter"""
        logger.info(f"开始 SFT 训练: {adapter_name}")

        start_time = time.time()

        # 1. 构建数据集
        logger.info("构建 SFT 数据集...")
        dataset = self.dataset_builder.build_sft_dataset(
            platform=platform,
            days=days,
            min_engagement_score=min_engagement_score,
            max_samples=max_samples,
        )

        if dataset.total_samples == 0:
            raise ValueError("数据集为空，无法训练")

        logger.info(f"数据集样本数: {dataset.total_samples}")

        # 2. 验证数据集
        validation_result = self.dataset_builder.validate_dataset(dataset)
        logger.info(f"数据集验证: {validation_result}")

        if validation_result["valid_rate"] < 0.8:
            logger.warning(f"数据集质量较低: {validation_result['valid_rate']}")

        # 3. 转换为 Dataset 对象
        from datasets import Dataset as HFDataset
        hf_dataset = HFDataset.from_list(dataset.samples)

        # 4. 划分训练集和验证集
        if eval_split > 0:
            split_dataset = hf_dataset.train_test_split(test_size=eval_split, seed=42)
            train_dataset = split_dataset["train"]
            eval_dataset = split_dataset["test"]
        else:
            train_dataset = hf_dataset
            eval_dataset = None

        # 5. 配置训练
        if output_dir is None:
            output_dir = f"./outputs/sft/{adapter_name}"

        config = SFTConfig(
            base_model=base_model,
            adapter_name=adapter_name,
            output_dir=output_dir,
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            learning_rate=learning_rate,
            platform=platform,
            persona=persona,
            niche=niche,
            **kwargs
        )

        # 6. 训练
        trainer = SFTTrainer(config)
        trainer.train(train_dataset, eval_dataset)

        # 7. 保存 adapter
        trainer.save_adapter()

        training_time = time.time() - start_time

        # 8. 注册 adapter
        adapter_record = self.registry.register(
            adapter_name=adapter_name,
            adapter_type="sft",
            base_model=base_model,
            adapter_path=output_dir,
            platform=platform,
            persona=persona,
            niche=niche,
            training_config=config.model_dump(),
            training_samples=dataset.total_samples,
            training_epochs=num_train_epochs,
            training_time_seconds=training_time,
        )

        # 9. 评估
        if eval_dataset is not None:
            logger.info("评估 adapter...")
            eval_metrics = self.evaluator.evaluate_adapter(
                adapter_name=adapter_name,
                eval_dataset=eval_dataset,
                platform=platform,
                max_samples=100,
            )
        else:
            eval_metrics = {}

        logger.info(f"SFT 训练完成: {adapter_name}")

        return {
            "adapter_name": adapter_name,
            "adapter_id": adapter_record.id,
            "adapter_path": output_dir,
            "training_samples": dataset.total_samples,
            "training_time_seconds": training_time,
            "eval_metrics": eval_metrics,
        }

    def train_dpo(
        self,
        platform: str,
        adapter_name: str,
        base_adapter: str,
        persona: Optional[str] = None,
        niche: Optional[str] = None,
        days: int = 30,
        min_score_diff: float = 0.02,
        max_pairs: Optional[int] = None,
        num_train_epochs: int = 1,
        per_device_train_batch_size: int = 2,
        learning_rate: float = 5e-5,
        beta: float = 0.1,
        output_dir: Optional[str] = None,
        eval_split: float = 0.1,
        **kwargs
    ) -> Dict[str, Any]:
        """训练 DPO adapter"""
        logger.info(f"开始 DPO 训练: {adapter_name}")

        start_time = time.time()

        # 1. 获取 base adapter
        base_adapter_record = self.registry.get(base_adapter)
        if not base_adapter_record:
            raise ValueError(f"Base adapter {base_adapter} 不存在")

        # 2. 构建 DPO 数据集
        logger.info("构建 DPO 数据集...")
        dataset = self.dataset_builder.build_dpo_dataset(
            platform=platform,
            days=days,
            min_score_diff=min_score_diff,
            max_pairs=max_pairs,
        )

        if dataset.total_samples == 0:
            raise ValueError("DPO 数据集为空，无法训练")

        logger.info(f"DPO 偏好对数量: {dataset.total_samples}")

        # 3. 验证数据集
        validation_result = self.dataset_builder.validate_dataset(dataset)
        logger.info(f"数据集验证: {validation_result}")

        # 4. 转换为 Dataset 对象
        from datasets import Dataset as HFDataset
        hf_dataset = HFDataset.from_list(dataset.samples)

        # 5. 划分训练集和验证集
        if eval_split > 0:
            split_dataset = hf_dataset.train_test_split(test_size=eval_split, seed=42)
            train_dataset = split_dataset["train"]
            eval_dataset = split_dataset["test"]
        else:
            train_dataset = hf_dataset
            eval_dataset = None

        # 6. 配置训练
        if output_dir is None:
            output_dir = f"./outputs/dpo/{adapter_name}"

        config = DPOConfig(
            base_model=base_adapter_record.adapter_path,
            adapter_name=adapter_name,
            is_adapter=True,
            output_dir=output_dir,
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            learning_rate=learning_rate,
            beta=beta,
            platform=platform,
            persona=persona,
            niche=niche,
            **kwargs
        )

        # 7. 训练
        trainer = DPOTrainer(config)
        trainer.train(train_dataset, eval_dataset)

        # 8. 保存 adapter
        trainer.save_adapter()

        training_time = time.time() - start_time

        # 9. 注册 adapter
        adapter_record = self.registry.register(
            adapter_name=adapter_name,
            adapter_type="dpo",
            base_model=base_adapter_record.adapter_path,
            adapter_path=output_dir,
            platform=platform,
            persona=persona,
            niche=niche,
            training_config=config.model_dump(),
            training_samples=dataset.total_samples,
            training_epochs=num_train_epochs,
            training_time_seconds=training_time,
        )

        # 10. 评估
        if eval_dataset is not None:
            logger.info("评估 DPO adapter...")
            eval_metrics = self.evaluator.evaluate_adapter(
                adapter_name=adapter_name,
                eval_dataset=eval_dataset,
                platform=platform,
                max_samples=100,
            )
        else:
            eval_metrics = {}

        logger.info(f"DPO 训练完成: {adapter_name}")

        return {
            "adapter_name": adapter_name,
            "adapter_id": adapter_record.id,
            "adapter_path": output_dir,
            "base_adapter": base_adapter,
            "training_pairs": dataset.total_samples,
            "training_time_seconds": training_time,
            "eval_metrics": eval_metrics,
        }

    def auto_train_pipeline(
        self,
        platform: str,
        persona: str,
        niche: str,
        sft_days: int = 30,
        dpo_days: int = 30,
        min_sft_samples: int = 100,
        min_dpo_pairs: int = 50,
    ) -> Dict[str, Any]:
        """自动训练流水线：SFT -> DPO"""
        logger.info(f"开始自动训练流水线: {platform}/{persona}/{niche}")

        results = {}

        # 1. 训练 SFT
        sft_adapter_name = f"{platform}_{persona}_{niche}_sft_v1".replace(" ", "_")

        try:
            sft_result = self.train_sft(
                platform=platform,
                adapter_name=sft_adapter_name,
                persona=persona,
                niche=niche,
                days=sft_days,
                max_samples=None,
            )
            results["sft"] = sft_result

            if sft_result["training_samples"] < min_sft_samples:
                logger.warning(f"SFT 样本数不足: {sft_result['training_samples']} < {min_sft_samples}")
                results["dpo"] = {"error": "SFT 样本数不足，跳过 DPO 训练"}
                return results

        except Exception as e:
            logger.error(f"SFT 训练失败: {e}")
            results["sft"] = {"error": str(e)}
            return results

        # 2. 训练 DPO
        dpo_adapter_name = f"{platform}_{persona}_{niche}_dpo_v1".replace(" ", "_")

        try:
            dpo_result = self.train_dpo(
                platform=platform,
                adapter_name=dpo_adapter_name,
                base_adapter=sft_adapter_name,
                persona=persona,
                niche=niche,
                days=dpo_days,
                max_pairs=None,
            )
            results["dpo"] = dpo_result

            if dpo_result["training_pairs"] < min_dpo_pairs:
                logger.warning(f"DPO 偏好对数不足: {dpo_result['training_pairs']} < {min_dpo_pairs}")

        except Exception as e:
            logger.error(f"DPO 训练失败: {e}")
            results["dpo"] = {"error": str(e)}

        logger.info("自动训练流水线完成")

        return results
