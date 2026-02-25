# 🚀 Growth Flywheel 2.5 - Execution Guide

## 🎯 Execution Strategy

**Philosophy**: Start with the smallest possible closed loop, then iterate.

**MVP Goal**: Prove the feedback loop works with minimal features:
```
Collect 100 viral notes → Extract patterns → Run 1 training episode → Verify pattern updates
```

---

## 📋 Phase 0: Pre-flight Check (Day 1)

### Step 0.1: Verify System Can Run

**Check database**:
```bash
# Check if PostgreSQL is running
psql -U postgres -d growth_flywheel -c "SELECT COUNT(*) FROM xhs_note;"

# Check if tables exist
psql -U postgres -d growth_flywheel -c "\dt"
```

**Check services**:
```bash
# Check Redis
redis-cli ping

# Check Qdrant (if using)
curl http://localhost:6333/collections

# Check MinIO (if using)
curl http://localhost:9000/minio/health/live
```

**Check Python environment**:
```bash
cd backend
python -c "import fastapi, sqlalchemy, celery, langchain; print('All imports OK')"
```

**Expected Output**: All services running, all imports successful.

---

### Step 0.2: Run Database Migrations

```bash
cd backend
alembic upgrade head
```

**Expected Output**: All migrations applied successfully.

---

### Step 0.3: Verify Existing Data

```bash
# Check if any data exists
psql -U postgres -d growth_flywheel -c "
SELECT
    (SELECT COUNT(*) FROM xhs_note) as notes,
    (SELECT COUNT(*) FROM xhs_metrics) as metrics,
    (SELECT COUNT(*) FROM pattern) as patterns,
    (SELECT COUNT(*) FROM generation) as generations;
"
```

**Expected Output**: Counts for each table (may be 0 if fresh install).

---

## 📦 Phase 1: MVP Data Collection (Days 2-3)

### Step 1.1: Create Historical Data Collector

Create `backend/app/training/data_collection/historical_collector.py`:

