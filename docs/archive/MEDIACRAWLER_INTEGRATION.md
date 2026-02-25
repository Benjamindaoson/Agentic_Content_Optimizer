# MediaCrawler 集成指南

## 📖 简介

本项目已集成 **MediaCrawler** 开源爬虫框架，支持多平台自媒体数据采集。

### 支持的平台

| 平台 | 状态 | 功能 |
|------|------|------|
| 小红书 | ✅ 已实现 | 搜索、详情、评论 |
| 抖音 | ✅ 已实现 | 基础框架 |
| B站 | ✅ 已实现 | 基础框架 |
| 快手 | 🚧 待实现 | - |
| 微博 | 🚧 待实现 | - |
| 知乎 | 🚧 待实现 | - |

---

## 🚀 快速开始

### 1. 安装依赖

Playwright 已包含在 `requirements.txt` 中，无需额外安装。

```bash
# 安装浏览器驱动
cd backend
playwright install chromium
```

### 2. 配置

编辑 `backend/config/mediacrawler_config.py`：

```python
# 是否启用 MediaCrawler（False=使用模拟数据）
ENABLE_MEDIACRAWLER: bool = True

# 浏览器模式（True=无头模式，False=显示浏览器）
HEADLESS: bool = True

# 速率限制
MAX_REQUESTS_PER_SECOND: float = 1.0
MAX_REQUESTS_PER_MINUTE: int = 30
```

### 3. 首次登录

首次使用需要扫码登录，登录态会自动保存。

```python
from app.crawlers.mediacrawler_adapter import XiaohongshuCrawler, MediaCrawlerConfig

# 创建配置（显示浏览器）
config = MediaCrawlerConfig(platform="xhs", headless=False)
crawler = XiaohongshuCrawler(config)

# 启动并登录
await crawler.start()
await crawler.login()  # 扫码登录

# 登录态会保存到 ./data/cookies/xhs_cookies.json
```

### 4. 开始采集

```python
# 搜索笔记
notes = await crawler.search_notes(keyword="护肤", page=1)

# 获取详情
detail = await crawler.get_note_detail(note_id="xxx")

# 获取评论
comments = await crawler.get_note_comments(note_id="xxx", max_count=50)
```

---

## 📚 使用方式

### 方式 1: 直接使用 MediaCrawler

适合需要精细控制的场景。

```python
from app.crawlers.mediacrawler_adapter import XiaohongshuCrawler, MediaCrawlerConfig

config = MediaCrawlerConfig(platform="xhs", headless=True)
crawler = XiaohongshuCrawler(config)

await crawler.start()

# 搜索
notes = await crawler.search_notes(keyword="美妆", page=1)

# 获取详情
for note in notes[:5]:
    detail = await crawler.get_note_detail(note['note_id'])
    print(detail)

await crawler.close()
```

### 方式 2: 通过适配器使用（推荐）

适合与现有系统集成。

```python
from app.crawlers.xhs_crawler import SpiderXHSAdapter

# 创建适配器（启用 MediaCrawler）
adapter = SpiderXHSAdapter(use_mediacrawler=True, headless=True)

# 采集笔记（自动转换为统一格式）
notes = await adapter.crawl_notes(
    category="护肤",
    time_window="7d",
    limit=20
)

# notes 是 List[XiaohongshuNote] 类型
for note in notes:
    print(f"{note.note_id}: {note.title}")
    print(f"  点赞: {note.likes}, 评论: {note.comments}")
```

### 方式 3: 完整流程（采集+保存）

适合生产环境。

```python
from app.crawlers.xhs_crawler import XHSCrawler, SpiderXHSAdapter
from app.db import get_db

# 创建爬虫
crawler = XHSCrawler(
    spider_adapter=SpiderXHSAdapter(use_mediacrawler=True, headless=True)
)

# 获取数据库会话
db = next(get_db())

# 采集并保存
stats = await crawler.crawl_and_save(
    category="美妆",
    time_window="7d",
    limit=50,
    db=db
)

print(f"成功: {stats['success']}, 失败: {stats['failed']}")
```

---

## 🔧 高级功能

### 1. 使用代理

```python
config = MediaCrawlerConfig(
    platform="xhs",
    headless=True,
    proxy="http://proxy.example.com:8080"
)
```

### 2. 自定义 User-Agent

```python
config = MediaCrawlerConfig(
    platform="xhs",
    headless=True,
    user_agent="Mozilla/5.0 ..."
)
```

### 3. 调整超时时间

```python
config = MediaCrawlerConfig(
    platform="xhs",
    headless=True,
    timeout=60000  # 60秒
)
```

### 4. 速率限制

通过 `EnhancedXHSCrawler` 使用内置的速率限制：

```python
from app.crawlers.xhs_crawler import EnhancedXHSCrawler
from app.crawlers.rate_limiter import RateLimitConfig

# 配置速率限制
rate_config = RateLimitConfig(
    max_requests_per_second=1.0,
    max_requests_per_minute=30,
    max_requests_per_hour=500
)

# 创建增强爬虫
crawler = EnhancedXHSCrawler(
    rate_limit_config=rate_config,
    enable_proxy=False
)

# 采集（自动应用速率限制）
stats = await crawler.crawl_viral_notes(
    category="护肤",
    limit=50,
    db=db
)
```

---

## 📝 运行示例

我们提供了完整的示例代码：

```bash
cd backend
python examples/mediacrawler_examples.py
```

示例包括：
1. 小红书关键词搜索
2. 获取笔记详情
3. 获取笔记评论
4. 使用集成的爬虫系统
5. 采集并保存到数据库
6. 多平台采集

---

## 🔐 登录态管理

### 保存登录态

登录成功后，登录态会自动保存到：

