"""
End-to-end production test.
Tests the complete workflow: collect → train → verify.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_complete_workflow():
    """Test complete workflow."""
    print("=" * 60)
    print("End-to-End Production Test")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Import after path setup
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.db.models import Base, XHSNote, Pattern
    from app.training.data_collection.real_data_collector import RealDataCollector
    from app.training.grpo_training_loop_mvp import GRPOTrainingLoopMVP
    from sqlalchemy import select, func

    # Create test database
    db_path = Path(f"e2e_test_{int(datetime.now().timestamp())}.db")
    DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

    print(f"Creating test database: {db_path}")
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    print("Database created")
    print()

    # Step 1: Data Collection
    print("=" * 60)
    print("STEP 1: Data Collection")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        collector = RealDataCollector(db, use_real_crawler=False)
        result = await collector.collect_viral_notes(
            category="美妆",
            target_count=50,  # Smaller for faster test
            min_likes=10000
        )

        print(f"Collected: {result['collected']}")
        print(f"Analyzed: {result['analyzed']}")
        print(f"Patterns: {result['patterns_extracted']}")
        print()

        if result['collected'] == 0:
            print("ERROR: No data collected")
            return False

    # Step 2: Training
    print("=" * 60)
    print("STEP 2: GRPO Training")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        trainer = GRPOTrainingLoopMVP(db)
        result = await trainer.run_training_episode()

        if result["status"] == "success":
            print(f"Episode ID: {result['episode_id']}")
            print(f"Patterns trained: {result['patterns_trained']}")
            print(f"Total samples: {result['total_samples']}")
            print(f"Average reward: {result['avg_reward']:.3f}")
            print()
        else:
            print(f"Training failed: {result.get('message')}")
            return False

    # Step 3: Verification
    print("=" * 60)
    print("STEP 3: Verification")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        note_count = await db.scalar(select(func.count(XHSNote.note_id)))
        pattern_count = await db.scalar(select(func.count(Pattern.pattern_id)))

        print(f"Total notes: {note_count}")
        print(f"Total patterns: {pattern_count}")
        print()

        # Get top patterns
        result = await db.execute(
            select(Pattern).order_by(Pattern.success_rate.desc()).limit(5)
        )
        patterns = result.scalars().all()

        print("Top 5 Patterns:")
        for i, p in enumerate(patterns, 1):
            print(f"{i}. {p.name}")
            print(f"   Success Rate: {p.success_rate:.3f}")
            print(f"   Thompson alpha: {p.thompson_alpha:.2f}, beta: {p.thompson_beta:.2f}")
            print(f"   Samples: {p.sample_size}")
            print()

    # Cleanup
    await engine.dispose()
    print(f"Test database saved: {db_path.absolute()}")
    print()

    print("=" * 60)
    print("End-to-End Test: PASSED")
    print("=" * 60)

    return True


async def test_celery_tasks():
    """Test Celery task definitions."""
    print("=" * 60)
    print("Celery Tasks Test")
    print("=" * 60)

    try:
        from app.tasks.training_tasks import (
            celery_app,
            collect_viral_notes_task,
            run_grpo_training_task,
            collect_online_metrics_task
        )

        print("Celery app: OK")
        print(f"Broker: {celery_app.conf.broker_url}")
        print()

        print("Registered tasks:")
        tasks = [t for t in celery_app.tasks.keys() if not t.startswith('celery.')]
        for task in tasks[:10]:
            print(f"  - {task}")
        print()

        print("Beat schedule:")
        for name, config in celery_app.conf.beat_schedule.items():
            print(f"  - {name}: {config['task']}")
        print()

        print("Celery Tasks Test: PASSED")
        return True

    except Exception as e:
        print(f"Celery Tasks Test: FAILED")
        print(f"Error: {str(e)}")
        return False


async def main():
    print("\n" + "=" * 60)
    print("Growth Flywheel 2.5 - Production Test Suite")
    print("=" * 60)
    print()

    results = {}

    # Test 1: Complete workflow
    print("\n[TEST 1/2] Complete Workflow Test")
    results['workflow'] = await test_complete_workflow()

    # Test 2: Celery tasks
    print("\n[TEST 2/2] Celery Tasks Test")
    results['celery'] = await test_celery_tasks()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, status in results.items():
        status_str = "PASS" if status else "FAIL"
        print(f"{test_name.title()}: {status_str}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nProduction System: READY")
        return 0
    else:
        print("\nProduction System: NEEDS ATTENTION")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