```python
"""
MVP Historical Data Collector
Collects 100 viral notes for initial testing.
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import XHSNote, XHSMetrics, XHSCover, XHSAnalysis, Pattern, PatternSample
from app.crawlers.xhs_crawler import XHSCrawler
from app.services.analysis_service import AnalysisService


class HistoricalDataCollectorMVP:
    """
    MVP version: Collect 100 viral notes for testing.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.crawler = XHSCrawler()
        self.analysis_service = AnalysisService(db)

    async def collect_bootstrap_data(
        self,
        target_count: int = 100,
        category: str = "美妆",
        min_likes: int = 10000
    ) -> Dict[str, Any]:
        """
        Collect viral notes for bootstrapping.

        Args:
            target_count: Number of notes to collect
            category: Category to crawl
            min_likes: Minimum likes threshold

        Returns:
            {
                "collected": int,
                "analyzed": int,
                "patterns_extracted": int,
                "errors": List[str]
            }
        """
        print(f"🚀 Starting data collection: target={target_count}, category={category}")

        collected = 0
        analyzed = 0
        patterns_extracted = 0
        errors = []

        try:
            # Use existing crawler to get notes
            # This assumes XHSCrawler has a method to search by category
            notes_data = await self.crawler.search_notes(
                keyword=category,
                sort="hot",  # Sort by popularity
                limit=target_count * 2  # Get more to filter
            )

            for note_data in notes_data:
                try:
                    # Filter by likes
                    if note_data.get("likes", 0) < min_likes:
                        continue

                    # Check if already exists
                    existing = await self.db.execute(
                        select(XHSNote).where(XHSNote.note_id == note_data["note_id"])
                    )
                    if existing.scalar_one_or_none():
                        print(f"⏭️  Note {note_data['note_id']} already exists, skipping")
                        continue

                    # Create note
                    note = XHSNote(
                        note_id=note_data["note_id"],
                        title=note_data.get("title", ""),
                        text=note_data.get("text", ""),
                        cover_url=note_data.get("cover_url", ""),
                        image_urls=note_data.get("image_urls", []),
                        author_id=note_data.get("author_id", ""),
                        publish_time=note_data.get("publish_time"),
                        category=category,
                        tags=note_data.get("tags", []),
                        is_viral=True,  # We filtered for viral content
                        analysis_status="pending"
                    )
                    self.db.add(note)

                    # Create metrics
                    metrics = XHSMetrics(
                        note_id=note_data["note_id"],
                        views=note_data.get("views", 0),
                        likes=note_data.get("likes", 0),
                        comments=note_data.get("comments", 0),
                        collects=note_data.get("collects", 0),
                        shares=note_data.get("shares", 0),
                        follows=note_data.get("follows", 0)
                    )
                    # Calculate engagement rate
                    if metrics.views > 0:
                        metrics.engagement_rate = (
                            metrics.likes + metrics.comments + metrics.collects
                        ) / metrics.views
                    self.db.add(metrics)

                    # Create cover record (download later)
                    if note_data.get("cover_url"):
                        cover = XHSCover(
                            note_id=note_data["note_id"],
                            cover_url=note_data["cover_url"],
                            download_status="pending"
                        )
                        self.db.add(cover)

                    await self.db.commit()
                    collected += 1
                    print(f"✅ Collected note {collected}/{target_count}: {note_data['note_id']}")

                    # Run analysis
                    try:
                        analysis = await self.analysis_service.analyze_note(note_data["note_id"])
                        if analysis:
                            analyzed += 1
                            print(f"📊 Analyzed note: {note_data['note_id']}")

                            # Extract pattern
                            pattern = await self._extract_pattern(note, metrics, analysis)
                            if pattern:
                                patterns_extracted += 1
                                print(f"🧩 Extracted pattern: {pattern.id}")

                    except Exception as e:
                        errors.append(f"Analysis failed for {note_data['note_id']}: {str(e)}")
                        print(f"⚠️  Analysis error: {str(e)}")

                    if collected >= target_count:
                        break

                    # Rate limiting
                    await asyncio.sleep(2)

                except Exception as e:
                    errors.append(f"Failed to process note: {str(e)}")
                    print(f"❌ Error: {str(e)}")
                    continue

        except Exception as e:
            errors.append(f"Crawler error: {str(e)}")
            print(f"❌ Crawler error: {str(e)}")

        result = {
            "collected": collected,
            "analyzed": analyzed,
            "patterns_extracted": patterns_extracted,
            "errors": errors
        }

        print(f"\n📈 Collection complete:")
        print(f"   Collected: {collected}")
        print(f"   Analyzed: {analyzed}")
        print(f"   Patterns: {patterns_extracted}")
        print(f"   Errors: {len(errors)}")

        return result

    async def _extract_pattern(
        self,
        note: XHSNote,
        metrics: XHSMetrics,
        analysis: XHSAnalysis
    ) -> Pattern:
        """
        Extract reusable pattern from analyzed note.
        """
        # Check if similar pattern exists
        existing = await self.db.execute(
            select(Pattern).where(
                Pattern.hook_template == analysis.hook_type,
                Pattern.body_structure == analysis.body_structure,
                Pattern.cta_template == analysis.cta_type
            )
        )
        pattern = existing.scalar_one_or_none()

        if pattern:
            # Update existing pattern
            pattern.sample_size += 1
            pattern.avg_viral_score = (
                (pattern.avg_viral_score * (pattern.sample_size - 1) + metrics.viral_score)
                / pattern.sample_size
            )
            pattern.avg_engagement_rate = (
                (pattern.avg_engagement_rate * (pattern.sample_size - 1) + metrics.engagement_rate)
                / pattern.sample_size
            )
            # Update Thompson Sampling priors (assume success if viral)
            pattern.thompson_alpha += 1
            pattern.success_rate = pattern.thompson_alpha / (
                pattern.thompson_alpha + pattern.thompson_beta
            )
        else:
            # Create new pattern
            pattern = Pattern(
                hook_template=analysis.hook_type,
                body_structure=analysis.body_structure,
                cta_template=analysis.cta_type,
                keywords=analysis.keywords or [],
                emotion_curve=analysis.emotion_curve or [],
                cover_layout=analysis.cover_layout,
                dominant_color=analysis.dominant_color,
                visual_elements=analysis.visual_elements or [],
                success_rate=1.0,  # Initial success (it's viral)
                sample_size=1,
                avg_viral_score=metrics.viral_score,
                avg_views=metrics.views,
                avg_engagement_rate=metrics.engagement_rate,
                thompson_alpha=2.0,  # Prior: 1 success + 1 pseudo-count
                thompson_beta=1.0,   # Prior: 0 failures + 1 pseudo-count
                version=1
            )
            self.db.add(pattern)

        await self.db.commit()

        # Create pattern sample link
        sample = PatternSample(
            pattern_id=pattern.id,
            note_id=note.note_id,
            contribution_score=1.0  # Full contribution for now
        )
        self.db.add(sample)
        await self.db.commit()

        return pattern
```

