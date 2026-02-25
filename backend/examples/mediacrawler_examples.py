"""
MediaCrawler 使用示例

演示如何使用 MediaCrawler 采集多平台数据
"""

import asyncio
import logging
from pathlib import Path

from app.crawlers.mediacrawler_adapter import (
    MediaCrawlerConfig,
    XiaohongshuCrawler,
    DouyinCrawler,
    BilibiliCrawler
)
from app.crawlers.xhs_crawler import SpiderXHSAdapter, XHSCrawler
from app.db import get_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_1_xiaohongshu_search():
    """
    示例 1: 小红书关键词搜索

    功能：搜索指定关键词的笔记
    """
    logger.info("=" * 60)
    logger.info("示例 1: 小红书关键词搜索")
    logger.info("=" * 60)

    # 创建配置
    config = MediaCrawlerConfig(
        platform="xhs",
        headless=False,  # 显示浏览器，方便扫码登录
        cookies_dir="./data/cookies"
    )

    # 创建爬虫
    crawler = XiaohongshuCrawler(config)

    try:
        # 启动爬虫
        await crawler.start()

        # 首次使用需要登录（扫码）
        # await crawler.login()

        # 搜索笔记
        notes = await crawler.search_notes(
            keyword="护肤",
            page=1,
            sort_type="general"
        )

        logger.info(f"✅ 搜索到 {len(notes)} 条笔记")

        # 打印前 3 条
        for i, note in enumerate(notes[:3], 1):
            logger.info(f"\n笔记 {i}:")
            logger.info(f"  ID: {note.get('note_id')}")
            logger.info(f"  标题: {note.get('title')}")
            logger.info(f"  作者: {note.get('author')}")
            logger.info(f"  点赞: {note.get('likes')}")

    except Exception as e:
        logger.error(f"❌ 搜索失败: {e}")

    finally:
        await crawler.close()


async def example_2_xiaohongshu_detail():
    """
    示例 2: 获取小红书笔记详情

    功能：根据笔记 ID 获取详细信息
    """
    logger.info("=" * 60)
    logger.info("示例 2: 获取小红书笔记详情")
    logger.info("=" * 60)

    config = MediaCrawlerConfig(platform="xhs", headless=True)
    crawler = XiaohongshuCrawler(config)

    try:
        await crawler.start()

        # 替换为真实的笔记 ID
        note_id = "your_note_id_here"

        # 获取详情
        detail = await crawler.get_note_detail(note_id)

        if detail:
            logger.info(f"✅ 获取笔记详情成功")
            logger.info(f"  标题: {detail.get('title')}")
            logger.info(f"  内容: {detail.get('content')[:100]}...")
            logger.info(f"  点赞: {detail.get('likes')}")
            logger.info(f"  收藏: {detail.get('collects')}")
            logger.info(f"  评论: {detail.get('comments')}")
            logger.info(f"  标签: {detail.get('tags')}")
        else:
            logger.warning("⚠️ 未能获取笔记详情")

    except Exception as e:
        logger.error(f"❌ 获取详情失败: {e}")

    finally:
        await crawler.close()


async def example_3_xiaohongshu_comments():
    """
    示例 3: 获取小红书笔记评论

    功能：获取指定笔记的评论列表
    """
    logger.info("=" * 60)
    logger.info("示例 3: 获取小红书笔记评论")
    logger.info("=" * 60)

    config = MediaCrawlerConfig(platform="xhs", headless=True)
    crawler = XiaohongshuCrawler(config)

    try:
        await crawler.start()

        # 替换为真实的笔记 ID
        note_id = "your_note_id_here"

        # 获取评论
        comments = await crawler.get_note_comments(note_id, max_count=20)

        logger.info(f"✅ 获取到 {len(comments)} 条评论")

        # 打印前 5 条
        for i, comment in enumerate(comments[:5], 1):
            logger.info(f"\n评论 {i}:")
            logger.info(f"  作者: {comment.get('author')}")
            logger.info(f"  内容: {comment.get('content')}")
            logger.info(f"  点赞: {comment.get('likes')}")
            logger.info(f"  时间: {comment.get('time')}")

    except Exception as e:
        logger.error(f"❌ 获取评论失败: {e}")

    finally:
        await crawler.close()


