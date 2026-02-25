"""
Simple training dashboard.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.db.models import XHSNote, Pattern, Generation
from sqlalchemy import select, func


async def main():
    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("Growth Flywheel Dashboard")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Data collection stats
        note_count = await db.scalar(select(func.count(XHSNote.id)))
        viral_count = await db.scalar(
            select(func.count(XHSNote.id)).where(XHSNote.is_viral == True)
        )

        print("Data Collection:")
        print(f"   Total notes: {note_count}")
        print(f"   Viral notes: {viral_count}")
        if note_count > 0:
            print(f"   Viral rate: {viral_count/note_count*100:.1f}%")
        print()

        # Pattern stats
        pattern_count = await db.scalar(select(func.count(Pattern.id)))
        result = await db.execute(
            select(func.avg(Pattern.success_rate), func.avg(Pattern.sample_size))
        )
        avg_success, avg_samples = result.one()

        print("Patterns:")
        print(f"   Total patterns: {pattern_count}")
        if avg_success:
            print(f"   Avg success rate: {avg_success:.3f}")
        if avg_samples:
            print(f"   Avg sample size: {avg_samples:.1f}")
        print()

        # Generation stats
        gen_count = await db.scalar(select(func.count(Generation.id)))
        recent_gens = await db.scalar(
            select(func.count(Generation.id)).where(
                Generation.created_at >= datetime.now() - timedelta(days=7)
            )
        )

        print("Generation:")
        print(f"   Total generations: {gen_count}")
        print(f"   Last 7 days: {recent_gens}")
        print()

        # Top patterns
        result = await db.execute(
            select(Pattern).order_by(Pattern.success_rate.desc()).limit(5)
        )
        top_patterns = result.scalars().all()

        print("Top 5 Patterns:")
        for i, p in enumerate(top_patterns, 1):
            print(f"   {i}. {p.hook_template} | Success: {p.success_rate:.3f} | Samples: {p.sample_size}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
