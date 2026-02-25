"""
MVP GRPO Training Loop
Simplified version for testing.
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import numpy as np

from app.db.models import Pattern, XHSNote, XHSMetrics, XHSAnalysis, PatternSample


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
        print("Starting GRPO training episode...")

        episode_id = str(uuid.uuid4())[:8]

        # 1. Load all patterns
        result = await self.db.execute(select(Pattern))
        patterns = result.scalars().all()

        if not patterns:
            return {"status": "no_patterns", "message": "No patterns found. Run data collection first."}

        print(f"Found {len(patterns)} patterns")

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
        print(f"\nAverage relative reward: {avg_reward:.3f}")

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
            print(f"      alpha: {old_alpha:.2f} -> {pattern.thompson_alpha:.2f}")
            print(f"      beta: {old_beta:.2f} -> {pattern.thompson_beta:.2f}")
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

        print(f"\nTraining episode complete!")
        print(f"   Episode ID: {episode_id}")
        print(f"   Patterns trained: {patterns_updated}")
        print(f"   Total samples: {total_samples}")
        print(f"   Checkpoint: {checkpoint_path}")

        return result

    async def _get_pattern_samples(self, pattern_id: str) -> List[str]:
        """Get all note IDs for a pattern."""
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
