"""
XHS-Downloader 集成使用示例

演示如何使用三级下载策略
"""

import asyncio
import logging
from pathlib import Path

from app.crawlers.xhs_crawler import (
    SpiderXHSAdapter,
    XHSDownloaderAdapter,
    XHSCrawler
)
from app.crawlers.xhs_downloader_adapter import XHSDownloaderConfig
from app.db import get_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_1_basic_download():
    """
    示例 1: 基础下载模式（推荐日常使用）

    特点：
    - 仅下载封面图
    - 速度快
    - 占用空间小
    - 适合大规模采集和数据分析
    """
    logger.info("=" * 60)
    logger.info("示例 1: 基础下载模式")
    logger.info("=" * 60)

    # 创建爬虫（基础模式）
    crawler = XHSCrawler(download_mode="basic")

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

        logger.info(f"\n✅ 基础下载完成:")
        logger.info(f"  总数: {stats['total']}")
        logger.info(f"  成功: {stats['success']}")
        logger.info(f"  封面下载: {stats['cover_downloaded']}")

    except Exception as e:
        logger.error(f"❌ 采集失败: {e}")


async def example_2_enhanced_download():
    """
    示例 2: 增强下载模式

    特点：
    - 下载所有图片
    - 速度适中
    - 适合素材收集
    - 适合图文作品分析
    """
    logger.info("=" * 60)
    logger.info("示例 2: 增强下载模式")
    logger.info("=" * 60)

    # 创建爬虫（增强模式）
    downloader = XHSDownloaderAdapter(
        download_mode="enhanced",
        use_hq_downloader=True  # 启用高质量下载器
    )

    crawler = XHSCrawler(
        downloader_adapter=downloader,
        download_mode="enhanced"
    )

    try:
        db = next(get_db())

        stats = await crawler.crawl_and_save(
            category="美妆",
            time_window="7d",
            limit=10,
            db=db
        )

        logger.info(f"\n✅ 增强下载完成:")
        logger.info(f"  总数: {stats['total']}")
        logger.info(f"  成功: {stats['success']}")
        logger.info(f"  封面下载: {stats['cover_downloaded']}")

    except Exception as e:
        logger.error(f"❌ 采集失败: {e}")


async def example_3_full_download():
    """
    示例 3: 完整下载模式

    特点：
    - 下载所有图片+视频
    - 速度慢
    - 占用空间大
    - 适合重要内容存档
    - 适合视频内容分析
    """
    logger.info("=" * 60)
    logger.info("示例 3: 完整下载模式")
    logger.info("=" * 60)

    # 创建爬虫（完整模式）
    downloader = XHSDownloaderAdapter(
        download_mode="full",
        use_hq_downloader=True
    )

    crawler = XHSCrawler(
        downloader_adapter=downloader,
        download_mode="full"
    )

    try:
        db = next(get_db())

        stats = await crawler.crawl_and_save(
            category="穿搭",
            time_window="7d",
            limit=5,  # 完整模式建议少量采集
            db=db
        )

        logger.info(f"\n✅ 完整下载完成:")
        logger.info(f"  总数: {stats['total']}")
        logger.info(f"  成功: {stats['success']}")
        logger.info(f"  封面下载: {stats['cover_downloaded']}")

    except Exception as e:
        logger.error(f"❌ 采集失败: {e}")


async def example_4_selective_download():
    """
    示例 4: 选择性下载（推荐）

    策略：
    1. 先用基础模式快速采集元数据
    2. 筛选出爆款内容
    3. 仅对爆款内容进行完整下载
    """
    logger.info("=" * 60)
    logger.info("示例 4: 选择性下载（智能策略）")
    logger.info("=" * 60)

    try:
        # 步骤 1: 快速采集元数据（基础模式）
        logger.info("\n📊 步骤 1: 快速采集元数据...")
        adapter = SpiderXHSAdapter(use_mediacrawler=True, headless=True)
        notes = await adapter.crawl_notes(
            category="护肤",
            time_window="7d",
            limit=50
        )

        logger.info(f"✅ 采集到 {len(notes)} 条笔记")

        # 步骤 2: 筛选爆款内容
        logger.info("\n🔍 步骤 2: 筛选爆款内容...")
        viral_notes = [
            note for note in notes
            if note.likes > 10000  # 点赞数 > 1万
        ]

        logger.info(f"✅ 筛选出 {len(viral_notes)} 条爆款笔记")

        # 步骤 3: 对爆款内容进行完整下载
        logger.info("\n⬇️ 步骤 3: 下载爆款内容...")

        downloader = XHSDownloaderAdapter(
            download_mode="full",
            use_hq_downloader=True
        )

        await downloader.hq_downloader.start()

        for i, note in enumerate(viral_notes[:5], 1):  # 限制下载数量
            logger.info(f"\n下载 {i}/{min(5, len(viral_notes))}: {note.title}")

            note_data = {
                'note_id': note.note_id,
                'title': note.title,
                'content': note.text,
                'cover_url': note.cover_url,
                'image_urls': note.image_urls,
                'author_name': note.author_name,
                'publish_time': note.publish_time,
                'likes': note.likes
            }

            stats = await downloader.hq_downloader.download_note(
                note_data,
                download_mode="full"
            )

            if stats.get('success'):
                logger.info(f"  ✅ 下载成功: 图片={stats['images']}, 视频={stats['videos']}")
            else:
                logger.warning(f"  ⚠️ 下载失败: {stats.get('error')}")

            # 速率限制
            await asyncio.sleep(2)

        await downloader.hq_downloader.close()

        logger.info("\n✅ 选择性下载完成！")

    except Exception as e:
        logger.error(f"❌ 选择性下载失败: {e}")


