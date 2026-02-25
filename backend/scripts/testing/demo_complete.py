"""
Fully working MVP demo with correct field names.
"""

import asyncio
import sys
import uuid
import random
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from app.db.models import Base, XHSNote, XHSMetrics, XHSCover, XHSAnalysis, Pattern, PatternSample
import numpy as np


async def main():
    print("=" * 60)
    print("Growth Flywheel MVP - Complete Demo")
    print("=" * 60)
    print()

    # Create SQLite database
    import time
    db_path = Path(f"mvp_demo_{int(time.time())}.db")

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
    print("STEP 1: Collecting Training Data (100 notes)")
    print("=" * 60)

    hook_types = ["question", "story", "shock", "benefit", "curiosity"]
    body_types = ["list", "tutorial", "comparison", "story", "tips"]
    cta_types = ["like", "collect", "follow", "comment", "share"]

    collected = 0
    patterns_created = {}

    async with AsyncSessionLocal() as db:
        for i in range(100):
            note_id = f"mock_{uuid.uuid4().hex[:12]}"
            hook_type = random.choice(hook_types)
            body_type = random.choice(body_types)
            cta_type = random.choice(cta_types)

            # Create note
            note = XHSNote(
                note_id=note_id,
                title=f"Mock Note {i+1}",
                text=f"Mock content with {hook_type} hook, {body_type} body, {cta_type} CTA.",
                cover_url=f"https://example.com/cover_{note_id}.jpg",
                image_urls=[f"https://example.com/img_{note_id}_1.jpg"],
                author_id=f"author_{random.randint(1, 100)}",
                publish_time=datetime.now() - timedelta(days=random.randint(1, 90)),
                category="美妆",
                tags=["美妆", hook_type, body_type],
                is_viral=True,
                analysis_status="completed"
            )
            db.add(note)

            # Create metrics
            views = random.randint(50000, 500000)
            likes = int(views * random.uniform(0.05, 0.15))
            comments = int(views * random.uniform(0.01, 0.05))
            collects = int(views * random.uniform(0.03, 0.10))

            metrics = XHSMetrics(
                note_id=note_id,
                views=views,
                likes=likes,
                comments=comments,
                collects=collects,
                shares=int(views * random.uniform(0.005, 0.02)),
                follows=random.randint(10, 100),
                engagement_rate=(likes + comments + collects) / views if views > 0 else 0,
                viral_score=min(1.0, ((likes + comments + collects) / views) * 5)
            )
            db.add(metrics)

            # Create cover
            cover = XHSCover(
                note_id=note_id,
                download_status="completed",
                layout="center",
                dominant_color="#FF6B6B"
            )
            db.add(cover)

            # Create analysis (using JSON fields)
            analysis = XHSAnalysis(
                note_id=note_id,
                structure={"hook": hook_type, "body": body_type, "cta": cta_type},
                emotion={"primary": "positive", "intensity": 0.8},
                topics={"main": "美妆", "keywords": [hook_type, body_type]},
                visual={"layout": "center", "color": "#FF6B6B"},
                timing={"publish_hour": 10},
                audience={"age_range": "18-35"}
            )
            db.add(analysis)

            # Create or update pattern
            pattern_key = f"{hook_type}_{body_type}_{cta_type}"
            if pattern_key not in patterns_created:
                pattern_id = f"pattern_{uuid.uuid4().hex[:8]}"
                pattern = Pattern(
                    pattern_id=pattern_id,
                    category="美妆",
                    name=f"{hook_type}-{body_type}-{cta_type}",
                    hook_template=hook_type,
                    body_structure={"type": body_type},
                    cta_template=cta_type,
                    keywords=[hook_type, body_type],
                    emotion_curve=[0.5, 0.7, 0.9],
                    cover_layout="center",
                    dominant_color="#FF6B6B",
                    visual_elements=["text", "product"],
                    success_rate=1.0,
                    sample_size=1,
                    avg_viral_score=metrics.viral_score,
                    avg_views=float(views),
                    avg_engagement_rate=metrics.engagement_rate,
                    thompson_alpha=2.0,
                    thompson_beta=1.0,
                    version=1
                )
                db.add(pattern)
                patterns_created[pattern_key] = pattern_id
            else:
                pattern_id = patterns_created[pattern_key]

            # Create pattern sample
            sample = PatternSample(
                pattern_id=pattern_id,
                note_id=note_id,
                contribution_score=1.0
            )
            db.add(sample)

            collected += 1
            if (i + 1) % 20 == 0:
                print(f"  Collected {i+1}/100 notes...")

        await db.commit()

    print(f"\nCollection complete: {collected} notes, {len(patterns_created)} patterns")
    print()

    # Step 2: Run GRPO training
    print("=" * 60)
    print("STEP 2: Running GRPO Training")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Load patterns
        result = await db.execute(select(Pattern))
        patterns = result.scalars().all()

        print(f"Found {len(patterns)} patterns")

        # Calculate rewards for each pattern
        pattern_rewards = {}
        for pattern in patterns:
            # Get samples
            result = await db.execute(
                select(PatternSample.note_id).where(PatternSample.pattern_id == pattern.pattern_id)
            )
            note_ids = [row[0] for row in result.all()]

            # Get metrics
            rewards = []
            for note_id in note_ids:
                result = await db.execute(
                    select(XHSMetrics).where(XHSMetrics.note_id == note_id)
                )
                metrics = result.scalar_one_or_none()
                if metrics:
                    rewards.append(metrics.viral_score)

            if rewards:
                pattern_rewards[pattern.pattern_id] = rewards

        # Calculate relative rewards (GRPO)
        relative_rewards = {}
        for pattern_id, rewards in pattern_rewards.items():
            mean_reward = np.mean(rewards)
            std_reward = np.std(rewards) if len(rewards) > 1 else 1.0
            rel_rewards = [(r - mean_reward) / (std_reward + 1e-8) for r in rewards]
            relative_rewards[pattern_id] = rel_rewards

        # Update patterns
        patterns_updated = 0
        for pattern in patterns:
            if pattern.pattern_id in relative_rewards:
                rel_rewards = relative_rewards[pattern.pattern_id]
                successes = sum(1 for r in rel_rewards if r > 0)
                failures = len(rel_rewards) - successes

                pattern.thompson_alpha += successes
                pattern.thompson_beta += failures
                pattern.success_rate = pattern.thompson_alpha / (
                    pattern.thompson_alpha + pattern.thompson_beta
                )
                patterns_updated += 1

        await db.commit()

        print(f"Training complete: {patterns_updated} patterns updated")
        print()

    # Step 3: Verify results
    print("=" * 60)
    print("STEP 3: Results")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        note_count = await db.scalar(select(func.count(XHSNote.note_id)))
        pattern_count = await db.scalar(select(func.count(Pattern.pattern_id)))

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
            print(f"{i}. {p.name}")
            print(f"   Success Rate: {p.success_rate:.3f}")
            print(f"   Thompson alpha: {p.thompson_alpha:.2f}, beta: {p.thompson_beta:.2f}")
            print(f"   Sample Size: {p.sample_size}")
            print(f"   Avg Viral Score: {p.avg_viral_score:.3f}")
            print()

    print("=" * 60)
    print("MVP Demo Complete!")
    print("=" * 60)
    print()
    print(f"Database: {db_path.absolute()}")
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