---

### Step 1.2: Create CLI Script to Run Collection

Create `backend/scripts/collect_data.py`:

```python
"""
CLI script to collect historical data.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import AsyncSessionLocal
from app.training.data_collection.historical_collector import HistoricalDataCollectorMVP


async def main():
    print("=" * 60)
    print("🚀 Growth Flywheel - Historical Data Collection")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        collector = HistoricalDataCollectorMVP(db)

        result = await collector.collect_bootstrap_data(
            target_count=100,
            category="美妆",
            min_likes=10000
        )

        print("\n" + "=" * 60)
        print("✅ Collection Complete!")
        print("=" * 60)
        print(f"Collected: {result['collected']}")
        print(f"Analyzed: {result['analyzed']}")
        print(f"Patterns: {result['patterns_extracted']}")
        print(f"Errors: {len(result['errors'])}")

        if result['errors']:
            print("\n⚠️  Errors:")
            for error in result['errors'][:5]:  # Show first 5
                print(f"   - {error}")


if __name__ == "__main__":
    asyncio.run(main())
```

**Run it**:
```bash
cd backend
python scripts/collect_data.py
```

**Expected Output**: 100 notes collected, analyzed, and patterns extracted.

---

## 🧠 Phase 2: MVP Training Loop (Days 4-5)

### Step 2.1: Create Simplified GRPO Training Loop

Create `backend/app/training/grpo_training_loop_mvp.py`:

