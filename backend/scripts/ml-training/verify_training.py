"""
Verify training results.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.db.models import Pattern
from sqlalchemy import select


async def main():
    print("=" * 60)
    print("Verifying Training Results")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Get all patterns
        result = await db.execute(select(Pattern).order_by(Pattern.success_rate.desc()))
        patterns = result.scalars().all()

        print(f"\nFound {len(patterns)} patterns\n")

        for i, pattern in enumerate(patterns[:10], 1):  # Top 10
            print(f"{i}. Pattern {pattern.id}")
            print(f"   Hook: {pattern.hook_template}")
            print(f"   Body: {pattern.body_structure}")
            print(f"   CTA: {pattern.cta_template}")
            print(f"   Success Rate: {pattern.success_rate:.3f}")
            print(f"   Thompson alpha: {pattern.thompson_alpha:.2f}")
            print(f"   Thompson beta: {pattern.thompson_beta:.2f}")
            print(f"   Sample Size: {pattern.sample_size}")
            print(f"   Avg Viral Score: {pattern.avg_viral_score:.3f}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
