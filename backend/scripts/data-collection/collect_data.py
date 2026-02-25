"""
CLI script to collect historical data.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.training.data_collection.historical_collector_mvp import HistoricalDataCollectorMVP


async def main():
    print("=" * 60)
    print("Growth Flywheel - Historical Data Collection")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        collector = HistoricalDataCollectorMVP(db)

        result = await collector.collect_bootstrap_data(
            target_count=100,
            category="美妆"
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
            for error in result['errors'][:5]:  # Show first 5
                print(f"   - {error}")


if __name__ == "__main__":
    asyncio.run(main())