```python
"""
MVP GRPO Training Loop
Simplified version for testing.
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import numpy as np

from app.db.models import Pattern, XHSNote, XHSMetrics, XHSAnalysis


class GRPOTrainingLoopMVP:
    """
    MVP training loop: Train on collected historical data.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_training_episode(self) -> Dict[str, Any]:
        """
        Run one training episode on historical data.

        Steps:
        1. Load all patterns with their samples
        2. Group samples by pattern
        3. Calculate relative rewards within each group
        4. Update pattern success rates (Bayesian)
        5. Update Thompson Sampling priors
        6. Save checkpoint

        Returns:
            {
                "episode_id": str,
                "patterns_trained": int,
                "total_samples": int,
                "avg_reward": float,
                "checkpoint_path": str
            }
        """
        print("🧠 Starting GRPO training episode...")

        episode_id = str(uuid.uuid4())[:8]

        # 1. Load all patterns
        result = await self.db.execute(select(Pattern))
        patterns = result.scalars().all()

        if not patterns:
            return {"status": "no_patterns", "message": "No patterns found. Run data collection first."}

        print(f"📊 Found {len(patterns)} patterns")

        # 2. For each pattern, calculate performance
        pattern_rewards = {}
        total_samples = 0

        for pattern in patterns:
            # Get all notes using this pattern
            samples = await self._get_pattern_samples(pattern.id)

            if not samples:
                continue

            # Calculate rewards for each sample
            rewards = []
            for note_id in samples:
                metrics = await self._get_note_metrics(note_id)
                if metrics:
                    # Simple reward: viral_score
                    reward = metrics.viral_score if metrics.viral_score else 0.0
                    rewards.append(reward)

            if rewards:
                pattern_rewards[pattern.id] = rewards
                total_samples += len(rewards)
                print(f"   Pattern {pattern.id}: {len(rewards)} samples, avg reward: {np.mean(rewards):.3f}")

        if not pattern_rewards:
            return {"status": "no_samples", "message": "No samples found for patterns."}

        # 3. Calculate relative rewards (GRPO)
        # For each pattern group, normalize rewards
        relative_rewards = {}
        all_rewards = []

        for pattern_id, rewards in pattern_rewards.items():
            mean_reward = np.mean(rewards)
            std_reward = np.std(rewards) if len(rewards) > 1 else 1.0

            # Relative reward: (reward - mean) / std
            rel_rewards = [(r - mean_reward) / (std_reward + 1e-8) for r in rewards]
            relative_rewards[pattern_id] = rel_rewards
            all_rewards.extend(rel_rewards)

        avg_reward = np.mean(all_rewards)
        print(f"\n📈 Average relative reward: {avg_reward:.3f}")

        # 4. Update patterns (Bayesian update)
        patterns_updated = 0

        for pattern in patterns:
            if pattern.id not in relative_rewards:
                continue

            rel_rewards = relative_rewards[pattern.id]

            # Count successes (positive relative reward) and failures
            successes = sum(1 for r in rel_rewards if r > 0)
            failures = len(rel_rewards) - successes

            # Bayesian update: α = α + successes, β = β + failures
            old_alpha = pattern.thompson_alpha
            old_beta = pattern.thompson_beta

            pattern.thompson_alpha += successes
            pattern.thompson_beta += failures

            # Update success rate
            pattern.success_rate = pattern.thompson_alpha / (
                pattern.thompson_alpha + pattern.thompson_beta
            )

            print(f"   Pattern {pattern.id}:")
            print(f"      Successes: {successes}, Failures: {failures}")
            print(f"      α: {old_alpha:.2f} → {pattern.thompson_alpha:.2f}")
            print(f"      β: {old_beta:.2f} → {pattern.thompson_beta:.2f}")
            print(f"      Success rate: {pattern.success_rate:.3f}")

            patterns_updated += 1

        await self.db.commit()

        # 5. Save checkpoint
        checkpoint_path = await self._save_checkpoint(
            episode_id=episode_id,
            patterns=patterns,
            total_samples=total_samples,
            avg_reward=avg_reward
        )

        result = {
            "status": "success",
            "episode_id": episode_id,
            "patterns_trained": patterns_updated,
            "total_samples": total_samples,
            "avg_reward": float(avg_reward),
            "checkpoint_path": checkpoint_path
        }

        print(f"\n✅ Training episode complete!")
        print(f"   Episode ID: {episode_id}")
        print(f"   Patterns trained: {patterns_updated}")
        print(f"   Total samples: {total_samples}")
        print(f"   Checkpoint: {checkpoint_path}")

        return result

    async def _get_pattern_samples(self, pattern_id: str) -> List[str]:
        """Get all note IDs for a pattern."""
        from app.db.models import PatternSample

        result = await self.db.execute(
            select(PatternSample.note_id).where(PatternSample.pattern_id == pattern_id)
        )
        return [row[0] for row in result.all()]

    async def _get_note_metrics(self, note_id: str) -> XHSMetrics:
        """Get metrics for a note."""
        result = await self.db.execute(
            select(XHSMetrics).where(XHSMetrics.note_id == note_id)
        )
        return result.scalar_one_or_none()

    async def _save_checkpoint(
        self,
        episode_id: str,
        patterns: List[Pattern],
        total_samples: int,
        avg_reward: float
    ) -> str:
        """Save training checkpoint."""
        checkpoint_dir = Path("checkpoints") / episode_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Save patterns
        patterns_data = [
            {
                "id": p.id,
                "hook_template": p.hook_template,
                "body_structure": p.body_structure,
                "cta_template": p.cta_template,
                "success_rate": float(p.success_rate) if p.success_rate else 0.0,
                "thompson_alpha": float(p.thompson_alpha) if p.thompson_alpha else 1.0,
                "thompson_beta": float(p.thompson_beta) if p.thompson_beta else 1.0,
                "sample_size": p.sample_size
            }
            for p in patterns
        ]

        with open(checkpoint_dir / "patterns.json", "w", encoding="utf-8") as f:
            json.dump(patterns_data, f, indent=2, ensure_ascii=False)

        # Save metadata
        metadata = {
            "episode_id": episode_id,
            "timestamp": datetime.now().isoformat(),
            "patterns_count": len(patterns),
            "total_samples": total_samples,
            "avg_reward": float(avg_reward),
            "avg_success_rate": float(np.mean([p["success_rate"] for p in patterns_data]))
        }

        with open(checkpoint_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return str(checkpoint_dir)
```

