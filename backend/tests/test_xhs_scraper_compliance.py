import pytest

from app.data.crawlers.outcome_scraper import XHSOutcomeScraper


def test_xhs_url_allowlist():
    scraper = XHSOutcomeScraper()
    scraper.allowed_domains = {"xiaohongshu.com", "www.xiaohongshu.com"}

    assert scraper._is_allowed_xhs_url("https://www.xiaohongshu.com/explore/abc123")
    assert scraper._is_allowed_xhs_url("https://xiaohongshu.com/explore/abc123")
    assert not scraper._is_allowed_xhs_url("https://evil.com/xiaohongshu.com")
    assert not scraper._is_allowed_xhs_url("not-a-url")


@pytest.mark.asyncio
async def test_scrape_respects_policy_switch():
    scraper = XHSOutcomeScraper()
    scraper.crawl_enabled = False

    result = await scraper.scrape("https://www.xiaohongshu.com/explore/abc123")
    assert result is None