async def example_5_custom_config():
    """
    示例 5: 自定义配置

    演示如何自定义下载器配置
    """
    logger.info("=" * 60)
    logger.info("示例 5: 自定义配置")
    logger.info("=" * 60)

    # 自定义配置
    config = XHSDownloaderConfig(
        work_path="./data",
        folder_name="MyDownloads",
        name_format="发布时间 作者昵称 作品标题",
        image_format="PNG",  # 使用 PNG 格式
        folder_mode=True,  # 每个作品单独文件夹
        author_archive=True,  # 按作者归档
        write_mtime=True,  # 修改文件时间为发布时间
        download_record=True,  # 记录下载历史
        timeout=15,
        max_retry=5
    )

    # 创建下载器
    from app.crawlers.xhs_downloader_adapter import XHSDownloaderAdapter as XHSDownloaderHQ

    downloader = XHSDownloaderHQ(config)

    try:
        await downloader.start()

        # 模拟笔记数据
        note_data = {
            'note_id': 'test_001',
            'title': '测试笔记',
            'content': '这是一条测试笔记',
            'cover_url': 'https://example.com/cover.jpg',
            'image_urls': [
                'https://example.com/img1.jpg',
                'https://example.com/img2.jpg'
            ],
            'author_name': '测试作者',
            'author_id': 'author_001',
            'publish_time': '2026-02-12',
            'likes': 1000
        }

        stats = await downloader.download_note(note_data, download_mode="enhanced")

        logger.info(f"\n✅ 自定义配置下载完成:")
        logger.info(f"  成功: {stats.get('success')}")
        logger.info(f"  图片: {stats.get('images')}")
        logger.info(f"  文件: {stats.get('files')}")

        await downloader.close()

    except Exception as e:
        logger.error(f"❌ 自定义配置下载失败: {e}")


async def example_6_performance_comparison():
    """
    示例 6: 性能对比

    对比三种下载模式的性能
    """
    logger.info("=" * 60)
    logger.info("示例 6: 性能对比")
    logger.info("=" * 60)

    import time

    modes = ["basic", "enhanced", "full"]
    results = {}

    for mode in modes:
        logger.info(f"\n测试 {mode} 模式...")

        crawler = XHSCrawler(
            downloader_adapter=XHSDownloaderAdapter(
                download_mode=mode,
                use_hq_downloader=(mode != "basic")
            ),
            download_mode=mode
        )

        try:
            db = next(get_db())

            start_time = time.time()

            stats = await crawler.crawl_and_save(
                category="测试",
                time_window="7d",
                limit=5,
                db=db
            )

            elapsed_time = time.time() - start_time

            results[mode] = {
                'time': elapsed_time,
                'success': stats['success'],
                'downloaded': stats['cover_downloaded']
            }

            logger.info(f"  ✅ {mode} 模式完成: {elapsed_time:.2f}秒")

        except Exception as e:
            logger.error(f"  ❌ {mode} 模式失败: {e}")
            results[mode] = {'error': str(e)}

    # 输出对比结果
    logger.info("\n" + "=" * 60)
    logger.info("性能对比结果:")
    logger.info("=" * 60)

    for mode, result in results.items():
        if 'error' not in result:
            logger.info(f"\n{mode.upper()} 模式:")
            logger.info(f"  耗时: {result['time']:.2f}秒")
            logger.info(f"  成功: {result['success']}条")
            logger.info(f"  下载: {result['downloaded']}个文件")
        else:
            logger.info(f"\n{mode.upper()} 模式: 失败 - {result['error']}")


async def main():
    """主函数"""
    logger.info("XHS-Downloader 集成使用示例")
    logger.info("=" * 60)

    examples = {
        "1": ("基础下载模式（推荐日常使用）", example_1_basic_download),
        "2": ("增强下载模式（素材收集）", example_2_enhanced_download),
        "3": ("完整下载模式（重要内容）", example_3_full_download),
        "4": ("选择性下载（智能策略）⭐", example_4_selective_download),
        "5": ("自定义配置", example_5_custom_config),
        "6": ("性能对比", example_6_performance_comparison),
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
    asyncio.run(main())
