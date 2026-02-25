"""
爬虫模块初始化
"""

from app.data.crawlers.outcome_scraper import XHSOutcomeScraper, scrape_and_sync_outcomes

# 兼容旧模块：避免导入时因历史依赖（app.db 旧模型）导致整体失败
try:
    from app.data.crawlers.xhs_crawler import (
        XiaohongshuNote,
        SpiderXHSAdapter,
        XHSDownloaderAdapter,
        PlaywrightFallback,
        XHSCrawler,
    )
except Exception:  # pragma: no cover - 仅用于兼容旧代码路径
    XiaohongshuNote = None
    SpiderXHSAdapter = None
    XHSDownloaderAdapter = None
    PlaywrightFallback = None
    XHSCrawler = None

__all__ = [
    "XHSOutcomeScraper",
    "scrape_and_sync_outcomes",
    "XiaohongshuNote",
    "SpiderXHSAdapter",
    "XHSDownloaderAdapter",
    "PlaywrightFallback",
    "XHSCrawler",
]
