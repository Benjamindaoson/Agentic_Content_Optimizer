"""
小红书数据采集系统

集成三个开源项目：
1. Spider_XHS - 主力采集器（元数据）
2. XHS-Downloader - 封面下载器
3. Playwright - 兜底浏览器

核心约束：note_id 作为唯一主键（SSOT），保证封面、指标、文本一一对应
"""

import logging
import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

from sqlalchemy.orm import Session
from app.db import XHSNote, XHSMetrics, XHSCover, get_db
from app.data.crawlers.rate_limiter import AdaptiveRateLimiter, RateLimitConfig
from app.data.crawlers.compliance_cache import ComplianceCache
from app.data.crawlers.proxy_pool import ProxyPool, Proxy
from app.data.crawlers.mediacrawler_adapter import (
    MediaCrawlerConfig,
    XiaohongshuCrawler as MediaCrawlerXHS
)
from app.data.crawlers.xhs_downloader_adapter import (
    XHSDownloaderConfig,
    XHSDownloaderAdapter as XHSDownloaderHQ
)

logger = logging.getLogger(__name__)


@dataclass
class XiaohongshuNote:
    """
    统一的小红书笔记数据结构

    所有采集器必须输出这个格式
    """
    # 核心字段（必须）
    note_id: str

    # 基础信息
    title: str
    text: str
    cover_url: Optional[str] = None
    image_urls: List[str] = field(default_factory=list)

    # 作者信息
    author_id: Optional[str] = None
    author_name: Optional[str] = None

    # 元数据
    publish_time: Optional[datetime] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # 指标
    views: int = 0
    likes: int = 0
    comments: int = 0
    collects: int = 0
    shares: int = 0
    follows: int = 0

    # 原始数据
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """验证必填字段"""
        if not self.note_id:
            raise ValueError("note_id 不能为空")
        if not self.title:
            raise ValueError("title 不能为空")
        if not self.text:
            raise ValueError("text 不能为空")


