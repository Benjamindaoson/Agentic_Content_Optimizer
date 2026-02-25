"""
MediaCrawler 适配器

集成 MediaCrawler 开源项目，支持多平台数据采集
- 小红书、抖音、快手、B站、微博、贴吧、知乎

技术原理：
- 基于 Playwright 浏览器自动化
- 保存登录态，无需 JS 逆向
- 通过 JS 表达式获取签名参数
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


@dataclass
class MediaCrawlerConfig:
    """MediaCrawler 配置"""
    platform: str  # xhs, douyin, kuaishou, bilibili, weibo, tieba, zhihu
    headless: bool = True
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    cookies_dir: str = "./data/cookies"
    timeout: int = 30000  # 30秒


class MediaCrawlerCore:
    """
    MediaCrawler 核心引擎

    基于 Playwright 的多平台爬虫核心
    """

    def __init__(self, config: MediaCrawlerConfig):
        """
        初始化 MediaCrawler

        Args:
            config: 配置对象
        """
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # 创建 cookies 目录
        Path(config.cookies_dir).mkdir(parents=True, exist_ok=True)

        logger.info(f"✅ MediaCrawlerCore 初始化完成: platform={config.platform}")

    async def start(self):
        """启动浏览器"""
        try:
            self.playwright = await async_playwright().start()

            # 启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                proxy={"server": self.config.proxy} if self.config.proxy else None
            )

            # 创建上下文
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": self.config.user_agent or await self.browser.version()
            }

            # 尝试加载已保存的 cookies
            cookies_file = Path(self.config.cookies_dir) / f"{self.config.platform}_cookies.json"
            if cookies_file.exists():
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    context_options["storage_state"] = cookies
                    logger.info(f"✅ 加载已保存的登录态: {cookies_file}")

            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()

            # 设置超时
            self.page.set_default_timeout(self.config.timeout)

            logger.info("✅ 浏览器启动成功")

        except Exception as e:
            logger.error(f"❌ 浏览器启动失败: {e}")
            raise

    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

            logger.info("✅ 浏览器已关闭")

        except Exception as e:
            logger.error(f"❌ 关闭浏览器失败: {e}")

    async def save_cookies(self):
        """保存登录态"""
        try:
            cookies_file = Path(self.config.cookies_dir) / f"{self.config.platform}_cookies.json"
            storage_state = await self.context.storage_state()

            with open(cookies_file, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 登录态已保存: {cookies_file}")

        except Exception as e:
            logger.error(f"❌ 保存登录态失败: {e}")

    async def login_by_qrcode(self, login_url: str, qrcode_selector: str, success_indicator: str):
        """
        二维码登录

        Args:
            login_url: 登录页面 URL
            qrcode_selector: 二维码元素选择器
            success_indicator: 登录成功标识（URL 包含的字符串）
        """
        try:
            logger.info(f"🔐 开始二维码登录: {login_url}")

            # 访问登录页
            await self.page.goto(login_url)

            # 等待二维码出现
            await self.page.wait_for_selector(qrcode_selector, timeout=10000)
            logger.info("📱 请使用手机 APP 扫描二维码登录...")

            # 等待登录成功（URL 变化）
            await self.page.wait_for_url(f"**/*{success_indicator}*", timeout=120000)

            logger.info("✅ 登录成功！")

            # 保存登录态
            await self.save_cookies()

        except Exception as e:
            logger.error(f"❌ 二维码登录失败: {e}")
            raise

    async def execute_js(self, js_code: str) -> Any:
        """
        执行 JavaScript 代码

        Args:
            js_code: JS 代码

        Returns:
            执行结果
        """
        try:
            result = await self.page.evaluate(js_code)
            return result
        except Exception as e:
            logger.error(f"❌ 执行 JS 失败: {e}")
            return None


class XiaohongshuCrawler:
    """
    小红书爬虫（基于 MediaCrawler）
    """

    def __init__(self, config: Optional[MediaCrawlerConfig] = None):
        """
        初始化小红书爬虫

        Args:
            config: 配置对象
        """
        if config is None:
            config = MediaCrawlerConfig(platform="xhs")

        self.core = MediaCrawlerCore(config)
        self.base_url = "https://www.xiaohongshu.com"

        logger.info("✅ XiaohongshuCrawler 初始化完成")

    async def start(self):
        """启动爬虫"""
        await self.core.start()

    async def close(self):
        """关闭爬虫"""
        await self.core.close()

    async def login(self):
        """登录小红书"""
        await self.core.login_by_qrcode(
            login_url=f"{self.base_url}/explore",
            qrcode_selector=".qrcode-img",
            success_indicator="explore"
        )

    async def search_notes(
        self,
        keyword: str,
        page: int = 1,
        sort_type: str = "general"
    ) -> List[Dict]:
        """
        搜索笔记

        Args:
            keyword: 搜索关键词
            page: 页码
            sort_type: 排序类型 (general=综合, popularity_descending=最热)

        Returns:
            笔记列表
        """
        try:
            logger.info(f"🔍 搜索笔记: keyword={keyword}, page={page}")

            # 构造搜索 URL
            search_url = f"{self.base_url}/search_result?keyword={keyword}&source=web_search_result_notes"

            # 访问搜索页
            await self.core.page.goto(search_url)
            await asyncio.sleep(2)  # 等待加载

            # 滚动加载更多内容
            for _ in range(3):
                await self.core.page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            # 提取笔记数据（通过 JS）
            notes_data = await self.core.execute_js("""
                () => {
                    const notes = [];
                    const noteElements = document.querySelectorAll('.note-item');

                    noteElements.forEach(el => {
                        try {
                            const link = el.querySelector('a');
                            const title = el.querySelector('.title')?.textContent || '';
                            const author = el.querySelector('.author')?.textContent || '';
                            const likes = el.querySelector('.like-count')?.textContent || '0';

                            if (link) {
                                const noteId = link.href.split('/').pop();
                                notes.push({
                                    note_id: noteId,
                                    title: title.trim(),
                                    author: author.trim(),
                                    likes: parseInt(likes.replace(/[^0-9]/g, '') || '0'),
                                    url: link.href
                                });
                            }
                        } catch (e) {
                            console.error('解析笔记失败:', e);
                        }
                    });

                    return notes;
                }
            """)

            logger.info(f"✅ 搜索完成: 找到 {len(notes_data or [])} 条笔记")
            return notes_data or []

        except Exception as e:
            logger.error(f"❌ 搜索笔记失败: {e}")
            return []

    async def get_note_detail(self, note_id: str) -> Optional[Dict]:
        """
        获取笔记详情

        Args:
            note_id: 笔记 ID

        Returns:
            笔记详情
        """
        try:
            logger.info(f"📄 获取笔记详情: note_id={note_id}")

            # 访问笔记页
            note_url = f"{self.base_url}/explore/{note_id}"
            await self.core.page.goto(note_url)
            await asyncio.sleep(2)

            # 提取笔记详情（通过 JS）
            note_detail = await self.core.execute_js("""
                () => {
                    try {
                        // 提取标题
                        const title = document.querySelector('.title')?.textContent || '';

                        // 提取内容
                        const content = document.querySelector('.content')?.textContent || '';

                        // 提取作者信息
                        const authorName = document.querySelector('.author-name')?.textContent || '';
                        const authorId = document.querySelector('.author-link')?.href?.split('/').pop() || '';

                        // 提取互动数据
                        const likes = document.querySelector('.like-count')?.textContent || '0';
                        const collects = document.querySelector('.collect-count')?.textContent || '0';
                        const comments = document.querySelector('.comment-count')?.textContent || '0';

                        // 提取封面图
                        const coverImg = document.querySelector('.cover-img')?.src || '';

                        // 提取标签
                        const tags = Array.from(document.querySelectorAll('.tag')).map(el => el.textContent.trim());

                        return {
                            title: title.trim(),
                            content: content.trim(),
                            author_name: authorName.trim(),
                            author_id: authorId,
                            likes: parseInt(likes.replace(/[^0-9]/g, '') || '0'),
                            collects: parseInt(collects.replace(/[^0-9]/g, '') || '0'),
                            comments: parseInt(comments.replace(/[^0-9]/g, '') || '0'),
                            cover_url: coverImg,
                            tags: tags
                        };
                    } catch (e) {
                        console.error('解析笔记详情失败:', e);
                        return null;
                    }
                }
            """)

            if note_detail:
                note_detail['note_id'] = note_id
                logger.info(f"✅ 获取笔记详情成功: {note_id}")
            else:
                logger.warning(f"⚠️ 未能解析笔记详情: {note_id}")

            return note_detail

        except Exception as e:
            logger.error(f"❌ 获取笔记详情失败: {e}")
            return None

    async def get_note_comments(
        self,
        note_id: str,
        max_count: int = 50
    ) -> List[Dict]:
        """
        获取笔记评论

        Args:
            note_id: 笔记 ID
            max_count: 最大评论数

        Returns:
            评论列表
        """
        try:
            logger.info(f"💬 获取笔记评论: note_id={note_id}, max_count={max_count}")

            # 访问笔记页
            note_url = f"{self.base_url}/explore/{note_id}"
            await self.core.page.goto(note_url)
            await asyncio.sleep(2)

            # 滚动加载评论
            for _ in range(5):
                await self.core.page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)

            # 提取评论（通过 JS）
            comments_data = await self.core.execute_js(f"""
                () => {{
                    const comments = [];
                    const commentElements = document.querySelectorAll('.comment-item');

                    commentElements.forEach((el, index) => {{
                        if (index >= {max_count}) return;

                        try {{
                            const author = el.querySelector('.comment-author')?.textContent || '';
                            const content = el.querySelector('.comment-content')?.textContent || '';
                            const likes = el.querySelector('.comment-like-count')?.textContent || '0';
                            const time = el.querySelector('.comment-time')?.textContent || '';

                            comments.push({{
                                author: author.trim(),
                                content: content.trim(),
                                likes: parseInt(likes.replace(/[^0-9]/g, '') || '0'),
                                time: time.trim()
                            }});
                        }} catch (e) {{
                            console.error('解析评论失败:', e);
                        }}
                    }});

                    return comments;
                }}
            """)

            logger.info(f"✅ 获取评论完成: {len(comments_data or [])} 条")
            return comments_data or []

        except Exception as e:
            logger.error(f"❌ 获取评论失败: {e}")
            return []


class DouyinCrawler:
    """抖音爬虫（基于 MediaCrawler）"""

    def __init__(self, config: Optional[MediaCrawlerConfig] = None):
        if config is None:
            config = MediaCrawlerConfig(platform="douyin")
        self.core = MediaCrawlerCore(config)
        self.base_url = "https://www.douyin.com"
        logger.info("✅ DouyinCrawler 初始化完成")

    async def start(self):
        await self.core.start()

    async def close(self):
        await self.core.close()

    async def login(self):
        """登录抖音"""
        await self.core.login_by_qrcode(
            login_url=f"{self.base_url}",
            qrcode_selector=".qrcode",
            success_indicator="user"
        )


class BilibiliCrawler:
    """B站爬虫（基于 MediaCrawler）"""

    def __init__(self, config: Optional[MediaCrawlerConfig] = None):
        if config is None:
            config = MediaCrawlerConfig(platform="bilibili")
        self.core = MediaCrawlerCore(config)
        self.base_url = "https://www.bilibili.com"
        logger.info("✅ BilibiliCrawler 初始化完成")

    async def start(self):
        await self.core.start()

    async def close(self):
        await self.core.close()

    async def login(self):
        """登录 B 站"""
        await self.core.login_by_qrcode(
            login_url=f"{self.base_url}",
            qrcode_selector=".qrcode-img",
            success_indicator="space"
        )


# 导出
__all__ = [
    'MediaCrawlerConfig',
    'MediaCrawlerCore',
    'XiaohongshuCrawler',
    'DouyinCrawler',
    'BilibiliCrawler'
]
