"""自动化 Outcome 采集器（生产级）。

能力：
1. Creator API 优先（若配置可用）
2. Playwright 爬虫降级
3. 选择器配置化（JSON）
4. 会话池（storage_state）支持
5. 失败回放（截图 + HTML）
6. 告警通知（Slack / PagerDuty）
"""

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.monitoring.alert_notifier import AlertNotifier

logger = logging.getLogger(__name__)


@dataclass
class ScrapedOutcome:
    """爬取到的帖子互动数据。"""

    post_url: str
    impressions: int = 0
    likes: int = 0
    comments: int = 0
    saves: int = 0
    shares: int = 0
    follows: int = 0
    scraped_at: str = ""
    source: str = "playwright"
    snapshot_path: Optional[str] = None


class XHSOutcomeScraper:
    """小红书帖子互动数据采集器。"""

    def __init__(self, mode: Optional[str] = None):
        self.settings = get_settings()
        self.mode = mode or self.settings.XHS_SCRAPER_MODE
        self.max_retries = max(1, int(self.settings.XHS_SCRAPER_MAX_RETRIES))
        self.timeout_ms = max(5000, int(self.settings.XHS_SCRAPER_TIMEOUT_MS))
        self.headless = bool(self.settings.XHS_SCRAPER_HEADLESS)
        self.allowed_domains = set(self.settings.get_xhs_allowed_domains())
        self.crawl_enabled = bool(self.settings.XHS_CRAWL_ENABLED and self.settings.XHS_CRAWL_ACCEPT_POLICY)
        self.notifier = AlertNotifier()
        self.selectors = self._load_selectors()

    def _load_selectors(self) -> Dict[str, Any]:
        config_path = self._resolve_path(self.settings.XHS_SELECTORS_CONFIG_PATH)
        if not config_path.exists():
            logger.warning(f"Selectors config not found: {config_path}, using default selectors")
            return {"metrics": {}}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to parse selectors config: {e}")
            return {"metrics": {}}

    @staticmethod
    def _resolve_path(raw_path: str) -> Path:
        p = Path(raw_path)
        if p.is_absolute():
            return p
        cwd = Path.cwd()
        # 候选1：相对当前目录
        candidates = [cwd / p]
        # 候选2：当前目录的父目录（当 cwd=backend 时支持 backend/config -> ../backend/config）
        candidates.append(cwd.parent / p)
        # 候选3：去掉开头的 "backend/" 前缀，再相对当前目录
        s = str(p).replace("\\", "/")
        if s.startswith("backend/"):
            candidates.append(cwd / s[len("backend/"):])
            candidates.append(cwd.parent / s[len("backend/"):])
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]

    async def scrape(self, post_url: str) -> Optional[ScrapedOutcome]:
        """爬取单个帖子的互动数据（带多级重试和模式降级）。"""
        if not self.crawl_enabled:
            logger.warning("XHS crawl disabled by policy flags (XHS_CRAWL_ENABLED/XHS_CRAWL_ACCEPT_POLICY)")
            return None
        if not self._is_allowed_xhs_url(post_url):
            logger.debug(f"Skipping non-XHS URL: {post_url}")
            return None

        # 优先 Creator API，可用性失败后自动降级 Playwright
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.mode == "creator_api":
                    result = await self._scrape_via_api(post_url)
                    if result:
                        return result
                result = await self._scrape_via_playwright(post_url)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"[XHS Scrape] attempt={attempt} url={post_url} error={e}")
                if attempt == self.max_retries:
                    self._notify_scrape_failure(post_url, str(e))
            await asyncio.sleep(min(2 * attempt, 8) + random.uniform(0.05, 0.3))
        return None

    def _is_allowed_xhs_url(self, post_url: str) -> bool:
        if not post_url:
            return False
        try:
            parsed = urlparse(post_url)
            host = (parsed.netloc or "").lower()
            if not host:
                return False
            return any(host == domain or host.endswith(f".{domain}") for domain in self.allowed_domains)
        except Exception:
            return False

    async def _scrape_via_api(self, post_url: str) -> Optional[ScrapedOutcome]:
        """通过创作者服务 API 获取数据（若配置可用）。"""
        api_base = self.settings.XHS_CREATOR_API_BASE
        token = self.settings.XHS_CREATOR_API_TOKEN
        if not api_base or not token:
            return None

        endpoint = api_base.rstrip("/") + "/content/metrics"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"post_url": post_url}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(endpoint, headers=headers, json=payload)
                if resp.status_code >= 400:
                    logger.warning(f"[Creator API] status={resp.status_code}, fallback to playwright")
                    return None
                data = resp.json()
        except Exception as e:
            logger.warning(f"[Creator API] request failed: {e}")
            return None

        metrics = data.get("data") or data
        outcome = ScrapedOutcome(
            post_url=post_url,
            impressions=int(metrics.get("impressions", 0) or 0),
            likes=int(metrics.get("likes", 0) or 0),
            comments=int(metrics.get("comments", 0) or 0),
            saves=int(metrics.get("saves", 0) or 0),
            shares=int(metrics.get("shares", 0) or 0),
            follows=int(metrics.get("follows", 0) or 0),
            scraped_at=datetime.utcnow().isoformat(),
            source="creator_api",
        )
        logger.info(f"[Creator API] {post_url} likes={outcome.likes} comments={outcome.comments}")
        return outcome

    def _choose_storage_state(self) -> Optional[str]:
        state_dir = self._resolve_path(self.settings.XHS_STORAGE_STATE_DIR)
        if not state_dir.exists():
            return None
        candidates = [p for p in state_dir.glob("*.json") if p.is_file()]
        if not candidates:
            return None
        return str(random.choice(candidates))

    async def _extract_metric(self, page, metric_name: str) -> int:
        metric_cfg = (self.selectors.get("metrics") or {}).get(metric_name, {})
        primary = metric_cfg.get("primary", []) or []
        fallback = metric_cfg.get("fallback", []) or []
        text_patterns = metric_cfg.get("text_patterns", []) or []

        # 1) 主选择器
        for sel in primary:
            val = await self._extract_by_selector(page, sel)
            if val > 0:
                return val

        # 2) 回退选择器
        for sel in fallback:
            val = await self._extract_by_selector(page, sel)
            if val > 0:
                return val

        # 3) 文本模式回退
        try:
            full_text = await page.text_content("body")
            if not full_text:
                return 0
            lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
            for line in lines:
                lowered = line.lower()
                if any(pat.lower() in lowered for pat in text_patterns):
                    parsed = self._parse_count(line)
                    if parsed > 0:
                        return parsed
        except Exception:
            pass
        return 0

    async def _extract_by_selector(self, page, selector: str) -> int:
        try:
            elements = await page.query_selector_all(selector)
            for el in elements:
                text = await el.text_content()
                if not text:
                    continue
                count = self._parse_count(text.strip())
                if count > 0:
                    return count
        except Exception:
            pass
        return 0

    async def _capture_snapshot(self, page, post_url: str, suffix: str = "error") -> Optional[str]:
        snapshot_dir = self._resolve_path(self.settings.XHS_SCRAPER_SNAPSHOT_DIR)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        safe_name = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        base = snapshot_dir / f"xhs_{safe_name}_{suffix}"
        png_path = str(base.with_suffix(".png"))
        html_path = str(base.with_suffix(".html"))
        meta_path = str(base.with_suffix(".json"))
        try:
            await page.screenshot(path=png_path, full_page=True)
            html = await page.content()
            Path(html_path).write_text(html, encoding="utf-8")
            Path(meta_path).write_text(
                json.dumps({"post_url": post_url, "captured_at": datetime.utcnow().isoformat()}, ensure_ascii=False),
                encoding="utf-8",
            )
            return png_path
        except Exception as e:
            logger.warning(f"Snapshot capture failed: {e}")
            return None

    async def _scrape_via_playwright(self, post_url: str) -> Optional[ScrapedOutcome]:
        """通过 Playwright 爬取公开页面数据（会话池 + 回放 + 多级提取）。"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install")
            return None

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        ]
        storage_state = self._choose_storage_state()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context_kwargs = {
                "user_agent": random.choice(user_agents),
                "viewport": {"width": 390, "height": 844},
                "is_mobile": True,
            }
            if storage_state:
                context_kwargs["storage_state"] = storage_state
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            snapshot_path: Optional[str] = None
            try:
                await page.goto(post_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                await page.wait_for_timeout(2500)

                outcome = ScrapedOutcome(
                    post_url=post_url,
                    scraped_at=datetime.utcnow().isoformat(),
                    source="playwright",
                )
                outcome.likes = await self._extract_metric(page, "likes")
                outcome.comments = await self._extract_metric(page, "comments")
                outcome.saves = await self._extract_metric(page, "saves")
                outcome.shares = await self._extract_metric(page, "shares")
                outcome.impressions = await self._extract_metric(page, "impressions")

                # 全 0 视为失败，触发快照和告警
                if (outcome.likes + outcome.comments + outcome.saves + outcome.shares + outcome.impressions) == 0:
                    snapshot_path = await self._capture_snapshot(page, post_url, suffix="empty")
                    outcome.snapshot_path = snapshot_path
                    self._notify_scrape_failure(post_url, "all metrics are zero", snapshot_path=snapshot_path)
                    logger.warning(f"[XHS Scrape] all metrics zero for {post_url}")
                    return None

                logger.info(
                    f"[XHS Scrape] {post_url}: likes={outcome.likes} comments={outcome.comments} "
                    f"saves={outcome.saves} shares={outcome.shares}"
                )
                return outcome
            except Exception as e:
                snapshot_path = await self._capture_snapshot(page, post_url, suffix="exception")
                self._notify_scrape_failure(post_url, str(e), snapshot_path=snapshot_path)
                logger.warning(f"[XHS Scrape] Failed for {post_url}: {e}")
                return None
            finally:
                await context.close()
                await browser.close()

    def _notify_scrape_failure(self, post_url: str, error: str, snapshot_path: Optional[str] = None):
        alert = f"WARNING: XHS scrape failed. url={post_url} error={error}"
        if snapshot_path:
            alert += f" snapshot={snapshot_path}"
        self.notifier.notify([alert])

    @staticmethod
    def _parse_count(text: str) -> int:
        """解析数量文本（如 '1.2万' → 12000）。"""
        import re

        raw = (text or "").replace(",", "").replace(" ", "")
        if not raw:
            return 0
        try:
            if "万" in raw:
                return int(float(raw.replace("万", "")) * 10000)
            lowered = raw.lower()
            if "w" in lowered:
                return int(float(lowered.replace("w", "")) * 10000)
            if raw.isdigit():
                return int(raw)
            nums = re.findall(r"[\d.]+", raw)
            if nums:
                return int(float(nums[0]))
        except (ValueError, IndexError):
            return 0
        return 0


async def scrape_and_sync_outcomes(
    db_session: AsyncSession,
    published_records: List[Dict[str, Any]],
) -> int:
    """
    批量爬取已发布帖子的互动数据并同步到 Outcome 表。

    Args:
        db_session: 数据库会话
        published_records: [{trace_id, platform_post_url, published_at}, ...]

    Returns:
        成功同步的条数
    """
    scraper = XHSOutcomeScraper()
    notifier = AlertNotifier()
    synced = 0
    attempted = 0
    failed = 0

    for record in published_records:
        post_url = record.get("platform_post_url", "")
        trace_id = record.get("trace_id", "")

        if not post_url or not trace_id:
            continue

        attempted += 1
        outcome_data = await scraper.scrape(post_url)
        if not outcome_data:
            failed += 1
            continue

        try:
            from app.ml.training.schemas import Outcome
            import uuid

            engagement_score = (
                outcome_data.likes * 3
                + outcome_data.comments * 5
                + outcome_data.saves * 4
                + outcome_data.shares * 6
            )
            existing_stmt = (
                select(Outcome)
                .where(Outcome.trace_id == trace_id)
                .where(Outcome.time_bucket == "24h")
                .order_by(Outcome.measured_at.desc())
                .limit(1)
            )
            existing = (await db_session.execute(existing_stmt)).scalar_one_or_none()

            if existing:
                outcome = existing
                outcome.impressions = outcome_data.impressions
                outcome.likes = outcome_data.likes
                outcome.comments = outcome_data.comments
                outcome.saves = outcome_data.saves
                outcome.shares = outcome_data.shares
                outcome.engagement_score = float(engagement_score)
                outcome.measured_at = datetime.utcnow()
                outcome.rl_synced = 0
                outcome.rl_synced_at = None
            else:
                outcome = Outcome(
                    id=str(uuid.uuid4()),
                    trace_id=trace_id,
                    impressions=outcome_data.impressions,
                    likes=outcome_data.likes,
                    comments=outcome_data.comments,
                    saves=outcome_data.saves,
                    shares=outcome_data.shares,
                    engagement_score=float(engagement_score),
                    time_bucket="24h",
                    measured_at=datetime.utcnow(),
                )
                db_session.add(outcome)
            await db_session.flush()

            # 触发 RL 同步
            from app.ml.rl.outcome_reward_bridge import sync_outcome_to_rl
            await sync_outcome_to_rl(
                db=db_session,
                trace_id=trace_id,
                engagement_score=float(engagement_score),
                time_bucket="24h",
            )

            synced += 1

        except Exception as e:
            logger.error(f"Failed to sync outcome for {trace_id}: {e}")
            failed += 1

        await asyncio.sleep(2)

    if attempted > 0:
        fail_ratio = failed / attempted
        if fail_ratio >= 0.5:
            notifier.notify(
                [
                    f"WARNING: XHS auto scrape high failure ratio "
                    f"failed={failed}/{attempted} ({fail_ratio:.1%})"
                ]
            )

    logger.info(
        f"[Auto Outcome] attempted={attempted} synced={synced} failed={failed} total={len(published_records)}"
    )
    return synced
