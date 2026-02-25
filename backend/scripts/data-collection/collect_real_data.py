"""
Collect real viral content from Xiaohongshu.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.training.data_collection.real_data_collector import RealDataCollector


async def main():
    print("=" * 60)
    print("Growth Flywheel - Real Data Collection")
    print("=" * 60)
    print()

    # Configuration
    USE_REAL_CRAWLER = False  # Set to True to use real XHS crawler
    CATEGORY = "美妆"
    TARGET_COUNT = 1000
    MIN_LIKES = 10000

    if not USE_REAL_CRAWLER:
        print("WARNING: Using mock data (USE_REAL_CRAWLER=False)")
        print("   Set USE_REAL_CRAWLER=True to crawl real XHS data")
        print()

    async with AsyncSessionLocal() as db:
        collector = RealDataCollector(db, use_real_crawler=USE_REAL_CRAWLER)

        result = await collector.collect_viral_notes(
            category=CATEGORY,
            target_count=TARGET_COUNT,
            min_likes=MIN_LIKES
        )

        print("\n" + "=" * 60)
        print("Collection Complete!")
        print("=" * 60)
        print(f"Collected: {result['collected']}")
        print(f"Analyzed: {result['analyzed']}")
        print(f"Patterns: {result['patterns_extracted']}")
        print(f"Errors: {len(result['errors'])}")

        if result['errors']:
            print("\nErrors:")
            for error in result['errors'][:10]:  # Show first 10
                print(f"   - {error}")


if __name__ == "__main__":
    asyncio.run(main())