class SpiderXHSAdapter:
    """
    MediaCrawler 适配器（原 Spider_XHS）

    使用 MediaCrawler 开源项目采集小红书数据
    """

    def __init__(self, use_mediacrawler: bool = True, headless: bool = True):
        """
        初始化适配器

        Args:
            use_mediacrawler: 是否使用 MediaCrawler（True=真实采集，False=模拟数据）
            headless: 是否无头模式
        """
        self.use_mediacrawler = use_mediacrawler
        self.mediacrawler = None

        if use_mediacrawler:
            config = MediaCrawlerConfig(
                platform="xhs",
                headless=headless,
                cookies_dir="./data/cookies"
            )
            self.mediacrawler = MediaCrawlerXHS(config)
            logger.info("✅ SpiderXHSAdapter 初始化完成（使用 MediaCrawler）")
        else:
            logger.info("✅ SpiderXHSAdapter 初始化完成（使用模拟数据）")

    async def crawl_notes(
        self,
        category: str,
        time_window: str = "7d",
        limit: int = 100
    ) -> List[XiaohongshuNote]:
        """
        使用 MediaCrawler 采集笔记

        Args:
            category: 分类（美妆/穿搭/美食等）
            time_window: 时间窗口（24h/7d/30d）
            limit: 采集数量

        Returns:
            笔记列表
        """
        logger.info(f"开始采集：分类={category}, 时间窗口={time_window}, 数量={limit}")

        notes = []

        try:
            if self.use_mediacrawler and self.mediacrawler:
                # 使用 MediaCrawler 真实采集
                raw_notes = await self._crawl_with_mediacrawler(category, limit)
            else:
                # 使用模拟数据
                raw_notes = self._mock_spider_data(category, limit)

            # 转换为统一格式
            for raw_note in raw_notes:
                try:
                    note = self._convert_to_xiaohongshu_note(raw_note)
                    notes.append(note)
                except Exception as e:
                    logger.error(f"转换笔记失败: {e}, raw_note={raw_note}")
                    continue

            logger.info(f"✅ 采集完成：成功 {len(notes)}/{len(raw_notes)} 条")

        except Exception as e:
            logger.error(f"❌ 采集失败: {e}")
            raise

        return notes

    async def _crawl_with_mediacrawler(
        self,
        keyword: str,
        limit: int
    ) -> List[Dict]:
        """
        使用 MediaCrawler 采集

        Args:
            keyword: 搜索关键词
            limit: 采集数量

        Returns:
            原始笔记数据列表
        """
        try:
            # 启动 MediaCrawler
            await self.mediacrawler.start()

            # 搜索笔记
            search_results = await self.mediacrawler.search_notes(
                keyword=keyword,
                page=1,
                sort_type="general"
            )

            # 获取详情
            raw_notes = []
            for i, result in enumerate(search_results[:limit]):
                try:
                    note_id = result.get('note_id')
                    if not note_id:
                        continue

                    # 获取笔记详情
                    detail = await self.mediacrawler.get_note_detail(note_id)
                    if detail:
                        # 合并搜索结果和详情
                        detail.update(result)
                        raw_notes.append(detail)

                    # 速率限制
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"获取笔记详情失败: {e}")
                    continue

            logger.info(f"✅ MediaCrawler 采集完成: {len(raw_notes)} 条")
            return raw_notes

        except Exception as e:
            logger.error(f"❌ MediaCrawler 采集失败: {e}")
            raise

        finally:
            # 关闭 MediaCrawler
            if self.mediacrawler:
                await self.mediacrawler.close()

    def _convert_to_xiaohongshu_note(self, raw_note: Dict) -> XiaohongshuNote:
        """
        将 MediaCrawler 的原始数据转换为 XiaohongshuNote

        Args:
            raw_note: MediaCrawler 返回的原始数据

        Returns:
            XiaohongshuNote 对象
        """
        # MediaCrawler 字段映射
        return XiaohongshuNote(
            note_id=raw_note.get('note_id', ''),
            title=raw_note.get('title', ''),
            text=raw_note.get('content', '') or raw_note.get('text', ''),
            cover_url=raw_note.get('cover_url', ''),
            image_urls=raw_note.get('image_urls', []),
            author_id=raw_note.get('author_id', ''),
            author_name=raw_note.get('author_name', '') or raw_note.get('author', ''),
            publish_time=self._parse_time(raw_note.get('publish_time')),
            category=raw_note.get('category', ''),
            tags=raw_note.get('tags', []),
            views=int(raw_note.get('views', 0)),
            likes=int(raw_note.get('likes', 0)),
            comments=int(raw_note.get('comments', 0)),
            collects=int(raw_note.get('collects', 0)),
            shares=int(raw_note.get('shares', 0)),
            follows=0,
            raw_metadata=raw_note
        )

    def _parse_time(self, time_str: Optional[str]) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None

        try:
            # 尝试多种时间格式
            from dateutil import parser
            return parser.parse(time_str)
        except Exception as e:
            logger.warning(f"时间解析失败: {time_str}, error={e}")
            return None

    def _mock_spider_data(self, category: str, limit: int) -> List[Dict]:
        """模拟 Spider_XHS 数据（仅用于测试）"""
        import random

        mock_data = []
        for i in range(min(limit, 10)):  # 限制模拟数据量
            mock_data.append({
                'note_id': f'mock_{category}_{i:04d}',
                'title': f'{category}爆款笔记 #{i+1}',
                'desc': f'这是一条关于{category}的爆款笔记内容，包含详细的介绍和推荐。',
                'cover': f'https://example.com/covers/{category}_{i}.jpg',
                'image_list': [
                    f'https://example.com/images/{category}_{i}_1.jpg',
                    f'https://example.com/images/{category}_{i}_2.jpg'
                ],
                'user': {
                    'user_id': f'user_{i % 5}',
                    'nickname': f'用户{i % 5}'
                },
                'time': datetime.now().isoformat(),
                'type': category,
                'tag_list': [category, '推荐', '种草'],
                'view_count': random.randint(100000, 500000),
                'liked_count': random.randint(5000, 20000),
                'comment_count': random.randint(500, 2000),
                'collected_count': random.randint(1000, 5000),
                'share_count': random.randint(500, 2000)
            })

        return mock_data


