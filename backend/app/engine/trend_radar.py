"""
实时热点雷达 (Trend Radar)

多平台热点捕获 → 交叉验证 → 与账号匹配度评分。
数据源优先级：
1. 微博热搜（公开 JSON 接口，免费）
2. 百度热搜（公开接口）
3. 小红书搜索下拉词（需爬虫，降级为 LLM 模拟）

设计哲学：
- 能用公开 API 就不爬虫
- 能用缓存就不重复请求
- 热点数据缓存 30 分钟（热点生命周期 4-8h，30min 刷新足够）
"""

import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TrendSignal:
    """热点信号"""
    keyword: str
    source: str  # weibo / baidu / xhs / cross_validated
    heat: float = 0.0
    category: str = ""
    url: str = ""
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def cache_key(self) -> str:
        return hashlib.md5(f"{self.keyword}:{self.source}".encode()).hexdigest()


@dataclass
class ScoredTrend:
    """带评分的热点"""
    keyword: str
    score: float  # 综合评分 [0, 1]
    heat: float
    sources: List[str]
    category: str = ""
    account_fit: float = 0.0  # 与账号定位的匹配度
    freshness: float = 1.0


class TrendRadar:
    """
    实时热点雷达

    使用场景（手动触发为主）：
    - 运营人员打开「热点雷达」页面，看到实时热点列表
    - 选择感兴趣的热点，点击「一键生成」
    - 不需要全自动，运营人员的判断力是不可替代的
    """

    CACHE_TTL_SECONDS = 1800  # 30 分钟缓存

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_ts: float = 0

    async def scan(self, account_niche: str = "") -> List[ScoredTrend]:
        """
        全平台扫描热点。

        Args:
            account_niche: 账号定位（如 "护肤", "穿搭"），用于匹配度评分

        Returns:
            按综合评分排序的热点列表
        """
        import time
        now = time.time()
        if now - self._cache_ts < self.CACHE_TTL_SECONDS and self._cache.get("trends"):
            logger.info("Trend radar: returning cached results")
            trends = self._cache["trends"]
        else:
            signals = []

            weibo = await self._scan_weibo()
            signals.extend(weibo)

            baidu = await self._scan_baidu()
            signals.extend(baidu)

            cross_validated = self._cross_validate(signals)
            trends = self._score_trends(cross_validated, account_niche)

            self._cache = {"trends": trends}
            self._cache_ts = now

        return sorted(trends, key=lambda x: x.score, reverse=True)

    async def _scan_weibo(self) -> List[TrendSignal]:
        """微博热搜（公开 JSON 接口，无需 API key）"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://weibo.com/ajax/side/hotSearch",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://weibo.com",
                    },
                )
                if resp.status_code != 200:
                    logger.warning(f"Weibo API returned {resp.status_code}")
                    return []

                data = resp.json()
                realtime = data.get("data", {}).get("realtime", [])

                signals = []
                for item in realtime[:30]:
                    word = item.get("word", "")
                    if not word:
                        continue
                    signals.append(TrendSignal(
                        keyword=word,
                        source="weibo",
                        heat=float(item.get("num", 0)),
                        category=item.get("category", ""),
                        url=f"https://s.weibo.com/weibo?q=%23{word}%23",
                    ))

                logger.info(f"Weibo: fetched {len(signals)} trends")
                return signals

        except Exception as e:
            logger.warning(f"Weibo scan failed: {e}")
            return []

    async def _scan_baidu(self) -> List[TrendSignal]:
        """百度热搜（公开接口）"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://top.baidu.com/api/board?platform=wise&tab=realtime",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                cards = data.get("data", {}).get("cards", [])

                signals = []
                for card in cards:
                    for item in card.get("content", [])[:20]:
                        word = item.get("word", "") or item.get("query", "")
                        if not word:
                            continue
                        signals.append(TrendSignal(
                            keyword=word,
                            source="baidu",
                            heat=float(item.get("hotScore", 0)),
                            url=item.get("url", ""),
                        ))

                logger.info(f"Baidu: fetched {len(signals)} trends")
                return signals

        except Exception as e:
            logger.warning(f"Baidu scan failed: {e}")
            return []

    def _cross_validate(self, signals: List[TrendSignal]) -> List[Dict[str, Any]]:
        """
        交叉验证：同时出现在多个平台的话题加权。
        去重 + 合并来源。
        """
        keyword_map: Dict[str, Dict[str, Any]] = {}

        for sig in signals:
            key = sig.keyword.strip().lower()
            if key not in keyword_map:
                keyword_map[key] = {
                    "keyword": sig.keyword,
                    "sources": [sig.source],
                    "heat": sig.heat,
                    "category": sig.category,
                    "url": sig.url,
                }
            else:
                entry = keyword_map[key]
                if sig.source not in entry["sources"]:
                    entry["sources"].append(sig.source)
                entry["heat"] = max(entry["heat"], sig.heat)
                if sig.category and not entry["category"]:
                    entry["category"] = sig.category

        return list(keyword_map.values())

    def _score_trends(
        self, validated: List[Dict[str, Any]], account_niche: str = ""
    ) -> List[ScoredTrend]:
        """综合评分：热度 × 多平台加成 × 账号匹配度"""
        if not validated:
            return []

        max_heat = max(t["heat"] for t in validated) or 1.0

        scored = []
        for t in validated:
            heat_norm = t["heat"] / max_heat

            # 多平台加成：出现在 2+ 平台的话题 +30% 分
            cross_bonus = 1.0 + 0.3 * (len(t["sources"]) - 1)

            # 账号匹配度（简单关键词匹配）
            account_fit = 0.5
            if account_niche:
                kw_lower = t["keyword"].lower()
                niche_lower = account_niche.lower()
                if niche_lower in kw_lower or kw_lower in niche_lower:
                    account_fit = 1.0
                elif any(c in kw_lower for c in niche_lower.split()):
                    account_fit = 0.7

            score = heat_norm * cross_bonus * (0.6 + 0.4 * account_fit)
            score = min(score, 1.0)

            scored.append(ScoredTrend(
                keyword=t["keyword"],
                score=round(score, 3),
                heat=t["heat"],
                sources=t["sources"],
                category=t.get("category", ""),
                account_fit=round(account_fit, 2),
            ))

        return scored

    async def get_topic_heat(self, topic: str) -> Optional[ScoredTrend]:
        """查询特定话题的热度"""
        trends = await self.scan()
        topic_lower = topic.lower()
        for t in trends:
            if topic_lower in t.keyword.lower() or t.keyword.lower() in topic_lower:
                return t
        return None

    async def suggest_alternatives(self, topic: str, top_k: int = 5) -> List[ScoredTrend]:
        """当用户输入的话题热度不高时，建议相近的高热度话题"""
        trends = await self.scan()
        topic_chars = set(topic)
        candidates = []
        for t in trends:
            overlap = len(topic_chars & set(t.keyword))
            if overlap >= 1:
                candidates.append((overlap, t))

        candidates.sort(key=lambda x: (-x[0], -x[1].score))
        return [t for _, t in candidates[:top_k]]
