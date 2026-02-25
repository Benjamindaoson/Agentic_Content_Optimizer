"""
MediaCrawler CLI 工具

快速使用 MediaCrawler 进行数据采集
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cmd_login(args):
    """登录命令"""
    logger.info(f"开始登录 {args.platform}...")

    config = MediaCrawlerConfig(
        platform=args.platform,
        headless=False  # 显示浏览器
    )

    if args.platform == "xhs":
        crawler = XiaohongshuCrawler(config)
    elif args.platform == "douyin":
        crawler = DouyinCrawler(config)
    elif args.platform == "bilibili":
        crawler = BilibiliCrawler(config)
    else:
        logger.error(f"不支持的平台: {args.platform}")
        return

    try:
        await crawler.start()
        await crawler.login()
        logger.info("✅ 登录成功！")
    except Exception as e:
        logger.error(f"❌ 登录失败: {e}")
    finally:
        await crawler.close()


async def cmd_search(args):
    """搜索命令"""
    logger.info(f"搜索关键词: {args.keyword}")

    config = MediaCrawlerConfig(
        platform=args.platform,
        headless=args.headless
    )

    crawler = XiaohongshuCrawler(config)

    try:
        await crawler.start()

        notes = await crawler.search_notes(
            keyword=args.keyword,
            page=args.page
        )

        logger.info(f"✅ 找到 {len(notes)} 条笔记")

        for i, note in enumerate(notes[:args.limit], 1):
            print(f"\n{i}. {note.get('title')}")
            print(f"   ID: {note.get('note_id')}")
            print(f"   作者: {note.get('author')}")
            print(f"   点赞: {note.get('likes')}")
            print(f"   URL: {note.get('url')}")

    except Exception as e:
        logger.error(f"❌ 搜索失败: {e}")
    finally:
        await crawler.close()


async def cmd_detail(args):
    """获取详情命令"""
    logger.info(f"获取笔记详情: {args.note_id}")

    config = MediaCrawlerConfig(
        platform=args.platform,
        headless=args.headless
    )

    crawler = XiaohongshuCrawler(config)

    try:
        await crawler.start()

        detail = await crawler.get_note_detail(args.note_id)

        if detail:
            print(f"\n标题: {detail.get('title')}")
            print(f"作者: {detail.get('author_name')}")
            print(f"内容: {detail.get('content')[:200]}...")
            print(f"点赞: {detail.get('likes')}")
            print(f"收藏: {detail.get('collects')}")
            print(f"评论: {detail.get('comments')}")
            print(f"标签: {', '.join(detail.get('tags', []))}")
        else:
            logger.warning("⚠️ 未能获取笔记详情")

    except Exception as e:
        logger.error(f"❌ 获取详情失败: {e}")
    finally:
        await crawler.close()


async def cmd_comments(args):
    """获取评论命令"""
    logger.info(f"获取笔记评论: {args.note_id}")

    config = MediaCrawlerConfig(
        platform=args.platform,
        headless=args.headless
    )

    crawler = XiaohongshuCrawler(config)

    try:
        await crawler.start()

        comments = await crawler.get_note_comments(
            args.note_id,
            max_count=args.limit
        )

        logger.info(f"✅ 获取到 {len(comments)} 条评论")

        for i, comment in enumerate(comments, 1):
            print(f"\n{i}. {comment.get('author')}")
            print(f"   内容: {comment.get('content')}")
            print(f"   点赞: {comment.get('likes')}")
            print(f"   时间: {comment.get('time')}")

    except Exception as e:
        logger.error(f"❌ 获取评论失败: {e}")
    finally:
        await crawler.close()


async def cmd_crawl(args):
    """采集命令（完整流程）"""
    logger.info(f"开始采集: 分类={args.category}, 数量={args.limit}")

    # 创建适配器
    adapter = SpiderXHSAdapter(
        use_mediacrawler=True,
        headless=args.headless
    )

    # 创建爬虫
    crawler = XHSCrawler(spider_adapter=adapter)

    try:
        # 获取数据库会话
        db = next(get_db())

        # 采集并保存
        stats = await crawler.crawl_and_save(
            category=args.category,
            time_window=args.time_window,
            limit=args.limit,
            db=db
        )

        print("\n采集统计:")
        print(f"  总数: {stats['total']}")
        print(f"  成功: {stats['success']}")
        print(f"  失败: {stats['failed']}")
        print(f"  封面下载: {stats['cover_downloaded']}")
        print(f"  封面失败: {stats['cover_failed']}")

    except Exception as e:
        logger.error(f"❌ 采集失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MediaCrawler CLI - 多平台爬虫工具"
    )

    # 全局参数
    parser.add_argument(
        "--platform",
        type=str,
        default="xhs",
        choices=["xhs", "douyin", "bilibili"],
        help="平台名称"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="无头模式（不显示浏览器）"
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # login 命令
    parser_login = subparsers.add_parser("login", help="登录平台")

    # search 命令
    parser_search = subparsers.add_parser("search", help="搜索笔记")
    parser_search.add_argument("keyword", type=str, help="搜索关键词")
    parser_search.add_argument("--page", type=int, default=1, help="页码")
    parser_search.add_argument("--limit", type=int, default=10, help="显示数量")

    # detail 命令
    parser_detail = subparsers.add_parser("detail", help="获取笔记详情")
    parser_detail.add_argument("note_id", type=str, help="笔记ID")

    # comments 命令
    parser_comments = subparsers.add_parser("comments", help="获取笔记评论")
    parser_comments.add_argument("note_id", type=str, help="笔记ID")
    parser_comments.add_argument("--limit", type=int, default=20, help="评论数量")

    # crawl 命令
    parser_crawl = subparsers.add_parser("crawl", help="采集并保存到数据库")
    parser_crawl.add_argument("category", type=str, help="分类/关键词")
    parser_crawl.add_argument("--limit", type=int, default=50, help="采集数量")
    parser_crawl.add_argument(
        "--time-window",
        type=str,
        default="7d",
        help="时间窗口（24h/7d/30d）"
    )

    # 解析参数
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    if args.command == "login":
        asyncio.run(cmd_login(args))
    elif args.command == "search":
        asyncio.run(cmd_search(args))
    elif args.command == "detail":
        asyncio.run(cmd_detail(args))
    elif args.command == "comments":
        asyncio.run(cmd_comments(args))
    elif args.command == "crawl":
        asyncio.run(cmd_crawl(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ 用户中断")
    except Exception as e:
        logger.error(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