class XHSDownloaderAdapter:
    """
    XHS-Downloader 适配器（增强版）

    支持三级下载策略：
    - basic: 仅下载封面（快速）
    - enhanced: 下载所有图片（标准）
    - full: 下载所有图片+视频（完整）
    """

    def __init__(
        self,
        save_dir: str = "data/covers",
        download_mode: str = "basic",
        use_hq_downloader: bool = False
    ):
        """
        初始化下载器

        Args:
            save_dir: 封面保存目录
            download_mode: 下载模式（basic/enhanced/full）
            use_hq_downloader: 是否使用高质量下载器
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.download_mode = download_mode
        self.use_hq_downloader = use_hq_downloader

        # 高质量下载器（可选）
        self.hq_downloader = None
        if use_hq_downloader:
            config = XHSDownloaderConfig(
                work_path=str(self.save_dir.parent),
                folder_name=self.save_dir.name,
                image_download=True,
                video_download=(download_mode == "full"),
                folder_mode=False
            )
            self.hq_downloader = XHSDownloaderHQ(config)
            logger.info(f"✅ XHSDownloaderAdapter 初始化完成（高质量模式: {download_mode}）")
        else:
            logger.info(f"✅ XHSDownloaderAdapter 初始化完成（基础模式）")

    async def download_cover(
        self,
        note_id: str,
        cover_url: str,
        note_data: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        下载封面图

        Args:
            note_id: 笔记ID
            cover_url: 封面URL
            note_data: 笔记完整数据（用于高质量下载）

        Returns:
            (success, local_path, error_message)
        """
        if not cover_url:
            return False, None, "cover_url 为空"

        # 使用高质量下载器
        if self.use_hq_downloader and self.hq_downloader and note_data:
            try:
                await self.hq_downloader.start()

                stats = await self.hq_downloader.download_note(
                    note_data,
                    download_mode=self.download_mode
                )

                await self.hq_downloader.close()

                if stats.get('success') and stats.get('files'):
                    local_path = stats['files'][0]
                    logger.info(f"✅ 高质量下载成功: {note_id}, 文件数={len(stats['files'])}")
                    return True, local_path, None
                else:
                    return False, None, stats.get('error', '下载失败')

            except Exception as e:
                logger.error(f"❌ 高质量下载失败: {e}")
                # 降级到基础下载
                return await self._basic_download(note_id, cover_url)

        # 基础下载
        return await self._basic_download(note_id, cover_url)

    async def _basic_download(
        self,
        note_id: str,
        cover_url: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        基础下载（快速）

        Args:
            note_id: 笔记ID
            cover_url: 封面URL

        Returns:
            (success, local_path, error_message)
        """
        local_path = self.save_dir / f"{note_id}.jpg"

        try:
            # 使用 httpx 下载
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(cover_url)
                response.raise_for_status()

                # 保存文件
                local_path.write_bytes(response.content)

            logger.info(f"✅ 封面下载成功: {note_id} -> {local_path}")
            return True, str(local_path), None

        except Exception as e:
            logger.error(f"❌ 封面下载失败: {note_id}, error={e}")
            return False, None, str(e)


class PlaywrightFallback:
    """
    Playwright 兜底浏览器

    当 Spider_XHS 和 XHS-Downloader 都失败时使用
    """

    def __init__(self, save_dir: str = "data/covers"):
        """
        初始化 Playwright

        Args:
            save_dir: 封面保存目录
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.browser = None
        logger.info(f"✅ PlaywrightFallback 初始化完成")

    async def init_browser(self):
        """初始化浏览器"""
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            logger.info("✅ Playwright 浏览器启动成功")

        except Exception as e:
            logger.error(f"❌ Playwright 浏览器启动失败: {e}")
            raise

    async def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            logger.info("✅ Playwright 浏览器已关闭")

    async def screenshot_cover(
        self,
        note_id: str,
        note_url: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        截图封面（兜底方案）

        Args:
            note_id: 笔记ID
            note_url: 笔记URL

        Returns:
            (success, local_path, error_message)
        """
        if not self.browser:
            await self.init_browser()

        local_path = self.save_dir / f"{note_id}.jpg"

        try:
            page = await self.browser.new_page()
            await page.goto(note_url, wait_until='networkidle')

            # 等待封面加载
            await page.wait_for_selector('img.cover', timeout=5000)

            # 截图封面区域
            cover_element = await page.query_selector('img.cover')
            if cover_element:
                await cover_element.screenshot(path=str(local_path))
                logger.info(f"✅ Playwright 截图成功: {note_id} -> {local_path}")
                await page.close()
                return True, str(local_path), None
            else:
                await page.close()
                return False, None, "未找到封面元素"

        except Exception as e:
            logger.error(f"❌ Playwright 截图失败: {note_id}, error={e}")
            return False, None, str(e)


class XHSCrawler:
    """
    小红书采集器（主控制器）

    协调三个采集工具，保证数据完整性
    支持三级下载策略：basic/enhanced/full
    """

    def __init__(
        self,
        spider_adapter: Optional[SpiderXHSAdapter] = None,
        downloader_adapter: Optional[XHSDownloaderAdapter] = None,
        playwright_fallback: Optional[PlaywrightFallback] = None,
        download_mode: str = "basic"
    ):
        """
        初始化采集器

        Args:
            spider_adapter: Spider_XHS 适配器
            downloader_adapter: XHS-Downloader 适配器
            playwright_fallback: Playwright 兜底
            download_mode: 下载模式（basic/enhanced/full）
        """
        self.spider = spider_adapter or SpiderXHSAdapter()
        self.downloader = downloader_adapter or XHSDownloaderAdapter(download_mode=download_mode)
        self.playwright = playwright_fallback or PlaywrightFallback()
        self.download_mode = download_mode

        logger.info(f"✅ XHSCrawler 初始化完成（下载模式: {download_mode}）")

    async def crawl_and_save(
        self,
        category: str,
        time_window: str = "7d",
        limit: int = 100,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        采集并保存到数据库

        Args:
            category: 分类
            time_window: 时间窗口
            limit: 采集数量
            db: 数据库会话

        Returns:
            统计信息
        """
        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'cover_downloaded': 0,
            'cover_failed': 0
        }

        # 1. 采集笔记元数据
        notes = await self.spider.crawl_notes(category, time_window, limit)
        stats['total'] = len(notes)

        # 2. 逐条处理
        for note in notes:
            try:
                # 2.1 下载封面
                cover_success, cover_path, cover_error = await self._download_cover_with_fallback(note)

                if cover_success:
                    stats['cover_downloaded'] += 1
                else:
                    stats['cover_failed'] += 1
                    logger.warning(f"封面下载失败: {note.note_id}, error={cover_error}")

                # 2.2 保存到数据库（事务）
                if db:
                    self._save_to_db(note, cover_path, db)
                    stats['success'] += 1

            except Exception as e:
                logger.error(f"处理笔记失败: {note.note_id}, error={e}")
                stats['failed'] += 1
                continue

        logger.info(f"✅ 采集完成: {stats}")
        return stats

    async def _download_cover_with_fallback(
        self,
        note: XiaohongshuNote
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        下载封面（带兜底）

        优先级：XHS-Downloader → Playwright

        Returns:
            (success, local_path, error_message)
        """
        # 尝试 1: XHS-Downloader（支持高质量下载）
        if note.cover_url:
            # 准备笔记数据（用于高质量下载）
            note_data = {
                'note_id': note.note_id,
                'title': note.title,
                'content': note.text,
                'cover_url': note.cover_url,
                'image_urls': note.image_urls,
                'author_name': note.author_name,
                'author_id': note.author_id,
                'publish_time': note.publish_time,
                'likes': note.likes,
                'comments': note.comments,
                'collects': note.collects
            }

            success, path, error = await self.downloader.download_cover(
                note.note_id,
                note.cover_url,
                note_data=note_data
            )
            if success:
                return True, path, None

        # 尝试 2: Playwright 兜底
        note_url = f"https://www.xiaohongshu.com/explore/{note.note_id}"
        success, path, error = await self.playwright.screenshot_cover(
            note.note_id,
            note_url
        )

        return success, path, error

    def _save_to_db(
        self,
        note: XiaohongshuNote,
        cover_path: Optional[str],
        db: Session
    ):
        """
        保存到数据库（原子操作）

        必须同时写入三表：notes + metrics + covers
        """
        try:
            # 1. 保存笔记主表
            db_note = XHSNote(
                note_id=note.note_id,
                title=note.title,
                text=note.text,
                cover_url=note.cover_url,
                image_urls=note.image_urls,
                author_id=note.author_id,
                author_name=note.author_name,
                publish_time=note.publish_time,
                category=note.category,
                tags=note.tags,
                raw_metadata=note.raw_metadata,
                crawled_at=datetime.now()
            )
            db.merge(db_note)  # 使用 merge 避免重复

            # 2. 保存指标表
            db_metrics = XHSMetrics(
                note_id=note.note_id,
                views=note.views,
                likes=note.likes,
                comments=note.comments,
                collects=note.collects,
                shares=note.shares,
                follows=note.follows,
                engagement_rate=self._calculate_engagement_rate(note)
            )
            db.merge(db_metrics)

            # 3. 保存封面表
            if cover_path:
                db_cover = XHSCover(
                    note_id=note.note_id,
                    local_path=cover_path,
                    image_hash=self._calculate_image_hash(cover_path),
                    download_status='success',
                    downloaded_at=datetime.now()
                )
                db.merge(db_cover)

            db.commit()
            logger.info(f"✅ 保存成功: {note.note_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 保存失败: {note.note_id}, error={e}")
            raise

    def _calculate_engagement_rate(self, note: XiaohongshuNote) -> float:
        """计算互动率"""
        if note.views == 0:
            return 0.0
        return (note.likes + note.comments + note.collects + note.shares) / note.views

    def _calculate_image_hash(self, image_path: str) -> str:
        """计算图片哈希（用于去重）"""
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"计算图片哈希失败: {e}")
            return ""


# ==================== 增强版采集器（带风控） ====================

class EnhancedXHSCrawler:
    """
    增强版小红书采集器

    新增功能：
    1. 速率限制（自适应）
    2. 合规缓存（避免重复请求）
    3. 代理池（IP 轮换）
    4. 错误重试（指数退避）
    5. 实时监控
    """

    def __init__(
        self,
        rate_limit_config: Optional[RateLimitConfig] = None,
        cache_dir: str = './cache',
        enable_proxy: bool = False,
        proxy_pool: Optional[ProxyPool] = None
    ):
        """
        Args:
            rate_limit_config: 速率限制配置
            cache_dir: 缓存目录
            enable_proxy: 是否启用代理
            proxy_pool: 代理池（如果启用代理）
        """
        # 基础采集器
        self.base_crawler = XHSCrawler()

        # 速率限制器
        if rate_limit_config is None:
            rate_limit_config = RateLimitConfig(
                max_requests_per_second=2.0,
                max_requests_per_minute=60,
                max_requests_per_hour=1000,
                burst_size=5,
                cooldown_on_error=60
            )
        self.rate_limiter = AdaptiveRateLimiter(rate_limit_config)

        # 合规缓存
        self.cache = ComplianceCache(
            memory_size=1000,
            cache_dir=cache_dir,
            default_ttl=86400  # 24 小时
        )

        # 代理池
        self.enable_proxy = enable_proxy
        self.proxy_pool = proxy_pool

        # 统计信息
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'rate_limit_waits': 0,
            'proxy_switches': 0,
            'errors': 0
        }

        logger.info("✅ EnhancedXHSCrawler 初始化完成")

    async def crawl_viral_notes(
        self,
        category: str,
        time_window: str = "7d",
        limit: int = 100,
        db: Optional[Session] = None,
        force_refresh: bool = False
    ) -> Dict:
        """
        采集爆款笔记（增强版）

        Args:
            category: 分类
            time_window: 时间窗口
            limit: 采集数量
            db: 数据库会话
            force_refresh: 是否强制刷新（忽略缓存）

        Returns:
            统计信息
        """
        logger.info(f"开始增强采集：分类={category}, 时间窗口={time_window}, 数量={limit}")

        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'cached': 0,
            'cover_downloaded': 0,
            'cover_failed': 0
        }

        # 1. 采集笔记元数据
        notes = await self._crawl_notes_with_cache(
            category,
            time_window,
            limit,
            force_refresh
        )
        stats['total'] = len(notes)

        # 2. 逐条处理
        for note in notes:
            try:
                # 2.1 检查缓存
                cached_note = await self.cache.get('note', note.note_id, allow_stale=not force_refresh)

                if cached_note and not force_refresh:
                    stats['cached'] += 1
                    stats['success'] += 1
                    logger.debug(f"使用缓存: {note.note_id}")
                    continue

                # 2.2 速率限制
                await self.rate_limiter.acquire()
                self.stats['rate_limit_waits'] += 1

                # 2.3 下载封面（带代理）
                start_time = time.time()
                cover_success, cover_path, cover_error = await self._download_cover_with_proxy(note)
                response_time = time.time() - start_time

                if cover_success:
                    stats['cover_downloaded'] += 1
                    self.rate_limiter.report_success(response_time)
                else:
                    stats['cover_failed'] += 1
                    self.rate_limiter.report_error('download_failed')
                    logger.warning(f"封面下载失败: {note.note_id}, error={cover_error}")

                # 2.4 保存到数据库
                if db:
                    self.base_crawler._save_to_db(note, cover_path, db)
                    stats['success'] += 1

                # 2.5 写入缓存
                await self.cache.set(
                    'note',
                    note.note_id,
                    {
                        'note_id': note.note_id,
                        'title': note.title,
                        'text': note.text,
                        'cover_path': cover_path,
                        'cached_at': datetime.now().isoformat()
                    },
                    ttl=86400
                )

            except Exception as e:
                logger.error(f"处理笔记失败: {note.note_id}, error={e}")
                stats['failed'] += 1
                self.stats['errors'] += 1
                self.rate_limiter.report_error('processing_failed')
                continue

        # 3. 更新统计
        self.stats['total_requests'] += stats['total']
        self.stats['cache_hits'] += stats['cached']
        self.stats['cache_misses'] += (stats['total'] - stats['cached'])

        logger.info(f"✅ 增强采集完成: {stats}")
        return stats

    async def _crawl_notes_with_cache(
        self,
        category: str,
        time_window: str,
        limit: int,
        force_refresh: bool
    ) -> List[XiaohongshuNote]:
        """
        采集笔记（带缓存）

        Args:
            category: 分类
            time_window: 时间窗口
            limit: 采集数量
            force_refresh: 是否强制刷新

        Returns:
            笔记列表
        """
        cache_key = f"{category}_{time_window}_{limit}"

        # 尝试从缓存获取
        if not force_refresh:
            cached_notes = await self.cache.get('notes_list', cache_key, allow_stale=True)
            if cached_notes:
                logger.info(f"使用缓存的笔记列表: {cache_key}")
                # 反序列化
                return [
                    XiaohongshuNote(**note_data)
                    for note_data in cached_notes
                ]

        # 从源获取
        await self.rate_limiter.acquire()
        notes = await self.base_crawler.spider.crawl_notes(category, time_window, limit)

        # 写入缓存
        notes_data = [
            {
                'note_id': note.note_id,
                'title': note.title,
                'text': note.text,
                'cover_url': note.cover_url,
                'image_urls': note.image_urls,
                'author_id': note.author_id,
                'author_name': note.author_name,
                'publish_time': note.publish_time.isoformat() if note.publish_time else None,
                'category': note.category,
                'tags': note.tags,
                'views': note.views,
                'likes': note.likes,
                'comments': note.comments,
                'collects': note.collects,
                'shares': note.shares,
                'follows': note.follows,
                'raw_metadata': note.raw_metadata
            }
            for note in notes
        ]

        await self.cache.set('notes_list', cache_key, notes_data, ttl=3600)  # 1 小时

        return notes

    async def _download_cover_with_proxy(
        self,
        note: XiaohongshuNote
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        下载封面（带代理）

        Args:
            note: 笔记对象

        Returns:
            (success, local_path, error_message)
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 获取代理
                proxy = None
                if self.enable_proxy and self.proxy_pool:
                    proxy = self.proxy_pool.get_proxy(strategy='smart')
                    if proxy:
                        self.stats['proxy_switches'] += 1
                        logger.debug(f"使用代理: {proxy.url}")

                # 下载封面
                success, path, error = await self.base_crawler._download_cover_with_fallback(note)

                # 报告代理状态
                if proxy:
                    if success:
                        self.proxy_pool.mark_success(proxy, time.time())
                    else:
                        self.proxy_pool.mark_failure(proxy)

                if success:
                    return True, path, None

                # 失败重试
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # 指数退避
                    logger.warning(f"下载失败，{wait_time}秒后重试 ({retry_count}/{max_retries})")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"下载封面异常: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(2 ** retry_count)

        return False, None, f"下载失败，已重试 {max_retries} 次"

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'crawler': self.stats,
            'rate_limiter': self.rate_limiter.get_stats(),
            'cache': self.cache.get_stats(),
            'proxy_pool': self.proxy_pool.get_stats() if self.proxy_pool else None
        }

    async def cleanup(self):
        """清理资源"""
        # 清理过期缓存
        await self.cache.cleanup()

        # 移除不可用代理
        if self.proxy_pool:
            self.proxy_pool.remove_unavailable()

        logger.info("✅ 资源清理完成")
