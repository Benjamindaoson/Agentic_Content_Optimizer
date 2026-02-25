"""
特征工程模块

用于从笔记中提取特征，供机器学习模型使用
"""

import logging
from typing import Dict, List, Optional
import re
import jieba
import numpy as np
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    特征提取器

    从笔记中提取多维度特征，用于训练预测模型
    """

    def __init__(self):
        # 停用词
        self.stopwords = set([
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去'
        ])

        # 情感词典（简化版）
        self.positive_words = set([
            '好', '棒', '赞', '喜欢', '爱', '美', '漂亮', '完美', '推荐',
            '值得', '必买', '惊艳', '绝了', '太好了', '超级', '非常'
        ])

        self.negative_words = set([
            '差', '烂', '不好', '失望', '后悔', '难用', '不推荐',
            '踩雷', '翻车', '一般', '不值', '浪费'
        ])

    def extract_text_features(self, title: str, text: str) -> Dict:
        """
        提取文本特征

        Args:
            title: 标题
            text: 正文

        Returns:
            文本特征字典
        """
        # 分词
        title_words = list(jieba.cut(title))
        text_words = list(jieba.cut(text))
        all_words = title_words + text_words

        # 去除停用词
        filtered_words = [w for w in all_words if w not in self.stopwords and len(w) > 1]

        # 1. 基础统计特征
        features = {
            # 长度特征
            'title_length': len(title),
            'text_length': len(text),
            'total_length': len(title) + len(text),
            'word_count': len(filtered_words),
            'avg_word_length': np.mean([len(w) for w in filtered_words]) if filtered_words else 0,

            # 标题特征
            'title_word_count': len(title_words),
            'title_has_emoji': int(self._has_emoji(title)),
            'title_has_number': int(bool(re.search(r'\d', title))),
            'title_has_exclamation': int('!' in title or '！' in title),
            'title_has_question': int('?' in title or '？' in title),

            # 正文特征
            'text_paragraph_count': len(text.split('\n')),
            'text_has_emoji': int(self._has_emoji(text)),
            'text_has_number': int(bool(re.search(r'\d', text))),
        }

        # 2. 情感特征
        positive_count = sum(1 for w in filtered_words if w in self.positive_words)
        negative_count = sum(1 for w in filtered_words if w in self.negative_words)

        features.update({
            'positive_word_count': positive_count,
            'negative_word_count': negative_count,
            'sentiment_score': (positive_count - negative_count) / max(len(filtered_words), 1)
        })

        # 3. 词频特征
        word_freq = Counter(filtered_words)
        top_words = word_freq.most_common(10)

        features.update({
            'unique_word_count': len(word_freq),
            'word_diversity': len(word_freq) / max(len(filtered_words), 1),
            'top_word_freq': top_words[0][1] if top_words else 0
        })

        # 4. 特殊符号特征
        features.update({
            'emoji_count': self._count_emoji(title + text),
            'hashtag_count': text.count('#'),
            'at_count': text.count('@'),
            'url_count': len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text))
        })

        return features

    def extract_structure_features(self, title: str, text: str) -> Dict:
        """
        提取结构特征

        Args:
            title: 标题
            text: 正文

        Returns:
            结构特征字典
        """
        features = {}

        # 1. 标题结构
        features['title_has_colon'] = int(':' in title or '：' in title)
        features['title_has_bracket'] = int('【' in title or '】' in title or '[' in title or ']' in title)
        features['title_has_dash'] = int('-' in title or '—' in title)

        # 2. 正文结构
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        features['paragraph_count'] = len(paragraphs)
        features['avg_paragraph_length'] = np.mean([len(p) for p in paragraphs]) if paragraphs else 0

        # 3. 列表结构
        features['has_numbered_list'] = int(bool(re.search(r'^\d+[.、]', text, re.MULTILINE)))
        features['has_bullet_list'] = int(bool(re.search(r'^[·•]', text, re.MULTILINE)))

        # 4. 强调结构
        features['has_bold'] = int('**' in text or '__' in text)
        features['has_italic'] = int('*' in text or '_' in text)

        return features

    def extract_timing_features(self, publish_time: Optional[datetime]) -> Dict:
        """
        提取时间特征

        Args:
            publish_time: 发布时间

        Returns:
            时间特征字典
        """
        if not publish_time:
            return {
                'hour': 0,
                'day_of_week': 0,
                'is_weekend': 0,
                'is_morning': 0,
                'is_afternoon': 0,
                'is_evening': 0,
                'is_night': 0
            }

        hour = publish_time.hour
        day_of_week = publish_time.weekday()

        return {
            'hour': hour,
            'day_of_week': day_of_week,
            'is_weekend': int(day_of_week >= 5),
            'is_morning': int(6 <= hour < 12),
            'is_afternoon': int(12 <= hour < 18),
            'is_evening': int(18 <= hour < 22),
            'is_night': int(hour >= 22 or hour < 6)
        }

    def extract_metrics_features(self, metrics: Dict) -> Dict:
        """
        提取指标特征

        Args:
            metrics: 指标字典

        Returns:
            指标特征字典
        """
        views = metrics.get('views', 0)
        likes = metrics.get('likes', 0)
        comments = metrics.get('comments', 0)
        collects = metrics.get('collects', 0)
        shares = metrics.get('shares', 0)

        features = {
            'views': views,
            'likes': likes,
            'comments': comments,
            'collects': collects,
            'shares': shares,

            # 互动率
            'like_rate': likes / max(views, 1),
            'comment_rate': comments / max(views, 1),
            'collect_rate': collects / max(views, 1),
            'share_rate': shares / max(views, 1),

            # 互动比例
            'comment_like_ratio': comments / max(likes, 1),
            'collect_like_ratio': collects / max(likes, 1),
            'share_like_ratio': shares / max(likes, 1),

            # 总互动
            'total_engagement': likes + comments + collects + shares,
            'engagement_rate': (likes + comments + collects + shares) / max(views, 1)
        }

        return features

    def extract_author_features(self, author_id: str, db) -> Dict:
        """
        提取作者特征

        Args:
            author_id: 作者ID
            db: 数据库会话

        Returns:
            作者特征字典
        """
        from sqlalchemy import func
        from app.db import XHSNote, XHSMetrics

        # 统计作者历史数据
        author_notes = db.query(XHSNote).filter(
            XHSNote.author_id == author_id
        ).all()

        if not author_notes:
            return {
                'author_note_count': 0,
                'author_avg_views': 0,
                'author_avg_likes': 0,
                'author_avg_viral_score': 0
            }

        # 计算平均指标
        total_views = 0
        total_likes = 0
        total_viral_scores = []

        for note in author_notes:
            metrics = db.query(XHSMetrics).filter(
                XHSMetrics.note_id == note.note_id
            ).first()

            if metrics:
                total_views += metrics.views
                total_likes += metrics.likes
                if metrics.viral_score:
                    total_viral_scores.append(metrics.viral_score)

        return {
            'author_note_count': len(author_notes),
            'author_avg_views': total_views / len(author_notes),
            'author_avg_likes': total_likes / len(author_notes),
            'author_avg_viral_score': np.mean(total_viral_scores) if total_viral_scores else 0
        }

    def extract_all_features(
        self,
        title: str,
        text: str,
        publish_time: Optional[datetime],
        metrics: Dict,
        author_id: Optional[str],
        db
    ) -> Dict:
        """
        提取所有特征

        Args:
            title: 标题
            text: 正文
            publish_time: 发布时间
            metrics: 指标
            author_id: 作者ID
            db: 数据库会话

        Returns:
            完整特征字典
        """
        features = {}

        # 1. 文本特征
        features.update(self.extract_text_features(title, text))

        # 2. 结构特征
        features.update(self.extract_structure_features(title, text))

        # 3. 时间特征
        features.update(self.extract_timing_features(publish_time))

        # 4. 指标特征
        features.update(self.extract_metrics_features(metrics))

        # 5. 作者特征
        if author_id and db:
            features.update(self.extract_author_features(author_id, db))

        return features

    def _has_emoji(self, text: str) -> bool:
        """检查是否包含emoji"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "]+",
            flags=re.UNICODE
        )
        return bool(emoji_pattern.search(text))

    def _count_emoji(self, text: str) -> int:
        """统计emoji数量"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "]+",
            flags=re.UNICODE
        )
        return len(emoji_pattern.findall(text))


# ==================== 使用示例 ====================

def example_usage():
    """使用示例"""
    extractor = FeatureExtractor()

    # 示例数据
    title = "🔥超好用的护肤品推荐！干皮必看"
    text = """
    姐妹们，今天给大家分享几款我最近在用的护肤品！

    1. **保湿精华**
    这款精华真的太好用了，用了一周皮肤明显变水润了。

    2. **面霜**
    质地很轻薄，不油腻，吸收很快。

    3. **眼霜**
    淡化细纹效果不错，坚持用会有效果。

    #护肤 #干皮救星 #好物推荐
    """

    publish_time = datetime.now()
    metrics = {
        'views': 10000,
        'likes': 500,
        'comments': 50,
        'collects': 200,
        'shares': 30
    }

    # 提取特征
    features = extractor.extract_all_features(
        title=title,
        text=text,
        publish_time=publish_time,
        metrics=metrics,
        author_id=None,
        db=None
    )

    print(f"提取的特征数量: {len(features)}")
    print(f"特征示例: {list(features.items())[:10]}")
