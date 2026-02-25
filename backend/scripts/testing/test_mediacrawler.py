"""
MediaCrawler 快速测试脚本

用于验证 MediaCrawler 集成是否正常工作
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.crawlers.mediacrawler_adapter import (
    MediaCrawlerConfig,
    XiaohongshuCrawler
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_functionality():
    """测试基础功能"""
    logger.info("=" * 60)
    logger.info("MediaCrawler 集成测试")
    logger.info("=" * 60)

    # 创建配置
    config = MediaCrawlerConfig(
        platform="xhs",
        headless=False,  # 显示浏览器，方便观察
        cookies_dir="./data/cookies"
    )

    # 创建爬虫
    crawler = XiaohongshuCrawler(config)

    try:
        logger.info("\n1️⃣ 启动浏览器...")
        await crawler.start()
        logger.info("✅ 浏览器启动成功")

        # 检查是否有保存的登录态
        cookies_file = Path(config.cookies_dir) / "xhs_cookies.json"
        if not cookies_file.exists():
            logger.info("\n2️⃣ 首次使用，需要登录...")
            logger.info("📱 请使用小红书 APP 扫描二维码登录")
            await crawler.login()
            logger.info("✅ 登录成功，登录态已保存")
        else:
            logger.info("\n2️⃣ 检测到已保存的登录态，跳过登录")

        logger.info("\n3️⃣ 测试搜索功能...")
        notes = await crawler.search_notes(
            keyword="测试",
            page=1,
            sort_type="general"
        )

        if notes and len(notes) > 0:
            logger.info(f"✅ 搜索成功，找到 {len(notes)} 条笔记")

            # 显示第一条笔记
            first_note = notes[0]
            logger.info("\n第一条笔记信息:")
            logger.info(f"  ID: {first_note.get('note_id')}")
            logger.info(f"  标题: {first_note.get('title')}")
            logger.info(f"  作者: {first_note.get('author')}")
            logger.info(f"  点赞: {first_note.get('likes')}")
            logger.info(f"  URL: {first_note.get('url')}")

            # 测试获取详情
            if first_note.get('note_id'):
                logger.info("\n4️⃣ 测试获取笔记详情...")
                detail = await crawler.get_note_detail(first_note['note_id'])

                if detail:
                    logger.info("✅ 获取详情成功")
                    logger.info(f"  标题: {detail.get('title')}")
                    logger.info(f"  内容长度: {len(detail.get('content', ''))}")
                    logger.info(f"  点赞: {detail.get('likes')}")
                    logger.info(f"  收藏: {detail.get('collects')}")
                    logger.info(f"  评论: {detail.get('comments')}")
                else:
                    logger.warning("⚠️ 未能获取笔记详情")

                # 测试获取评论
                logger.info("\n5️⃣ 测试获取评论...")
                comments = await crawler.get_note_comments(
                    first_note['note_id'],
                    max_count=5
                )

                if comments and len(comments) > 0:
                    logger.info(f"✅ 获取评论成功，共 {len(comments)} 条")
                    for i, comment in enumerate(comments[:3], 1):
                        logger.info(f"\n  评论 {i}:")
                        logger.info(f"    作者: {comment.get('author')}")
                        logger.info(f"    内容: {comment.get('content')[:50]}...")
                else:
                    logger.info("ℹ️ 该笔记暂无评论")

        else:
            logger.warning("⚠️ 搜索未返回结果，可能需要调整选择器")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        logger.info("\n6️⃣ 关闭浏览器...")
        await crawler.close()
        logger.info("✅ 浏览器已关闭")


async def test_adapter_integration():
    """测试适配器集成"""
    logger.info("\n" + "=" * 60)
    logger.info("测试适配器集成")
    logger.info("=" * 60)

    from app.crawlers.xhs_crawler import SpiderXHSAdapter

    try:
        # 创建适配器（使用 MediaCrawler）
        logger.info("\n1️⃣ 创建适配器...")
        adapter = SpiderXHSAdapter(
            use_mediacrawler=True,
            headless=False
        )
        logger.info("✅ 适配器创建成功")

        # 采集笔记
        logger.info("\n2️⃣ 开始采集笔记...")
        notes = await adapter.crawl_notes(
            category="测试",
            time_window="7d",
            limit=3
        )

        logger.info(f"✅ 采集完成，共 {len(notes)} 条笔记")

        # 显示笔记信息
        for i, note in enumerate(notes, 1):
            logger.info(f"\n笔记 {i}:")
            logger.info(f"  ID: {note.note_id}")
            logger.info(f"  标题: {note.title}")
            logger.info(f"  内容: {note.text[:100]}...")
            logger.info(f"  点赞: {note.likes}")
            logger.info(f"  评论: {note.comments}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 适配器集成测试完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n❌ 适配器测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MediaCrawler 集成测试")
    print("=" * 60)
    print("\n请选择测试类型:")
    print("  1. 基础功能测试（推荐）")
    print("  2. 适配器集成测试")
    print("  3. 运行所有测试")

    choice = input("\n输入选项 (1-3): ").strip()

    if choice == "1":
        await test_basic_functionality()
    elif choice == "2":
        await test_adapter_integration()
    elif choice == "3":
        await test_basic_functionality()
        await test_adapter_integration()
    else:
        logger.error("无效的选项")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ 用户中断测试")
    except Exception as e:
        logger.error(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
