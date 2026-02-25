"""
XHS-Downloader 适配器

集成 XHS-Downloader 开源项目，实现高质量文件下载
- 支持高清图片下载（PNG、WEBP、JPEG、HEIC）
- 支持视频文件下载
- 支持多种下载模式
"""

import logging
import asyncio
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import httpx
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class XHSDownloaderConfig:
    """XHS-Downloader 配置"""
    work_path: str = "./data"
    folder_name: str = "Download"
    name_format: str = "发布时间 作者昵称 作品标题"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    cookie: str = ""
    proxy: Optional[str] = None
    timeout: int = 10
    chunk: int = 1024 * 1024 * 2  # 2MB
    max_retry: int = 3
    image_format: str = "JPEG"  # AUTO, PNG, WEBP, JPEG, HEIC
    folder_mode: bool = False
    image_download: bool = True
    video_download: bool = True
    live_download: bool = False
    download_record: bool = True
    author_archive: bool = False
    write_mtime: bool = False


class XHSDownloaderCore:
    """
    XHS-Downloader 核心引擎

    基于 HTTP 请求的高质量文件下载器
    """

    def __init__(self, config: XHSDownloaderConfig):
        """
        初始化下载器

        Args:
            config: 配置对象
        """
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None

        # 创建下载目录
        self.download_dir = Path(config.work_path) / config.folder_name
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # 下载记录
        self.download_records = set()
        self._load_download_records()

        logger.info(f"✅ XHSDownloaderCore 初始化完成: {self.download_dir}")

    def _load_download_records(self):
        """加载下载记录"""
        record_file = Path(self.config.work_path) / "download_records.txt"
        if record_file.exists():
            with open(record_file, 'r', encoding='utf-8') as f:
                self.download_records = set(line.strip() for line in f if line.strip())
            logger.info(f"✅ 加载下载记录: {len(self.download_records)} 条")

    def _save_download_record(self, note_id: str):
        """保存下载记录"""
        if not self.config.download_record:
            return

        self.download_records.add(note_id)
        record_file = Path(self.config.work_path) / "download_records.txt"

        with open(record_file, 'a', encoding='utf-8') as f:
            f.write(f"{note_id}\n")

    def is_downloaded(self, note_id: str) -> bool:
        """检查是否已下载"""
        return note_id in self.download_records

    async def start(self):
        """启动下载器"""
        try:
            # 创建 HTTP 客户端
            self.client = httpx.AsyncClient(
                headers={"User-Agent": self.config.user_agent},
                cookies=self._parse_cookie(self.config.cookie),
                proxies=self.config.proxy,
                timeout=self.config.timeout,
                follow_redirects=True
            )

            logger.info("✅ XHS-Downloader 启动成功")

        except Exception as e:
            logger.error(f"❌ XHS-Downloader 启动失败: {e}")
            raise

    async def close(self):
        """关闭下载器"""
        if self.client:
            await self.client.aclose()
            logger.info("✅ XHS-Downloader 已关闭")

    def _parse_cookie(self, cookie_str: str) -> Dict[str, str]:
        """解析 Cookie 字符串"""
        if not cookie_str:
            return {}

        cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key.strip()] = value.strip()

        return cookies

    async def download_image(
        self,
        url: str,
        save_path: Path,
        note_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        下载图片

        Args:
            url: 图片 URL
            save_path: 保存路径
            note_id: 笔记 ID

        Returns:
            (success, error_message)
        """
        if not self.config.image_download:
            return False, "图片下载已禁用"

        # 检查是否已下载
        if self.config.download_record and save_path.exists():
            logger.debug(f"⏭️ 跳过已存在的文件: {save_path.name}")
            return True, None

        retry_count = 0
        while retry_count < self.config.max_retry:
            try:
                # 下载文件
                response = await self.client.get(url)
                response.raise_for_status()

                # 保存文件
                async with aiofiles.open(save_path, 'wb') as f:
                    await f.write(response.content)

                logger.info(f"✅ 图片下载成功: {save_path.name}")
                return True, None

            except Exception as e:
                retry_count += 1
                if retry_count < self.config.max_retry:
                    wait_time = 2 ** retry_count
                    logger.warning(f"⚠️ 下载失败，{wait_time}秒后重试 ({retry_count}/{self.config.max_retry})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 图片下载失败: {e}")
                    return False, str(e)

        return False, "下载失败，已达最大重试次数"

    async def download_video(
        self,
        url: str,
        save_path: Path,
        note_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        下载视频

        Args:
            url: 视频 URL
            save_path: 保存路径
            note_id: 笔记 ID

        Returns:
            (success, error_message)
        """
        if not self.config.video_download:
            return False, "视频下载已禁用"

        # 检查是否已下载
        if self.config.download_record and save_path.exists():
            logger.debug(f"⏭️ 跳过已存在的文件: {save_path.name}")
            return True, None

        retry_count = 0
        while retry_count < self.config.max_retry:
            try:
                # 流式下载大文件
                async with self.client.stream('GET', url) as response:
                    response.raise_for_status()

                    async with aiofiles.open(save_path, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=self.config.chunk):
                            await f.write(chunk)

                logger.info(f"✅ 视频下载成功: {save_path.name}")
                return True, None

            except Exception as e:
                retry_count += 1
                if retry_count < self.config.max_retry:
                    wait_time = 2 ** retry_count
                    logger.warning(f"⚠️ 下载失败，{wait_time}秒后重试 ({retry_count}/{self.config.max_retry})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 视频下载失败: {e}")
                    return False, str(e)

        return False, "下载失败，已达最大重试次数"

    def _generate_filename(
        self,
        note_data: Dict,
        index: int = 0,
        extension: str = "jpg"
    ) -> str:
        """
        生成文件名

        Args:
            note_data: 笔记数据
            index: 文件序号
            extension: 文件扩展名

        Returns:
            文件名
        """
        # 解析名称格式
        parts = []
        format_fields = self.config.name_format.split()

        for field in format_fields:
            if field == "发布时间":
                publish_time = note_data.get('publish_time', '')
                if isinstance(publish_time, datetime):
                    parts.append(publish_time.strftime('%Y%m%d'))
                elif publish_time:
                    parts.append(str(publish_time)[:10].replace('-', ''))
            elif field == "作者昵称":
                parts.append(note_data.get('author_name', 'unknown'))
            elif field == "作品标题":
                title = note_data.get('title', 'untitled')
                # 清理文件名非法字符
                title = self._sanitize_filename(title)
                parts.append(title[:50])  # 限制长度
            elif field == "作品ID":
                parts.append(note_data.get('note_id', 'unknown'))

        # 组合文件名
        filename = "_".join(parts)

        # 添加序号（如果有多个文件）
        if index > 0:
            filename = f"{filename}_{index}"

        return f"{filename}.{extension}"

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        return filename.strip()

    async def download_note_files(
        self,
        note_data: Dict,
        download_mode: str = "basic"
    ) -> Dict[str, Any]:
        """
        下载笔记的所有文件

        Args:
            note_data: 笔记数据
            download_mode: 下载模式（basic/enhanced/full）

        Returns:
            下载统计信息
        """
        note_id = note_data.get('note_id', '')
        if not note_id:
            return {'success': False, 'error': 'note_id 为空'}

        # 检查下载记录
        if self.config.download_record and self.is_downloaded(note_id):
            logger.info(f"⏭️ 跳过已下载的笔记: {note_id}")
            return {'success': True, 'skipped': True}

        stats = {
            'success': True,
            'images': 0,
            'videos': 0,
            'failed': 0,
            'files': []
        }

        try:
            # 创建作品文件夹（如果启用）
            if self.config.folder_mode:
                folder_name = self._generate_filename(note_data, extension='')
                work_dir = self.download_dir / folder_name
                work_dir.mkdir(parents=True, exist_ok=True)
            else:
                work_dir = self.download_dir

            # 下载封面图
            cover_url = note_data.get('cover_url')
            if cover_url and download_mode in ['basic', 'enhanced', 'full']:
                filename = self._generate_filename(note_data, 0, 'jpg')
                save_path = work_dir / filename

                success, error = await self.download_image(cover_url, save_path, note_id)
                if success:
                    stats['images'] += 1
                    stats['files'].append(str(save_path))
                else:
                    stats['failed'] += 1

            # 下载所有图片（enhanced/full 模式）
            if download_mode in ['enhanced', 'full']:
                image_urls = note_data.get('image_urls', [])
                for i, img_url in enumerate(image_urls, 1):
                    filename = self._generate_filename(note_data, i, 'jpg')
                    save_path = work_dir / filename

                    success, error = await self.download_image(img_url, save_path, note_id)
                    if success:
                        stats['images'] += 1
                        stats['files'].append(str(save_path))
                    else:
                        stats['failed'] += 1

                    # 速率限制
                    await asyncio.sleep(0.5)

            # 下载视频（full 模式）
            if download_mode == 'full':
                video_url = note_data.get('video_url')
                if video_url:
                    filename = self._generate_filename(note_data, 0, 'mp4')
                    save_path = work_dir / filename

                    success, error = await self.download_video(video_url, save_path, note_id)
                    if success:
                        stats['videos'] += 1
                        stats['files'].append(str(save_path))
                    else:
                        stats['failed'] += 1

            # 保存下载记录
            if stats['images'] > 0 or stats['videos'] > 0:
                self._save_download_record(note_id)

            logger.info(f"✅ 笔记文件下载完成: {note_id}, 图片={stats['images']}, 视频={stats['videos']}")

        except Exception as e:
            logger.error(f"❌ 下载笔记文件失败: {e}")
            stats['success'] = False
            stats['error'] = str(e)

        return stats


class XHSDownloaderAdapter:
    """
    XHS-Downloader 适配器

    提供统一的下载接口
    """

    def __init__(self, config: Optional[XHSDownloaderConfig] = None):
        """
        初始化适配器

        Args:
            config: 配置对象
        """
        if config is None:
            config = XHSDownloaderConfig()

        self.downloader = XHSDownloaderCore(config)
        logger.info("✅ XHSDownloaderAdapter 初始化完成")

    async def start(self):
        """启动下载器"""
        await self.downloader.start()

    async def close(self):
        """关闭下载器"""
        await self.downloader.close()

    async def download_note(
        self,
        note_data: Dict,
        download_mode: str = "basic"
    ) -> Dict[str, Any]:
        """
        下载笔记文件

        Args:
            note_data: 笔记数据
            download_mode: 下载模式
                - basic: 仅下载封面（快速）
                - enhanced: 下载所有图片（标准）
                - full: 下载所有图片+视频（完整）

        Returns:
            下载统计信息
        """
        return await self.downloader.download_note_files(note_data, download_mode)

    def is_downloaded(self, note_id: str) -> bool:
        """检查笔记是否已下载"""
        return self.downloader.is_downloaded(note_id)


# 导出
__all__ = [
    'XHSDownloaderConfig',
    'XHSDownloaderCore',
    'XHSDownloaderAdapter'
]
