"""
GRPO (Group Relative Policy Optimization) Engine — PyTorch Implementation

Core idea:
1. Use relative rewards within a group instead of absolute rewards
2. Relative reward = (reward - mean) / std
3. Reduces reward variance, improves training stability
4. Uses neural network policy for action selection
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import logging
from datetime import datetime
import json
import os

import torch
import torch.nn as nn
import torch.optim as optim

from app.schemas.policy import Experience, Episode, PolicyState, GRPOUpdate
from app.ml.rl.networks import PolicyNetwork, StateEncoder, DEFAULT_STATE_DIM, DEFAULT_HIDDEN_DIM

logger = logging.getLogger(__name__)


@dataclass
class GRPOConfig:
    """Legacy GRPO config - use constructor params for GRPOEngine directly."""
    group_size: int = 8
    epsilon: float = 0.1
    learning_rate: float = 1e-4
    entropy_coef: float = 0.01


class GRPOEngine:
    """
    GRPO (Group Relative Policy Optimization) with PyTorch neural network policy.
    """

    def __init__(
        self,
        learning_rate: float = 1e-4,
        temperature: float = 1.0,
        clip_epsilon: float = 0.2,
        state_dim: int = DEFAULT_STATE_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
        action_dim: int = 64,
    ):
        self.learning_rate = learning_rate
        self.temperature = temperature
        self.clip_epsilon = clip_epsilon
        self.action_dim = action_dim

        # Neural network policy
        self.policy_net = PolicyNetwork(state_dim, hidden_dim, action_dim)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        self.state_encoder = StateEncoder(state_dim)

        # Action mapping: maps action dicts to indices and back
        self._action_to_idx: Dict[str, int] = {}
        self._idx_to_action: Dict[int, Dict[str, str]] = {}
        self._next_idx = 0

        # Legacy policy state for compatibility
        self.policy_state = PolicyState()

        logger.info(
            f"GRPO Engine initialized (PyTorch): lr={learning_rate}, "
            f"temp={temperature}, clip={clip_epsilon}, "
            f"state_dim={state_dim}, action_dim={action_dim}"
        )

    def _get_action_idx(self, action: Dict[str, str]) -> int:
        """Get or create index for an action."""
        key = json.dumps(action, sort_keys=True)
        if key not in self._action_to_idx:
            if self._next_idx >= self.action_dim:
                # Wrap around if we exceed action_dim
                idx = hash(key) % self.action_dim
            else:
                idx = self._next_idx
                self._next_idx += 1
            self._action_to_idx[key] = idx
            self._idx_to_action[idx] = action
        return self._action_to_idx[key]

    def _encode_state(self, exp: Experience) -> torch.Tensor:
        """Encode experience state into tensor."""
        state_dict = {
            "topic": exp.topic,
            "platform": exp.platform,
            "goal_metric": exp.goal_metric,
            "geo_keywords": exp.geo_keywords,
        }
        return self.state_encoder.encode(state_dict)

    def update_policy(self, episode: Episode) -> GRPOUpdate:
        """Update policy based on an episode using GRPO."""
        # 1. Calculate relative rewards
        relative_rewards = self._calculate_relative_rewards(episode.experiences)

        # 2. Encode states and get action indices
        states = torch.stack([self._encode_state(exp) for exp in episode.experiences])
        action_indices = [self._get_action_idx(exp.action) for exp in episode.experiences]
        action_tensor = torch.LongTensor(action_indices)
        reward_tensor = torch.FloatTensor(relative_rewards)

        # 3. Get old log probs (before update)
        self.policy_net.eval()
        with torch.no_grad():
            old_log_probs = self.policy_net(states)
            old_action_log_probs = old_log_probs.gather(1, action_tensor.unsqueeze(1)).squeeze(1)

        # 4. Policy gradient update with clipping (GRPO style)
        self.policy_net.train()
        self.optimizer.zero_grad()

        new_log_probs = self.policy_net(states)
        new_action_log_probs = new_log_probs.gather(1, action_tensor.unsqueeze(1)).squeeze(1)

        # Compute ratio
        ratio = torch.exp(new_action_log_probs - old_action_log_probs.detach())

        # Clipped surrogate objective
        surr1 = ratio * reward_tensor
        surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * reward_tensor
        loss = -torch.mean(torch.min(surr1, surr2))

        # Entropy bonus for exploration
        probs = torch.exp(new_log_probs)
        entropy = -torch.sum(probs * new_log_probs, dim=-1).mean()
        loss = loss - 0.01 * entropy

        loss.backward()
        nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=0.5)
        self.optimizer.step()

        # 5. Update legacy state
        update_magnitude = float(loss.item())
        self.policy_state.total_episodes += 1
        self.policy_state.total_updates += 1
        self.policy_state.last_updated = datetime.now().isoformat()

        # Build policy snapshots for the update record
        policy_before = {json.dumps(exp.action, sort_keys=True): 0.0 for exp in episode.experiences}
        policy_after = {}
        with torch.no_grad():
            for exp in episode.experiences:
                state = self._encode_state(exp).unsqueeze(0)
                probs = self.policy_net.get_action_probs(state)
                idx = self._get_action_idx(exp.action)
                key = json.dumps(exp.action, sort_keys=True)
                policy_after[key] = float(probs[0, idx].item())

        grpo_update = GRPOUpdate(
            episode_id=episode.episode_id,
            policy_before=policy_before,
            policy_after=policy_after,
            relative_rewards=relative_rewards,
            policy_gradients={},
            update_magnitude=abs(update_magnitude),
            learning_rate=self.learning_rate,
        )

        logger.info(
            f"Policy updated: episode={episode.episode_id}, "
            f"loss={update_magnitude:.4f}, "
            f"avg_relative_reward={np.mean(relative_rewards):.4f}"
        )

        return grpo_update

    def _calculate_relative_rewards(self, experiences: List[Experience]) -> List[float]:
        """Calculate group-relative rewards (normalized within group)."""
        rewards = [exp.reward for exp in experiences]
        mean_reward = np.mean(rewards)
        std_reward = max(np.std(rewards), 1e-8)
        return [(r - mean_reward) / std_reward for r in rewards]

    def sample_action(
        self,
        action_space: List[Dict[str, str]],
        state: Optional[Dict[str, Any]] = None,
        exploration: bool = False,
    ) -> Dict[str, str]:
        """Sample an action from the policy network."""
        if exploration or not self._action_to_idx:
            return action_space[np.random.randint(len(action_space))]

        # Encode state
        if state is None:
            state = {}
        state_tensor = self.state_encoder.encode(state).unsqueeze(0)

        # Forward pass
        self.policy_net.eval()
        with torch.no_grad():
            probs = self.policy_net.get_action_probs(state_tensor)[0]

        # Get probabilities for available actions
        action_probs = []
        for action in action_space:
            idx = self._get_action_idx(action)
            action_probs.append(float(probs[idx].item()))

        # Normalize and apply temperature
        action_probs = np.array(action_probs)
        action_probs = np.power(action_probs, 1.0 / self.temperature)
        action_probs = action_probs / action_probs.sum()

        idx = np.random.choice(len(action_space), p=action_probs)
        return action_space[idx]

    def get_top_actions(
        self,
        action_space: List[Dict[str, str]],
        state: Optional[Dict[str, Any]] = None,
        k: int = 5,
    ) -> List[Dict[str, str]]:
        """Get top-k actions by probability."""
        if not self._action_to_idx:
            indices = np.random.choice(len(action_space), size=min(k, len(action_space)), replace=False)
            return [action_space[i] for i in indices]

        if state is None:
            state = {}
        state_tensor = self.state_encoder.encode(state).unsqueeze(0)

        self.policy_net.eval()
        with torch.no_grad():
            probs = self.policy_net.get_action_probs(state_tensor)[0]

        action_probs = []
        for action in action_space:
            idx = self._get_action_idx(action)
            action_probs.append((action, float(probs[idx].item())))

        action_probs.sort(key=lambda x: x[1], reverse=True)
        return [a for a, _ in action_probs[:k]]

    def _action_to_key(self, action: Dict[str, str]) -> str:
        """Convert action to string key."""
        return json.dumps(action, sort_keys=True)

    def _key_to_action(self, key: str) -> Dict[str, str]:
        """Convert string key to action."""
        return json.loads(key)

    def save_policy(self) -> Dict[str, Any]:
        """Save policy state."""
        return self.policy_state.dict()

    def load_policy(self, policy_data: Dict[str, Any]):
        """Load policy state."""
        self.policy_state = PolicyState(**policy_data)

    def save_checkpoint(self, path: str):
        """Save full checkpoint using torch.save."""
        checkpoint = {
            "policy_net_state_dict": self.policy_net.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "action_to_idx": self._action_to_idx,
            "idx_to_action": {str(k): v for k, v in self._idx_to_action.items()},
            "next_idx": self._next_idx,
            "policy_state": self.policy_state.dict(),
            "hyperparameters": {
                "learning_rate": self.learning_rate,
                "temperature": self.temperature,
                "clip_epsilon": self.clip_epsilon,
            },
        }
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        torch.save(checkpoint, path)
        logger.info(f"Saved GRPO checkpoint to {path}")

    def load_checkpoint(self, path: str):
        """Load full checkpoint using torch.load."""
        checkpoint = torch.load(path, map_location="cpu")
        self.policy_net.load_state_dict(checkpoint["policy_net_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self._action_to_idx = checkpoint["action_to_idx"]
        self._idx_to_action = {int(k): v for k, v in checkpoint["idx_to_action"].items()}
        self._next_idx = checkpoint["next_idx"]
        self.policy_state = PolicyState(**checkpoint["policy_state"])
        logger.info(f"Loaded GRPO checkpoint from {path}")
