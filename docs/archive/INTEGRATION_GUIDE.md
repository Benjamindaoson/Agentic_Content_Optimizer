# 🔧 风控组件集成指南

## 快速开始

### 1. 基础集成

```python
from app.crawlers.xhs_crawler import EnhancedXHSCrawler
from app.crawlers.rate_limiter import RateLimitConfig
from app.crawlers.proxy_pool import ProxyPool

# 创建增强采集器
crawler = EnhancedXHSCrawler(
    rate_limit_config=RateLimitConfig(
        max_requests_per_second=2.0,
        max_requests_per_minute=60,
        max_requests_per_hour=1000
    ),
    cache_dir='./cache',
    enable_proxy=False  # 暂不启用代理
)

# 采集数据
stats = await crawler.crawl_viral_notes(
    category='美妆',
    time_window='7d',
    limit=100,
    db=db_session
)
```

### 2. 启用代理池

```python
# 创建代理池
proxy_pool = ProxyPool()

# 添加代理
proxy_pool.add_proxies_from_list([
    {'ip': '127.0.0.1', 'port': 7890, 'protocol': 'http'},
    {'ip': '127.0.0.1', 'port': 7891, 'protocol': 'http'},
])

# 启动健康检查（后台任务）
import asyncio
asyncio.create_task(proxy_pool.start_health_check())

# 创建采集器（启用代理）
crawler = EnhancedXHSCrawler(
    enable_proxy=True,
    proxy_pool=proxy_pool
)
```

### 3. 监控和统计

```python
# 获取统计信息
stats = crawler.get_stats()

print(f"缓存命中率: {stats['cache']['hit_rate']:.2%}")
print(f"当前速率: {stats['rate_limiter']['current_rate']:.2f} req/s")
print(f"成功率: {stats['rate_limiter']['success_rate']:.2%}")

# 定期清理
await crawler.cleanup()
```

## API 集成

### 更新 FastAPI 端点

```python
# backend/app/api.py

from app.crawlers.xhs_crawler import EnhancedXHSCrawler

# 全局采集器实例
enhanced_crawler = EnhancedXHSCrawler(
    cache_dir='./cache',
    enable_proxy=False
)

@app.post("/api/v1/crawl/viral")
async def crawl_viral_content(
    request: CrawlRequest,
    db: Session = Depends(get_db)
):
    """采集爆款内容（增强版）"""
    try:
        stats = await enhanced_crawler.crawl_viral_notes(
            category=request.category,
            time_window=request.time_window,
            limit=request.limit,
            db=db,
            force_refresh=request.force_refresh
        )

        return {
            'code': 200,
            'message': '采集成功',
            'data': stats
        }

    except Exception as e:
        logger.error(f"采集失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/crawl/stats")
async def get_crawler_stats():
    """获取采集器统计信息"""
    stats = enhanced_crawler.get_stats()
    return {
        'code': 200,
        'data': stats
    }
```

## Celery 任务集成

### 更新 Celery 任务

```python
# backend/app/tasks/tasks.py

from app.crawlers.xhs_crawler import EnhancedXHSCrawler

# 创建全局采集器
enhanced_crawler = EnhancedXHSCrawler()

@celery_app.task(name='app.tasks.crawl_viral_notes_enhanced')
def crawl_viral_notes_enhanced_task(
    category: str,
    time_window: str = '7d',
    limit: int = 100,
    force_refresh: bool = False
):
    """采集爆款笔记（增强版）"""
    db = next(get_db())

    try:
        # 使用增强采集器
        stats = asyncio.run(
            enhanced_crawler.crawl_viral_notes(
                category=category,
                time_window=time_window,
                limit=limit,
                db=db,
                force_refresh=force_refresh
            )
        )

        # WebSocket 推送结果
        asyncio.run(
            push_crawl_progress(
                task_id=crawl_viral_notes_enhanced_task.request.id,
                progress=100,
                message='采集完成',
                stats=stats
            )
        )

        return stats

    except Exception as e:
        logger.error(f"采集任务失败: {e}")
        raise

    finally:
        db.close()
```

## 配置文件

### 环境变量

```bash
# .env

# 速率限制
RATE_LIMIT_PER_SECOND=2.0
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_BURST_SIZE=5
RATE_LIMIT_COOLDOWN=60

# 缓存
CACHE_DIR=./cache
CACHE_MEMORY_SIZE=1000
CACHE_DEFAULT_TTL=86400

# 代理
ENABLE_PROXY=false
PROXY_CHECK_INTERVAL=300
PROXY_MAX_FAIL_COUNT=5
```

### 配置加载