async def example_4_integrated_crawler():
    """
    示例 4: 使用集成的爬虫系统

    功能：通过 SpiderXHSAdapter 使用 MediaCrawler
    """
    logger.info("=" * 60)
    logger.info("示例 4: 使用集成的爬虫系统")
    logger.info("=" * 60)

    # 创建适配器（启用 MediaCrawler）
    adapter = SpiderXHSAdapter(
        use_mediacrawler=True,
        headless=False  # 首次使用显示浏览器，方便登录
    )

    try:
        # 采集笔记
        notes = await adapter.crawl_notes(
            category="美妆",
            time_window="7d",
            limit=10
        )

        logger.info(f"✅ 采集到 {len(notes)} 条笔记")

        # 打印前 3 条
        for i, note in enumerate(notes[:3], 1):
            logger.info(f"\n笔记 {i}:")
            logger.info(f"  ID: {note.note_id}")
            logger.info(f"  标题: {note.title}")
            logger.info(f"  内容: {note.text[:100]}...")
            logger.info(f"  点赞: {note.likes}")
            logger.info(f"  评论: {note.comments}")

    except Exception as e:
        logger.error(f"❌ 采集失败: {e}")


async def example_5_save_to_database():
    """
    示例 5: 采集并保存到数据库

    功能：完整的采集流程，包括保存到数据库
    """
    logger.info("=" * 60)
    logger.info("示例 5: 采集并保存到数据库")
    logger.info("=" * 60)

    # 创建爬虫
    crawler = XHSCrawler(
        spider_adapter=SpiderXHSAdapter(use_mediacrawler=True, headless=True)
    )

    try:
        # 获取数据库会话
        db = next(get_db())

        # 采集并保存
        stats = await crawler.crawl_and_save(
            category="护肤",
            time_window="7d",
            limit=20,
            db=db
        )

        logger.info(f"✅ 采集完成:")
        logger.info(f"  总数: {stats['total']}")
        logger.info(f"  成功: {stats['success']}")
        logger.info(f"  失败: {stats['failed']}")
        logger.info(f"  封面下载: {stats['cover_downloaded']}")
        logger.info(f"  封面失败: {stats['cover_failed']}")

    except Exception as e:
        logger.error(f"❌ 采集失败: {e}")


async def example_6_multi_platform():
    """
    示例 6: 多平台采集

    功能：同时采集小红书、抖音、B站数据
    """
    logger.info("=" * 60)
    logger.info("示例 6: 多平台采集")
    logger.info("=" * 60)

    # 创建多个爬虫
    xhs_crawler = XiaohongshuCrawler(MediaCrawlerConfig(platform="xhs"))
    douyin_crawler = DouyinCrawler(MediaCrawlerConfig(platform="douyin"))
    bilibili_crawler = BilibiliCrawler(MediaCrawlerConfig(platform="bilibili"))

    try:
        # 并发启动
        await asyncio.gather(
            xhs_crawler.start(),
            douyin_crawler.start(),
            bilibili_crawler.start()
        )

        logger.info("✅ 所有平台爬虫已启动")

        # 这里可以添加具体的采集逻辑
        # ...

    except Exception as e:
        logger.error(f"❌ 多平台采集失败: {e}")

    finally:
        # 关闭所有爬虫
        await asyncio.gather(
            xhs_crawler.close(),
            douyin_crawler.close(),
            bilibili_crawler.close()
        )


async def main():
    """主函数"""
    logger.info("MediaCrawler 使用示例")
    logger.info("=" * 60)

    # 选择要运行的示例
    examples = {
        "1": ("小红书关键词搜索", example_1_xiaohongshu_search),
        "2": ("获取小红书笔记详情", example_2_xiaohongshu_detail),
        "3": ("获取小红书笔记评论", example_3_xiaohongshu_comments),
        "4": ("使用集成的爬虫系统", example_4_integrated_crawler),
        "5": ("采集并保存到数据库", example_5_save_to_database),
        "6": ("多平台采集", example_6_multi_platform),
    }

    print("\n请选择要运行的示例:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")

    choice = input("\n输入选项 (1-6): ").strip()

    if choice in examples:
        name, func = examples[choice]
        logger.info(f"\n运行示例: {name}\n")
        await func()
    else:
        logger.error("无效的选项")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
