# MediaCrawler 快速使用指南

## 🚀 5分钟快速上手

### 1. 安装浏览器驱动

```bash
cd backend
playwright install chromium
```

### 2. 首次登录

```bash
# 登录小红书（会打开浏览器）
python scripts/mediacrawler_cli.py --platform xhs login

# 扫码登录后，登录态会自动保存
```

### 3. 开始使用

```bash
# 搜索笔记
python scripts/mediacrawler_cli.py search "护肤" --limit 5

# 获取笔记详情
python scripts/mediacrawler_cli.py detail <note_id>

# 获取评论
python scripts/mediacrawler_cli.py comments <note_id> --limit 20

# 采集并保存到数据库
python scripts/mediacrawler_cli.py crawl "美妆" --limit 50
```

---

## 📖 CLI 命令参考

### 全局参数

```bash
--platform xhs|douyin|bilibili  # 平台选择（默认: xhs）
--headless                       # 无头模式（不显示浏览器）
```

### login - 登录平台

```bash
python scripts/mediacrawler_cli.py --platform xhs login
```

首次使用必须登录，登录态会保存到 `./data/cookies/` 目录。

### search - 搜索笔记

```bash
python scripts/mediacrawler_cli.py search "关键词" [选项]

选项:
  --page N      页码（默认: 1）
  --limit N     显示数量（默认: 10）
```

示例:
```bash
# 搜索"护肤"相关笔记
python scripts/mediacrawler_cli.py search "护肤" --limit 20

# 无头模式搜索
python scripts/mediacrawler_cli.py --headless search "美妆"
```

### detail - 获取笔记详情

```bash
python scripts/mediacrawler_cli.py detail <note_id>
```

示例:
```bash
python scripts/mediacrawler_cli.py detail 65a1b2c3d4e5f6g7h8i9
```

### comments - 获取笔记评论

```bash
python scripts/mediacrawler_cli.py comments <note_id> [选项]

选项:
  --limit N     评论数量（默认: 20）
```

示例:
```bash
python scripts/mediacrawler_cli.py comments 65a1b2c3d4e5f6g7h8i9 --limit 50
```

### crawl - 采集并保存

```bash
python scripts/mediacrawler_cli.py crawl "分类" [选项]

选项:
  --limit N           采集数量（默认: 50）
  --time-window W     时间窗口（默认: 7d）
```

示例:
```bash
# 采集50条"护肤"笔记
python scripts/mediacrawler_cli.py crawl "护肤" --limit 50

# 采集最近24小时的"美妆"笔记
python scripts/mediacrawler_cli.py crawl "美妆" --time-window 24h --limit 30
```

---

## 💻 Python 代码使用

### 方式1: 直接使用 MediaCrawler

```python
from app.crawlers.mediacrawler_adapter import XiaohongshuCrawler, MediaCrawlerConfig

# 创建配置
config = MediaCrawlerConfig(platform="xhs", headless=True)
crawler = XiaohongshuCrawler(config)

# 启动
await crawler.start()

# 搜索
notes = await crawler.search_notes(keyword="护肤", page=1)

# 获取详情
detail = await crawler.get_note_detail(note_id="xxx")

# 获取评论
comments = await crawler.get_note_comments(note_id="xxx", max_count=50)

# 关闭
await crawler.close()
```

### 方式2: 通过适配器（推荐）

```python
from app.crawlers.xhs_crawler import SpiderXHSAdapter

# 创建适配器
adapter = SpiderXHSAdapter(use_mediacrawler=True, headless=True)

# 采集笔记
notes = await adapter.crawl_notes(
    category="护肤",
    time_window="7d",
    limit=50
)

# 自动转换为 XiaohongshuNote 格式
for note in notes:
    print(f"{note.note_id}: {note.title}")
    print(f"  点赞: {note.likes}, 评论: {note.comments}")
```

### 方式3: 完整流程

```python
from app.crawlers.xhs_crawler import XHSCrawler, SpiderXHSAdapter
from app.db import get_db

# 创建爬虫
crawler = XHSCrawler(
    spider_adapter=SpiderXHSAdapter(use_mediacrawler=True)
)

# 采集并保存到数据库
db = next(get_db())
stats = await crawler.crawl_and_save(
    category="美妆",
    time_window="7d",
    limit=100,
    db=db
)

print(f"成功: {stats['success']}, 失败: {stats['failed']}")
```

---

## 🔧 配置调整

编辑 `backend/config/mediacrawler_config.py`:

```python
# 启用/禁用 MediaCrawler
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
```

---

## 🐛 常见问题

### 1. 浏览器启动失败

```bash
# 重新安装浏览器驱动
playwright install chromium
```

### 2. 登录态过期

```bash
# 删除旧的 cookies
rm ./data/cookies/xhs_cookies.json

# 重新登录
python scripts/mediacrawler_cli.py login
```

### 3. 采集失败

- 检查网络连接
- 降低采集速率
- 查看日志文件

### 4. 数据为空

- 检查选择器是否正确
- 平台可能更新了页面结构
- 尝试手动访问确认

---

## 📊 性能建议

### 速率控制

```python
# 推荐设置
MAX_REQUESTS_PER_SECOND: float = 1.0   # 每秒1次
MAX_REQUESTS_PER_MINUTE: int = 30      # 每分钟30次
MAX_REQUESTS_PER_HOUR: int = 500       # 每小时500次
```

### 批量采集

```python
# 分批采集，避免一次性采集过多
for category in ["护肤", "美妆", "穿搭"]:
    notes = await adapter.crawl_notes(
        category=category,
        limit=50  # 每个分类50条
    )
    await asyncio.sleep(60)  # 批次间延迟
```

### 使用缓存

```python
# 启用缓存避免重复请求
from app.crawlers.xhs_crawler import EnhancedXHSCrawler

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
    force_refresh=False
)
```

---

## 📚 更多文档

- [完整集成指南](./MEDIACRAWLER_INTEGRATION.md)
- [集成完成报告](./MEDIACRAWLER_INTEGRATION_COMPLETE.md)
- [项目概览](./PROJECT_OVERVIEW.md)

---

## 🎯 下一步

1. ✅ 完成首次登录
2. ✅ 运行测试脚本验证
3. ✅ 开始采集数据
4. ✅ 根据需要调整配置
5. ✅ 集成到你的工作流

---

**最后更新**: 2026-02-12