```
./data/cookies/
├── xhs_cookies.json      # 小红书
├── douyin_cookies.json   # 抖音
└── bilibili_cookies.json # B站
```

### 重新登录

如果登录态过期，删除对应的 cookies 文件，重新运行登录流程：

```bash
rm ./data/cookies/xhs_cookies.json
```

然后在代码中调用：

```python
await crawler.login()  # 重新扫码登录
```

---

## ⚙️ 配置说明

### 全局配置

编辑 `backend/config/mediacrawler_config.py`：

```python
class MediaCrawlerSettings:
    # 是否启用 MediaCrawler
    ENABLE_MEDIACRAWLER: bool = True

    # 浏览器模式
    HEADLESS: bool = True

    # 速率限制
    MAX_REQUESTS_PER_SECOND: float = 1.0
    MAX_REQUESTS_PER_MINUTE: int = 30
    MAX_REQUESTS_PER_HOUR: int = 500

    # 采集配置
    DEFAULT_LIMIT: int = 50
    MAX_LIMIT: int = 200
    CRAWL_COMMENTS: bool = True
    MAX_COMMENTS: int = 50

    # 缓存配置
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 86400  # 24小时
```

### 平台配置

每个平台都有独立的配置：

```python
XIAOHONGSHU: Dict[str, Any] = {
    "platform": "xhs",
    "base_url": "https://www.xiaohongshu.com",
    "login_url": "https://www.xiaohongshu.com/explore",
    "qrcode_selector": ".qrcode-img",
    "success_indicator": "explore",
    "enabled": True
}
```

---

## 🐛 故障排查

### 1. 浏览器启动失败

**问题**: `playwright.async_api._errors.Error: Executable doesn't exist`

**解决**:
```bash
playwright install chromium
```

### 2. 登录失败

**问题**: 二维码不显示或扫码后无响应

**解决**:
- 设置 `headless=False` 查看浏览器
- 检查网络连接
- 尝试更换代理

### 3. 采集失败

**问题**: 无法获取数据或返回空列表

**解决**:
- 检查登录态是否过期（删除 cookies 重新登录）
- 检查选择器是否正确（平台可能更新了页面结构）
- 降低采集速率

### 4. 速率限制

**问题**: 被平台限流或封号

**解决**:
- 降低 `MAX_REQUESTS_PER_SECOND`
- 增加 `REQUEST_INTERVAL`
- 启用代理池
- 使用多个账号轮换

---

## 📊 数据格式

### XiaohongshuNote 统一格式

所有采集的数据都会转换为统一格式：

```python
@dataclass
class XiaohongshuNote:
    note_id: str           # 笔记ID
    title: str             # 标题
    text: str              # 内容
    cover_url: str         # 封面URL
    image_urls: List[str]  # 图片列表
    author_id: str         # 作者ID
    author_name: str       # 作者名称
    publish_time: datetime # 发布时间
    category: str          # 分类
    tags: List[str]        # 标签
    views: int             # 浏览量
    likes: int             # 点赞数
    comments: int          # 评论数
    collects: int          # 收藏数
    shares: int            # 分享数
    raw_metadata: Dict     # 原始数据
```

---

## 🔄 与现有系统集成

MediaCrawler 已完全集成到现有的爬虫系统中：

```
backend/app/crawlers/
├── mediacrawler_adapter.py   # MediaCrawler 核心适配器
├── xhs_crawler.py             # 小红书爬虫（已集成 MediaCrawler）
├── rate_limiter.py            # 速率限制器
├── compliance_cache.py        # 合规缓存
└── proxy_pool.py              # 代理池
```

### 切换数据源

```python
# 使用 MediaCrawler（真实采集）
adapter = SpiderXHSAdapter(use_mediacrawler=True)

# 使用模拟数据（测试/演示）
adapter = SpiderXHSAdapter(use_mediacrawler=False)
```

---

## 📈 性能优化

### 1. 并发采集

```python
import asyncio

async def crawl_multiple_keywords():
    keywords = ["护肤", "美妆", "穿搭"]

    tasks = [
        adapter.crawl_notes(category=kw, limit=20)
        for kw in keywords
    ]

    results = await asyncio.gather(*tasks)
    return results
```

### 2. 批量处理

```python
# 批量获取详情
note_ids = ["id1", "id2", "id3", ...]

async def get_details_batch(note_ids, batch_size=10):
    for i in range(0, len(note_ids), batch_size):
        batch = note_ids[i:i+batch_size]
        tasks = [crawler.get_note_detail(nid) for nid in batch]
        details = await asyncio.gather(*tasks)
        yield details
        await asyncio.sleep(5)  # 批次间延迟
```

### 3. 使用缓存

```python
# 启用缓存避免重复请求
crawler = EnhancedXHSCrawler(
    cache_dir='./data/cache',
    enable_proxy=False
)

# 首次采集
stats = await crawler.crawl_viral_notes(category="护肤", limit=50)

# 再次采集（使用缓存）
stats = await crawler.crawl_viral_notes(
    category="护肤",
    limit=50,
    force_refresh=False  # 使用缓存
)
```

---

## 🔒 安全建议

1. **速率限制**: 严格控制请求频率，避免被封号
2. **登录态保护**: 不要泄露 cookies 文件
3. **代理使用**: 大规模采集时使用代理池
4. **错误处理**: 添加完善的异常处理和重试机制
5. **日志记录**: 记录所有采集活动，便于审计

---

## 📞 技术支持

如有问题，请查看：
- [MediaCrawler 官方文档](https://github.com/NanmiCoder/MediaCrawler)
- [Playwright 文档](https://playwright.dev/python/)
- 项目 Issues

---

**最后更新**: 2026-02-12
**维护者**: Claude Sonnet 4.5
