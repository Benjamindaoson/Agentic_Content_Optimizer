"""
Dataset Builder

从 generation traces 和 outcomes 自动构建训练数据集
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import json
import logging

from app.ml.training.schemas import (
    GenerationTrace,
    Outcome,
    SFTDataSample,
    DPODataSample,
    TrainingDataset
)

logger = logging.getLogger(__name__)


class DatasetBuilder:
    """训练数据集构建器"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_engagement_score(self, outcome: Outcome) -> float:
        """计算综合互动分

        小红书优先公式：
        score = 0.45*saves_rate + 0.25*read_time_norm + 0.20*comment_rate + 0.10*click_rate
        """
        if outcome.impressions == 0:
            return 0.0

        saves_rate = outcome.saves / outcome.impressions
        comment_rate = outcome.comments / outcome.impressions
        click_rate = outcome.clicks / outcome.impressions if outcome.impressions > 0 else 0.0

        # 归一化停留时间（假设 60 秒为满分）
        read_time_norm = min(outcome.read_time_avg / 60.0, 1.0)

        score = (
            0.45 * saves_rate +
            0.25 * read_time_norm +
            0.20 * comment_rate +
            0.10 * click_rate
        )

        return score

    def build_sft_dataset(
        self,
        platform: str,
        days: int = 30,
        min_engagement_score: float = 0.01,
        max_samples: Optional[int] = None
    ) -> TrainingDataset:
        """构建 SFT 训练数据集

        Args:
            platform: 平台（xhs, douyin）
            days: 最近 N 天的数据
            min_engagement_score: 最小互动分（过滤低质量内容）
            max_samples: 最大样本数

        Returns:
            TrainingDataset
        """
        logger.info(f"Building SFT dataset for platform={platform}, days={days}")

        start_date = datetime.utcnow() - timedelta(days=days)

        # 查询有效果数据的 traces
        query = self.db.query(GenerationTrace).join(Outcome).filter(
            and_(
                GenerationTrace.platform == platform,
                GenerationTrace.created_at >= start_date,
                Outcome.engagement_score >= min_engagement_score
            )
        )

        if max_samples:
            query = query.limit(max_samples)

        traces = query.all()

        samples = []
        for trace in traces:
            # 构建 messages 格式
            system_content = trace.system_prompt or f"你是{platform}平台的专业内容创作者"

            user_content = self._build_user_prompt(trace)

            assistant_content = trace.output

            sample = SFTDataSample(
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": assistant_content}
                ],
                metadata={
                    "trace_id": trace.id,
                    "platform": trace.platform,
                    "persona": trace.persona,
                    "niche": trace.niche,
                    "engagement_score": trace.outcomes[0].engagement_score if trace.outcomes else 0.0
                }
            )

            samples.append(sample.dict())

        logger.info(f"Built {len(samples)} SFT samples")

        return TrainingDataset(
            dataset_type="sft",
            platform=platform,
            samples=samples,
            total_samples=len(samples),
            metadata={
                "days": days,
                "min_engagement_score": min_engagement_score
            }
        )

    def build_dpo_dataset(
        self,
        platform: str,
        days: int = 30,
        min_score_diff: float = 0.02,
        max_pairs: Optional[int] = None
    ) -> TrainingDataset:
        """构建 DPO 训练数据集

        从同一 topic/persona 下的多个版本中，选择高分和低分内容构建偏好对

        Args:
            platform: 平台
            days: 最近 N 天的数据
            min_score_diff: 最小分数差异
            max_pairs: 最大偏好对数量

        Returns:
            TrainingDataset
        """
        logger.info(f"Building DPO dataset for platform={platform}, days={days}")

        start_date = datetime.utcnow() - timedelta(days=days)

        # 查询所有有效果的 traces，按 topic+persona 分组
        traces = self.db.query(GenerationTrace).join(Outcome).filter(
            and_(
                GenerationTrace.platform == platform,
                GenerationTrace.created_at >= start_date
            )
        ).all()

        # 按 (topic, persona) 分组
        groups: Dict[tuple, List[GenerationTrace]] = {}
        for trace in traces:
            key = (trace.topic, trace.persona or "default")
            if key not in groups:
                groups[key] = []
            groups[key].append(trace)

        # 构建偏好对
        pairs = []
        for (topic, persona), group_traces in groups.items():
            if len(group_traces) < 2:
                continue

            # 计算每个 trace 的 engagement_score
            scored_traces = []
            for trace in group_traces:
                if not trace.outcomes:
                    continue

                score = self.calculate_engagement_score(trace.outcomes[0])
                scored_traces.append((trace, score))

            # 排序
            scored_traces.sort(key=lambda x: x[1], reverse=True)

            # 构建偏好对：高分 vs 低分
            for i in range(len(scored_traces)):
                for j in range(i + 1, len(scored_traces)):
                    chosen_trace, chosen_score = scored_traces[i]
                    rejected_trace, rejected_score = scored_traces[j]

                    score_diff = chosen_score - rejected_score

                    if score_diff < min_score_diff:
                        continue

                    prompt = self._build_user_prompt(chosen_trace)

                    pair = DPODataSample(
                        prompt=prompt,
                        chosen=chosen_trace.output,
                        rejected=rejected_trace.output,
                        score_diff=score_diff,
                        metadata={
                            "chosen_trace_id": chosen_trace.id,
                            "rejected_trace_id": rejected_trace.id,
                            "chosen_score": chosen_score,
                            "rejected_score": rejected_score,
                            "topic": topic,
                            "persona": persona
                        }
                    )

                    pairs.append(pair.dict())

                    if max_pairs and len(pairs) >= max_pairs:
                        break

                if max_pairs and len(pairs) >= max_pairs:
                    break

            if max_pairs and len(pairs) >= max_pairs:
                break

        logger.info(f"Built {len(pairs)} DPO pairs")

        return TrainingDataset(
            dataset_type="dpo",
            platform=platform,
            samples=pairs,
            total_samples=len(pairs),
            metadata={
                "days": days,
                "min_score_diff": min_score_diff
            }
        )

    def _build_user_prompt(self, trace: GenerationTrace) -> str:
        """构建用户 prompt"""
        parts = []

        parts.append(f"平台: {trace.platform}")

        if trace.persona:
            parts.append(f"人设: {trace.persona}")

        if trace.niche:
            parts.append(f"领域: {trace.niche}")

        parts.append(f"主题: {trace.topic}")

        if trace.constraints:
            parts.append(f"约束: {json.dumps(trace.constraints, ensure_ascii=False)}")

        if trace.retrieved_context:
            context_str = "\n".join([
                f"- {ctx.get('content', '')[:100]}..."
                for ctx in trace.retrieved_context[:3]
            ])
            parts.append(f"参考素材:\n{context_str}")

        return "\n".join(parts)

    def export_to_jsonl(self, dataset: TrainingDataset, output_path: str):
        """导出数据集为 JSONL 格式"""
        with open(output_path, "w", encoding="utf-8") as f:
            for sample in dataset.samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        logger.info(f"Exported {dataset.total_samples} samples to {output_path}")

    def validate_dataset(self, dataset: TrainingDataset) -> Dict[str, Any]:
        """验证数据集质量"""
        validation_result = {
            "total_samples": dataset.total_samples,
            "valid_samples": 0,
            "invalid_samples": 0,
            "issues": []
        }

        for idx, sample in enumerate(dataset.samples):
            try:
                if dataset.dataset_type == "sft":
                    # 验证 SFT 样本
                    if "messages" not in sample:
                        validation_result["issues"].append(f"Sample {idx}: missing 'messages'")
                        validation_result["invalid_samples"] += 1
                        continue

                    messages = sample["messages"]
                    if len(messages) < 2:
                        validation_result["issues"].append(f"Sample {idx}: too few messages")
                        validation_result["invalid_samples"] += 1
                        continue

                    # 检查内容长度
                    assistant_msg = [m for m in messages if m["role"] == "assistant"]
                    if assistant_msg and len(assistant_msg[0]["content"]) < 10:
                        validation_result["issues"].append(f"Sample {idx}: output too short")
                        validation_result["invalid_samples"] += 1
                        continue

                elif dataset.dataset_type == "dpo":
                    # 验证 DPO 样本
                    required_fields = ["prompt", "chosen", "rejected"]
                    missing_fields = [f for f in required_fields if f not in sample]

                    if missing_fields:
                        validation_result["issues"].append(
                            f"Sample {idx}: missing fields {missing_fields}"
                        )
                        validation_result["invalid_samples"] += 1
                        continue

                    # 检查 chosen 和 rejected 不同
                    if sample["chosen"] == sample["rejected"]:
                        validation_result["issues"].append(f"Sample {idx}: chosen == rejected")
                        validation_result["invalid_samples"] += 1
                        continue

                validation_result["valid_samples"] += 1

            except Exception as e:
                validation_result["issues"].append(f"Sample {idx}: {str(e)}")
                validation_result["invalid_samples"] += 1

        validation_result["valid_rate"] = (
            validation_result["valid_samples"] / validation_result["total_samples"]
            if validation_result["total_samples"] > 0 else 0.0
        )

        return validation_result