```python
# backend/app/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 速率限制
    rate_limit_per_second: float = 2.0
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    rate_limit_burst_size: int = 5
    rate_limit_cooldown: int = 60

    # 缓存
    cache_dir: str = './cache'
    cache_memory_size: int = 1000
    cache_default_ttl: int = 86400

    # 代理
    enable_proxy: bool = False
    proxy_check_interval: int = 300
    proxy_max_fail_count: int = 5

    class Config:
        env_file = '.env'

settings = Settings()
```

## 测试

### 单元测试

```python
# tests/test_enhanced_crawler.py

import pytest
from app.crawlers.xhs_crawler import EnhancedXHSCrawler

@pytest.mark.asyncio
async def test_enhanced_crawler():
    """测试增强采集器"""
    crawler = EnhancedXHSCrawler(
        cache_dir='./test_cache',
        enable_proxy=False
    )

    # 测试采集
    stats = await crawler.crawl_viral_notes(
        category='美妆',
        time_window='7d',
        limit=10,
        db=None
    )

    assert stats['total'] > 0
    assert stats['success'] >= 0

    # 测试缓存
    stats2 = await crawler.crawl_viral_notes(
        category='美妆',
        time_window='7d',
        limit=10,
        db=None
    )

    assert stats2['cached'] > 0

    # 清理
    await crawler.cleanup()
```

### 性能测试

```python
# tests/test_performance.py

import time
import asyncio
from app.crawlers.xhs_crawler import EnhancedXHSCrawler

async def test_performance():
    """性能测试"""
    crawler = EnhancedXHSCrawler()

    start_time = time.time()

    # 并发采集
    tasks = [
        crawler.crawl_viral_notes('美妆', '7d', 50),
        crawler.crawl_viral_notes('穿搭', '7d', 50),
        crawler.crawl_viral_notes('美食', '7d', 50),
    ]

    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    print(f"总耗时: {elapsed:.2f}s")
    print(f"总采集: {sum(r['total'] for r in results)} 条")
    print(f"平均速率: {sum(r['total'] for r in results) / elapsed:.2f} notes/s")

    # 获取统计
    stats = crawler.get_stats()
    print(f"缓存命中率: {stats['cache']['hit_rate']:.2%}")
```

## 监控和告警

### Prometheus 指标

```python
# backend/app/monitoring.py

from prometheus_client import Counter, Histogram, Gauge

# 采集指标
crawl_requests_total = Counter(
    'crawl_requests_total',
    'Total crawl requests',
    ['category', 'status']
)

crawl_duration_seconds = Histogram(
    'crawl_duration_seconds',
    'Crawl duration in seconds',
    ['category']
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate'
)

rate_limiter_current_rate = Gauge(
    'rate_limiter_current_rate',
    'Current rate limit'
)

# 更新指标
def update_metrics(crawler):
    """更新 Prometheus 指标"""
    stats = crawler.get_stats()

    cache_hit_rate.set(stats['cache']['hit_rate'])
    rate_limiter_current_rate.set(stats['rate_limiter']['current_rate'])
```

### 定期任务

```python
# backend/app/tasks/monitoring.py

@celery_app.task(name='app.tasks.update_crawler_metrics')
def update_crawler_metrics():
    """更新采集器指标（每分钟）"""
    from app.monitoring import update_metrics
    from app.api import enhanced_crawler

    update_metrics(enhanced_crawler)

# 定时任务配置
celery_app.conf.beat_schedule = {
    'update-crawler-metrics': {
        'task': 'app.tasks.update_crawler_metrics',
        'schedule': 60.0,  # 每分钟
    },
}
```

## 故障排查

### 常见问题

**1. 速率限制过于严格**

```python
# 调整配置
rate_config = RateLimitConfig(
    max_requests_per_second=5.0,  # 提高速率
    cooldown_on_error=30  # 缩短冷却
)
```

**2. 缓存未命中**

```python
# 检查缓存统计
stats = crawler.get_stats()
print(f"缓存命中率: {stats['cache']['hit_rate']}")

# 强制刷新
stats = await crawler.crawl_viral_notes(
    category='美妆',
    force_refresh=True  # 忽略缓存
)
```

**3. 代理不可用**

```python
# 检查代理状态
proxy_stats = proxy_pool.get_stats()
print(f"可用代理: {proxy_stats['available']}/{proxy_stats['total']}")

# 手动检查
await proxy_pool.check_all_proxies()

# 移除不可用代理
proxy_pool.remove_unavailable()
```

## 最佳实践

1. **生产环境必须启用代理池**
2. **定期清理过期缓存**（每天）
3. **监控缓存命中率**（目标 > 30%）
4. **监控速率限制器状态**（避免频繁冷却）
5. **设置合理的 TTL**（根据数据更新频率）
6. **使用 force_refresh 谨慎**（仅在必要时）
7. **定期检查代理健康**（每 5-10 分钟）
8. **记录详细日志**（便于故障排查）

---

**最后更新**: 2026-02-12