---

### Step 2.2: Create CLI Script to Run Training

Create `backend/scripts/train_grpo.py`:

```python
"""
CLI script to run GRPO training.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import AsyncSessionLocal
from app.training.grpo_training_loop_mvp import GRPOTrainingLoopMVP


async def main():
    print("=" * 60)
    print("🧠 Growth Flywheel - GRPO Training")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        trainer = GRPOTrainingLoopMVP(db)

        result = await trainer.run_training_episode()

        if result["status"] != "success":
            print(f"\n❌ Training failed: {result.get('message')}")
            return

        print("\n" + "=" * 60)
        print("✅ Training Complete!")
        print("=" * 60)
        print(f"Episode ID: {result['episode_id']}")
        print(f"Patterns trained: {result['patterns_trained']}")
        print(f"Total samples: {result['total_samples']}")
        print(f"Average reward: {result['avg_reward']:.3f}")
        print(f"Checkpoint: {result['checkpoint_path']}")


if __name__ == "__main__":
    asyncio.run(main())
```

**Run it**:
```bash
cd backend
python scripts/train_grpo.py
```

**Expected Output**: Patterns updated with new Thompson Sampling priors, checkpoint saved.

---

## 🔍 Phase 3: Verification (Day 6)

### Step 3.1: Verify Pattern Updates

Create `backend/scripts/verify_training.py`:

```python
"""
Verify training results.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import AsyncSessionLocal
from app.db.models import Pattern
from sqlalchemy import select


async def main():
    print("=" * 60)
    print("🔍 Verifying Training Results")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Get all patterns
        result = await db.execute(select(Pattern).order_by(Pattern.success_rate.desc()))
        patterns = result.scalars().all()

        print(f"\n📊 Found {len(patterns)} patterns\n")

        for i, pattern in enumerate(patterns[:10], 1):  # Top 10
            print(f"{i}. Pattern {pattern.id}")
            print(f"   Hook: {pattern.hook_template}")
            print(f"   Body: {pattern.body_structure}")
            print(f"   CTA: {pattern.cta_template}")
            print(f"   Success Rate: {pattern.success_rate:.3f}")
            print(f"   Thompson α: {pattern.thompson_alpha:.2f}")
            print(f"   Thompson β: {pattern.thompson_beta:.2f}")
            print(f"   Sample Size: {pattern.sample_size}")
            print(f"   Avg Viral Score: {pattern.avg_viral_score:.3f}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
```

**Run it**:
```bash
cd backend
python scripts/verify_training.py
```

**Expected Output**: List of patterns sorted by success rate, showing updated Thompson Sampling priors.

---

### Step 3.2: Test Generation with Updated Patterns

```bash
# Use existing generation API
curl -X POST http://localhost:8000/api/v4/generation/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "春季护肤",
    "platform": "xiaohongshu",
    "category": "美妆"
  }'
```

