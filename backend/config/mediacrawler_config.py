"""
MediaCrawler 配置文件

配置多平台爬虫参数
"""

from typing import Dict, Any


class MediaCrawlerSettings:
    """MediaCrawler 全局设置"""

    # ==================== 基础配置 ====================

    # 是否启用 MediaCrawler（False=使用模拟数据）
    ENABLE_MEDIACRAWLER: bool = True

    # 浏览器模式（True=无头模式，False=显示浏览器）
    HEADLESS: bool = True

    # Cookies 保存目录
    COOKIES_DIR: str = "./data/cookies"

    # 请求超时时间（毫秒）
    TIMEOUT: int = 30000

    # ==================== 速率限制 ====================

    # 每秒最大请求数
    MAX_REQUESTS_PER_SECOND: float = 1.0

    # 每分钟最大请求数
    MAX_REQUESTS_PER_MINUTE: int = 30

    # 每小时最大请求数
    MAX_REQUESTS_PER_HOUR: int = 500

    # 请求间隔（秒）
    REQUEST_INTERVAL: float = 2.0

    # ==================== 采集配置 ====================

    # 默认采集数量
    DEFAULT_LIMIT: int = 50

    # 最大采集数量
    MAX_LIMIT: int = 200

    # 是否采集评论
    CRAWL_COMMENTS: bool = True

    # 最大评论数
    MAX_COMMENTS: int = 50

    # 是否下载封面
    DOWNLOAD_COVERS: bool = True

    # 封面保存目录
    COVERS_DIR: str = "./data/covers"

    # ==================== 下载策略配置 ⭐ 新增 ====================

    # 下载模式（basic/enhanced/full）
    DOWNLOAD_MODE: str = "basic"

    # 是否启用高质量下载器
    USE_HQ_DOWNLOADER: bool = False

    # 下载模式说明：
    # - basic: 仅下载封面（快速，适合日常采集）
    # - enhanced: 下载所有图片（标准，适合素材收集）
    # - full: 下载所有图片+视频（完整，适合重要内容）

    # 图片下载格式
    IMAGE_FORMAT: str = "JPEG"  # AUTO, PNG, WEBP, JPEG, HEIC

    # 视频下载开关
    VIDEO_DOWNLOAD: bool = True

    # 是否将每个作品的文件储存至单独的文件夹
    FOLDER_MODE: bool = False

    # 是否记录下载成功的作品 ID
    DOWNLOAD_RECORD: bool = True

    # 是否将每个作者的作品存至单独的文件夹
    AUTHOR_ARCHIVE: bool = False

    # 是否将作品文件的修改时间修改为作品的发布时间
    WRITE_MTIME: bool = False

    # ==================== 平台配置 ====================

    # 小红书配置
    XIAOHONGSHU: Dict[str, Any] = {
        "platform": "xhs",
        "base_url": "https://www.xiaohongshu.com",
        "login_url": "https://www.xiaohongshu.com/explore",
        "qrcode_selector": ".qrcode-img",
        "success_indicator": "explore",
        "enabled": True
    }

    # 抖音配置
    DOUYIN: Dict[str, Any] = {
        "platform": "douyin",
        "base_url": "https://www.douyin.com",
        "login_url": "https://www.douyin.com",
        "qrcode_selector": ".qrcode",
        "success_indicator": "user",
        "enabled": True
    }

    # B站配置
    BILIBILI: Dict[str, Any] = {
        "platform": "bilibili",
        "base_url": "https://www.bilibili.com",
        "login_url": "https://www.bilibili.com",
        "qrcode_selector": ".qrcode-img",
        "success_indicator": "space",
        "enabled": True
    }

    # 快手配置
    KUAISHOU: Dict[str, Any] = {
        "platform": "kuaishou",
        "base_url": "https://www.kuaishou.com",
        "enabled": False  # 暂未实现
    }

    # 微博配置
    WEIBO: Dict[str, Any] = {
        "platform": "weibo",
        "base_url": "https://weibo.com",
        "enabled": False  # 暂未实现
    }

    # 知乎配置
    ZHIHU: Dict[str, Any] = {
        "platform": "zhihu",
        "base_url": "https://www.zhihu.com",
        "enabled": False  # 暂未实现
    }

    # ==================== 代理配置 ====================

    # 是否启用代理
    ENABLE_PROXY: bool = False

    # 代理列表
    PROXY_LIST: list = [
        # "http://proxy1.example.com:8080",
        # "http://proxy2.example.com:8080",
    ]

    # ==================== 缓存配置 ====================

    # 是否启用缓存
    ENABLE_CACHE: bool = True

    # 缓存目录
    CACHE_DIR: str = "./data/cache"

    # 缓存过期时间（秒）
    CACHE_TTL: int = 86400  # 24小时

    # ==================== 日志配置 ====================

    # 日志级别
    LOG_LEVEL: str = "INFO"

    # 日志文件
    LOG_FILE: str = "./logs/mediacrawler.log"

    # ==================== 安全配置 ====================

    # 用户代理
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # 是否随机化 User-Agent
    RANDOMIZE_USER_AGENT: bool = True

    # 重试次数
    MAX_RETRIES: int = 3

    # 重试间隔（秒）
    RETRY_INTERVAL: float = 5.0


# 导出配置实例
settings = MediaCrawlerSettings()
