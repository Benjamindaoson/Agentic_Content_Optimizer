"""
每日数据流水线 - 自动从线上日志构建偏好对

功能：
1. 每日定时运行（凌晨 2:00）
2. 从 user_feedback_log 提取数据
3. 构建偏好对
4. 保存为训练数据集
5. 混合 HelpSteer3 数据
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data.data_engineering.synthetic_data_generator import PreferencePair
from app.data.data_engineering.feedback_collector import UserFeedbackLog

logger = logging.getLogger(__name__)


class DailyDataPipeline:
    """每日数据流水线"""

    def __init__(
        self,
        db: Session,
        output_dir: str = "./data/daily_preference_pairs",
        helpsteer3_dir: str = "./data/helpsteer3",
        mix_ratio: float = 0.2  # 20% 线上数据 + 80% HelpSteer3
    ):
        """初始化流水线

        Args:
            db: 数据库会话
            output_dir: 输出目录
            helpsteer3_dir: HelpSteer3 数据集目录
            mix_ratio: 线上数据混合比例
        """
        self.db = db
        self.output_dir = output_dir
        self.helpsteer3_dir = helpsteer3_dir
        self.mix_ratio = mix_ratio

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

    def fetch_raw_feedback(self, days: int = 1) -> pd.DataFrame:
        """从日志表获取最近 N 天的原始反馈数据

        Args:
            days: 天数

        Returns:
            DataFrame
        """
        logger.info(f"Fetching feedback from last {days} days...")

        query = text("""
            SELECT
                prompt,
                generated_content,
                model_version,
                pattern_id,
                event_type,
                event_timestamp,
                user_id,
                feedback_value
            FROM user_feedback_log
            WHERE event_timestamp >= :start_time
                AND prompt IS NOT NULL
                AND generated_content IS NOT NULL
            ORDER BY event_timestamp DESC
        """)

        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        try:
            df = pd.read_sql(query, self.db.bind, params={"start_time": start_time})
            logger.info(f"Fetched {len(df)} feedback records")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch feedback: {e}")
            return pd.DataFrame()

    def map_event_to_score(self, event_type: str, feedback_value: Optional[float] = None) -> Optional[float]:
        """将事件类型映射为奖励分数

        Args:
            event_type: 事件类型
            feedback_value: 反馈值（如果有）

        Returns:
            奖励分数
        """
        # 如果有显式的反馈值，直接使用
        if feedback_value is not None:
            return feedback_value

        # 否则根据事件类型映射
        mapping = {
            "like": 1.0,
            "share": 1.0,
            "collect": 1.0,
            "comment": 0.8,
            "click": 0.5,
            "exposure": 0.0,
            "dislike": -1.0,
            "hide": -1.0,
            "report": -2.0
        }
        return mapping.get(event_type)

    def build_preference_pairs(
        self,
        df: pd.DataFrame,
        score_threshold: float = 0.5,
        min_prompt_length: int = 10,
        max_prompt_length: int = 2048,
        min_response_length: int = 10,
        max_response_length: int = 4096
    ) -> List[PreferencePair]:
        """构建偏好对

        Args:
            df: 原始数据 DataFrame
            score_threshold: 分数阈值
            min_prompt_length: 最小 prompt 长度
            max_prompt_length: 最大 prompt 长度
            min_response_length: 最小响应长度
            max_response_length: 最大响应长度

        Returns:
            偏好对列表
        """
        logger.info("Building preference pairs...")

        # 添加分数列
        df["reward_score"] = df.apply(
            lambda row: self.map_event_to_score(row["event_type"], row.get("feedback_value")),
            axis=1
        )
        df = df.dropna(subset=["reward_score"])

        # 长度过滤
        df = df[
            (df["prompt"].str.len() >= min_prompt_length) &
            (df["prompt"].str.len() <= max_prompt_length) &
            (df["generated_content"].str.len() >= min_response_length) &
            (df["generated_content"].str.len() <= max_response_length)
        ]

        # 按 prompt 分组
        pairs = []
        for prompt, group in df.groupby("prompt"):
            # 找出高分样本（chosen 候选）
            chosen_candidates = group[group["reward_score"] >= score_threshold]
            # 找出低分样本（rejected 候选）
            rejected_candidates = group[group["reward_score"] <= -score_threshold]

            if len(chosen_candidates) > 0 and len(rejected_candidates) > 0:
                # 取分数最高的作为 chosen，分数最低的作为 rejected
                chosen = chosen_candidates.loc[chosen_candidates["reward_score"].idxmax()]
                rejected = rejected_candidates.loc[rejected_candidates["reward_score"].idxmin()]

                # 确保 chosen 和 rejected 不是同一个生成内容
                if chosen["generated_content"] != rejected["generated_content"]:
                    pair = PreferencePair(
                        pair_id=f"online_{datetime.now().strftime('%Y%m%d')}_{len(pairs)}",
                        topic=prompt,
                        platform="xiaohongshu",
                        chosen_content=chosen["generated_content"],
                        rejected_content=rejected["generated_content"],
                        chosen_score=float(chosen["reward_score"]),
                        rejected_score=float(rejected["reward_score"]),
                        metadata={
                            "source": "online",
                            "chosen_model": chosen["model_version"],
                            "rejected_model": rejected["model_version"],
                            "chosen_pattern": chosen.get("pattern_id"),
                            "rejected_pattern": rejected.get("pattern_id")
                        }
                    )
                    pairs.append(pair)

        logger.info(f"Built {len(pairs)} preference pairs from online data")
        return pairs

    def load_helpsteer3_pairs(self, max_samples: int = None) -> List[PreferencePair]:
        """加载 HelpSteer3 偏好对

        Args:
            max_samples: 最大样本数

        Returns:
            偏好对列表
        """
        logger.info("Loading HelpSteer3 preference pairs...")

        train_path = os.path.join(self.helpsteer3_dir, "train.jsonl")

        if not os.path.exists(train_path):
            logger.warning(f"HelpSteer3 data not found: {train_path}")
            return []

        pairs = []
        with open(train_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if max_samples and i >= max_samples:
                    break

                data = json.loads(line)
                pair = PreferencePair(
                    pair_id=data.get("sample_id", f"helpsteer3_{i}"),
                    topic=data.get("prompt", ""),
                    platform="general",
                    chosen_content=data.get("chosen", ""),
                    rejected_content=data.get("rejected", ""),
                    chosen_score=10.0,
                    rejected_score=5.0,
                    metadata={"source": "helpsteer3"}
                )
                pairs.append(pair)

        logger.info(f"Loaded {len(pairs)} HelpSteer3 pairs")
        return pairs

    def mix_datasets(
        self,
        online_pairs: List[PreferencePair],
        helpsteer3_pairs: List[PreferencePair]
    ) -> List[PreferencePair]:
        """混合线上数据和 HelpSteer3 数据

        Args:
            online_pairs: 线上偏好对
            helpsteer3_pairs: HelpSteer3 偏好对

        Returns:
            混合后的偏好对列表
        """
        logger.info("Mixing online and HelpSteer3 datasets...")

        total_online = len(online_pairs)
        total_helpsteer3 = len(helpsteer3_pairs)

        if total_online == 0:
            logger.warning("No online data, using HelpSteer3 only")
            return helpsteer3_pairs

        # 计算目标数量
        target_online = int(total_online)
        target_helpsteer3 = int(target_online * (1 - self.mix_ratio) / self.mix_ratio)

        # 采样 HelpSteer3 数据
        import random
        if target_helpsteer3 < total_helpsteer3:
            sampled_helpsteer3 = random.sample(helpsteer3_pairs, target_helpsteer3)
        else:
            sampled_helpsteer3 = helpsteer3_pairs

        # 混合
        mixed_pairs = online_pairs + sampled_helpsteer3
        random.shuffle(mixed_pairs)

        logger.info(f"Mixed dataset: {len(online_pairs)} online + {len(sampled_helpsteer3)} HelpSteer3 = {len(mixed_pairs)} total")

        return mixed_pairs

    def save_preference_pairs(
        self,
        pairs: List[PreferencePair],
        date_str: str = None
    ) -> str:
        """保存偏好对到文件

        Args:
            pairs: 偏好对列表
            date_str: 日期字符串（默认今天）

        Returns:
            输出文件路径
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")

        output_path = os.path.join(self.output_dir, f"preference_pairs_{date_str}.jsonl")

        with open(output_path, 'w', encoding='utf-8') as f:
            for pair in pairs:
                data = {
                    "pair_id": pair.pair_id,
                    "prompt": pair.topic,
                    "chosen": pair.chosen_content,
                    "rejected": pair.rejected_content,
                    "chosen_score": pair.chosen_score,
                    "rejected_score": pair.rejected_score,
                    "source": pair.metadata.get("source", "unknown")
                }
                f.write(json.dumps(data, ensure_ascii=False) + '\n')

        logger.info(f"Saved {len(pairs)} preference pairs to {output_path}")
        return output_path

    def run_daily_pipeline(self, days: int = 1) -> Dict[str, Any]:
        """运行每日流水线

        Args:
            days: 收集天数

        Returns:
            运行结果
        """
        logger.info("="*80)
        logger.info("Running daily data pipeline...")
        logger.info("="*80)

        start_time = datetime.now()

        try:
            # 1. 获取线上反馈数据
            df = self.fetch_raw_feedback(days=days)

            # 2. 构建偏好对
            online_pairs = self.build_preference_pairs(df)

            # 3. 加载 HelpSteer3 数据
            helpsteer3_pairs = self.load_helpsteer3_pairs()

            # 4. 混合数据集
            mixed_pairs = self.mix_datasets(online_pairs, helpsteer3_pairs)

            # 5. 保存偏好对
            output_path = self.save_preference_pairs(mixed_pairs)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result = {
                "status": "success",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "online_pairs": len(online_pairs),
                "helpsteer3_pairs": len(helpsteer3_pairs),
                "total_pairs": len(mixed_pairs),
                "output_path": output_path
            }

            logger.info("="*80)
            logger.info("Daily pipeline completed successfully!")
            logger.info(f"Online pairs: {len(online_pairs)}")
            logger.info(f"HelpSteer3 pairs: {len(helpsteer3_pairs)}")
            logger.info(f"Total pairs: {len(mixed_pairs)}")
            logger.info(f"Output: {output_path}")
            logger.info("="*80)

            return result

        except Exception as e:
            logger.error(f"Daily pipeline failed: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Celery 任务示例
"""
from celery import Celery
from app.core.database import SessionLocal

celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task
def run_daily_data_pipeline():
    '''每日数据流水线任务'''
    db = SessionLocal()
    try:
        pipeline = DailyDataPipeline(db=db)
        result = pipeline.run_daily_pipeline()
        return result
    finally:
        db.close()

# 定时任务配置
celery_app.conf.beat_schedule = {
    'daily-data-pipeline': {
        'task': 'tasks.run_daily_data_pipeline',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨 2:00
    },
}
"""
