"""
CLI script to run GRPO training.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.training.grpo_training_loop_mvp import GRPOTrainingLoopMVP


async def main():
    print("=" * 60)
    print("Growth Flywheel - GRPO Training")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        trainer = GRPOTrainingLoopMVP(db)

        result = await trainer.run_training_episode()

        if result["status"] != "success":
            print(f"\nTraining failed: {result.get('message')}")
            return

        print("\n" + "=" * 60)
        print("Training Complete!")
        print("=" * 60)
        print(f"Episode ID: {result['episode_id']}")
        print(f"Patterns trained: {result['patterns_trained']}")
        print(f"Total samples: {result['total_samples']}")
        print(f"Average reward: {result['avg_reward']:.3f}")
        print(f"Checkpoint: {result['checkpoint_path']}")


if __name__ == "__main__":
    asyncio.run(main())
