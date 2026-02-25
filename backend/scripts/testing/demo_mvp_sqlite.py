"""
SQLite version for quick MVP demo (no PostgreSQL required).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from app.db.models import Base, XHSNote, XHSMetrics, XHSCover, XHSAnalysis, Pattern, PatternSample
from app.training.data_collection.historical_collector_mvp import HistoricalDataCollectorMVP
from app.training.grpo_training_loop_mvp import GRPOTrainingLoopMVP


async def main():
    print("=" * 60)
    print("Growth Flywheel MVP - SQLite Demo")
    print("=" * 60)
    print()

    # Create SQLite database
    import time
    db_path = Path(f"demo_mvp_{int(time.time())}.db")

    DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

    print(f"Creating database: {db_path}")
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables created!")
    print()

    # Create session factory
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Step 1: Collect data
    print("=" * 60)
    print("STEP 1: Collecting Training Data")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        collector = HistoricalDataCollectorMVP(db)
        result = await collector.collect_bootstrap_data(
            target_count=100,
            category="美妆"
        )

        print()
        print("Collection Results:")
        print(f"  Collected: {result['collected']}")
        print(f"  Analyzed: {result['analyzed']}")
        print(f"  Patterns: {result['patterns_extracted']}")
        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")

    print()

    # Step 2: Run training
    print("=" * 60)
    print("STEP 2: Running GRPO Training")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        trainer = GRPOTrainingLoopMVP(db)
        result = await trainer.run_training_episode()

        if result["status"] == "success":
            print()
            print("Training Results:")
            print(f"  Episode ID: {result['episode_id']}")
            print(f"  Patterns trained: {result['patterns_trained']}")
            print(f"  Total samples: {result['total_samples']}")
            print(f"  Average reward: {result['avg_reward']:.3f}")
            print(f"  Checkpoint: {result['checkpoint_path']}")
        else:
            print(f"Training failed: {result.get('message')}")

    print()

    # Step 3: Verify results
    print("=" * 60)
    print("STEP 3: Verifying Results")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Get statistics
        note_count = await db.scalar(select(func.count(XHSNote.note_id)))
        pattern_count = await db.scalar(select(func.count(Pattern.id)))

        print()
        print(f"Database Statistics:")
        print(f"  Total notes: {note_count}")
        print(f"  Total patterns: {pattern_count}")
        print()

        # Get top patterns
        result = await db.execute(
            select(Pattern).order_by(Pattern.success_rate.desc()).limit(10)
        )
        patterns = result.scalars().all()

        print("Top 10 Patterns (by success rate):")
        print()
        for i, p in enumerate(patterns, 1):
            print(f"{i}. Pattern {p.id}")
            print(f"   Hook: {p.hook_template}")
            print(f"   Body: {p.body_structure}")
            print(f"   CTA: {p.cta_template}")
            print(f"   Success Rate: {p.success_rate:.3f}")
            print(f"   Thompson alpha: {p.thompson_alpha:.2f}")
            print(f"   Thompson beta: {p.thompson_beta:.2f}")
            print(f"   Sample Size: {p.sample_size}")
            print(f"   Avg Viral Score: {p.avg_viral_score:.3f}")
            print()

    print("=" * 60)
    print("MVP Demo Complete!")
    print("=" * 60)
    print()
    print(f"Database saved to: {db_path.absolute()}")
    print(f"Checkpoint saved to: checkpoints/")
    print()
    print("Next steps:")
    print("1. Fix PostgreSQL connection for production use")
    print("2. Replace mock data with real XHS crawler")
    print("3. Implement publishing pipeline")
    print("4. Add real-time metrics collection")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