**Expected Output**: Generated content using patterns with updated success rates (higher-performing patterns should be sampled more often).

---

## 📊 Phase 4: Monitoring (Day 7)

### Step 4.1: Create Simple Dashboard Script

Create `backend/scripts/dashboard.py`:

```python
"""
Simple training dashboard.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import AsyncSessionLocal
from app.db.models import XHSNote, Pattern, Generation
from sqlalchemy import select, func


async def main():
    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("📊 Growth Flywheel Dashboard")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Data collection stats
        note_count = await db.scalar(select(func.count(XHSNote.id)))
        viral_count = await db.scalar(
            select(func.count(XHSNote.id)).where(XHSNote.is_viral == True)
        )

        print("📦 Data Collection:")
        print(f"   Total notes: {note_count}")
        print(f"   Viral notes: {viral_count}")
        print(f"   Viral rate: {viral_count/note_count*100:.1f}%" if note_count > 0 else "   Viral rate: N/A")
        print()

        # Pattern stats
        pattern_count = await db.scalar(select(func.count(Pattern.id)))
        result = await db.execute(
            select(func.avg(Pattern.success_rate), func.avg(Pattern.sample_size))
        )
        avg_success, avg_samples = result.one()

        print("🧩 Patterns:")
        print(f"   Total patterns: {pattern_count}")
        print(f"   Avg success rate: {avg_success:.3f}" if avg_success else "   Avg success rate: N/A")
        print(f"   Avg sample size: {avg_samples:.1f}" if avg_samples else "   Avg sample size: N/A")
        print()

        # Generation stats
        gen_count = await db.scalar(select(func.count(Generation.id)))
        recent_gens = await db.scalar(
            select(func.count(Generation.id)).where(
                Generation.created_at >= datetime.now() - timedelta(days=7)
            )
        )

        print("✨ Generation:")
        print(f"   Total generations: {gen_count}")
        print(f"   Last 7 days: {recent_gens}")
        print()

        # Top patterns
        result = await db.execute(
            select(Pattern).order_by(Pattern.success_rate.desc()).limit(5)
        )
        top_patterns = result.scalars().all()

        print("🏆 Top 5 Patterns:")
        for i, p in enumerate(top_patterns, 1):
            print(f"   {i}. {p.hook_template} | Success: {p.success_rate:.3f} | Samples: {p.sample_size}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
```

**Run it**:
```bash
cd backend
python scripts/dashboard.py
```

---

## 🎯 Success Criteria for MVP

After completing all phases, you should have:

✅ **Data**: 100+ viral notes collected and analyzed
✅ **Patterns**: 10+ patterns extracted with Thompson Sampling priors
✅ **Training**: 1+ training episode completed successfully
✅ **Verification**: Pattern success rates updated based on performance
✅ **Generation**: New content generated using updated patterns
✅ **Monitoring**: Dashboard showing system stats

---

## 🚀 Next Steps After MVP

Once MVP is working:

1. **Scale Data Collection**:
   - Increase to 10,000+ notes
   - Add more categories
   - Implement scheduled crawling

2. **Add Real-Time Metrics**:
   - Implement publishing pipeline
   - Collect metrics from published content
   - Close the feedback loop

3. **Enhance Training**:
   - Add reward model training
   - Implement PPO as alternative
   - Add diversity bonuses

4. **Production Deployment**:
   - Dockerize services
   - Set up monitoring
   - Add CI/CD

---

## 🆘 Troubleshooting

### Issue: Crawler fails
**Solution**: Check if MediaCrawler is installed and configured. Use fallback Playwright crawler.

### Issue: No patterns extracted
**Solution**: Check if XHSAnalysis is running correctly. Verify analysis_service is working.

### Issue: Training fails with "no samples"
**Solution**: Ensure data collection completed successfully. Check PatternSample table has entries.

### Issue: Database connection errors
**Solution**: Verify PostgreSQL is running. Check connection string in .env file.

---

**Document Version**: 1.0
**Last Updated**: 2026-02-13
