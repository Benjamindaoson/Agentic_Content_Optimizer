"""
PPO (Proximal Policy Optimization) Engine — PyTorch Implementation

Algorithm:
L^CLIP(theta) = E[min(r_t(theta)A_t, clip(r_t(theta), 1-eps, 1+eps)A_t)]
"""

from typing import List, Dict, Any, Optional
import numpy as np
import logging
from datetime import datetime
import json
import os

import torch
import torch.nn as nn
import torch.optim as optim

from app.schemas.policy import Experience, Episode, PolicyState
from app.ml.rl.networks import PolicyNetwork, ValueNetwork, StateEncoder, DEFAULT_STATE_DIM, DEFAULT_HIDDEN_DIM

logger = logging.getLogger(__name__)


class PPOEngine:
    """
    PPO (Proximal Policy Optimization) with PyTorch policy and value networks.

    Advantages over GRPO:
    1. More stable training (clipping mechanism)
    2. Value function for advantage estimation
    3. Entropy bonus for exploration
    4. Better sample efficiency
    """

    def __init__(
        self,
        learning_rate: float = 3e-4,
        clip_epsilon: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        state_dim: int = DEFAULT_STATE_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
        action_dim: int = 64,
    ):
        self.learning_rate = learning_rate
        self.clip_epsilon = clip_epsilon
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.action_dim = action_dim

        # Neural networks
        self.policy_net = PolicyNetwork(state_dim, hidden_dim, action_dim)
        self.value_net = ValueNetwork(state_dim, hidden_dim)
        self.policy_optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        self.value_optimizer = optim.Adam(self.value_net.parameters(), lr=learning_rate)
        self.state_encoder = StateEncoder(state_dim)

        # Action mapping
        self._action_to_idx: Dict[str, int] = {}
        self._idx_to_action: Dict[int, Dict[str, str]] = {}
        self._next_idx = 0

        # Legacy policy state
        self.policy_state = PolicyState()

        logger.info(
            f"PPO Engine initialized (PyTorch): lr={learning_rate}, "
            f"clip={clip_epsilon}, value_coef={value_coef}, "
            f"entropy_coef={entropy_coef}"
        )

    def _get_action_idx(self, action: Dict[str, str]) -> int:
        """Get or create index for an action."""
        key = self._action_to_key(action)
        if key not in self._action_to_idx:
            if self._next_idx >= self.action_dim:
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

    def update_policy(
        self,
        episode: Episode,
        num_epochs: int = 4,
        batch_size: int = 64,
    ) -> Dict[str, Any]:
        """Update policy using PPO with clipped surrogate objective."""
        experiences = episode.experiences
        if not experiences:
            return {"policy_loss": 0, "value_loss": 0, "entropy": 0}

        # Encode all states
        states = torch.stack([self._encode_state(exp) for exp in experiences])
        action_indices = torch.LongTensor([self._get_action_idx(exp.action) for exp in experiences])
        rewards = torch.FloatTensor([exp.reward for exp in experiences])

        # Compute advantages using GAE
        with torch.no_grad():
            values = self.value_net(states)
        advantages = self._compute_gae(rewards, values)
        value_targets = advantages + values.detach()

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Get old log probs
        with torch.no_grad():
            old_log_probs = self.policy_net(states)
            old_action_log_probs = old_log_probs.gather(1, action_indices.unsqueeze(1)).squeeze(1)

        # PPO update (multiple epochs)
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        n_updates = 0

        for epoch in range(num_epochs):
            indices = torch.randperm(len(experiences))

            for start in range(0, len(experiences), batch_size):
                end = min(start + batch_size, len(experiences))
                batch_idx = indices[start:end]

                batch_states = states[batch_idx]
                batch_actions = action_indices[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_value_targets = value_targets[batch_idx]
                batch_old_log_probs = old_action_log_probs[batch_idx]

                # Policy loss
                new_log_probs = self.policy_net(batch_states)
                new_action_log_probs = new_log_probs.gather(1, batch_actions.unsqueeze(1)).squeeze(1)

                ratio = torch.exp(new_action_log_probs - batch_old_log_probs.detach())
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * batch_advantages
                policy_loss = -torch.mean(torch.min(surr1, surr2))

                # Entropy bonus
                probs = torch.exp(new_log_probs)
                entropy = -torch.sum(probs * new_log_probs, dim=-1).mean()

                # Total policy loss
                actor_loss = policy_loss - self.entropy_coef * entropy

                self.policy_optimizer.zero_grad()
                actor_loss.backward()
                nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=0.5)
                self.policy_optimizer.step()

                # Value loss
                predicted_values = self.value_net(batch_states)
                value_loss = nn.functional.mse_loss(predicted_values, batch_value_targets.detach())

                self.value_optimizer.zero_grad()
                value_loss.backward()
                nn.utils.clip_grad_norm_(self.value_net.parameters(), max_norm=0.5)
                self.value_optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                n_updates += 1

        # Update stats
        self.policy_state.total_episodes += 1
        self.policy_state.total_updates += 1
        self.policy_state.last_updated = datetime.now().isoformat()

        n_updates = max(n_updates, 1)
        return {
            "policy_loss": total_policy_loss / n_updates,
            "value_loss": total_value_loss / n_updates,
            "entropy": total_entropy / n_updates,
            "num_epochs": num_epochs,
            "num_experiences": len(experiences),
        }

    def _compute_gae(self, rewards: torch.Tensor, values: torch.Tensor) -> torch.Tensor:
        """Compute Generalized Advantage Estimation."""
        n = len(rewards)
        advantages = torch.zeros(n)
        gae = 0.0

        for i in reversed(range(n)):
            next_value = values[i + 1] if i < n - 1 else 0.0
            delta = rewards[i] + self.gamma * next_value - values[i]
            gae = delta + self.gamma * self.gae_lambda * gae
            advantages[i] = gae

        return advantages

    def sample_action(
        self,
        action_space: List[Dict[str, str]],
        state: Optional[Dict[str, Any]] = None,
        exploration: bool = False,
    ) -> Dict[str, str]:
        """Sample an action from the policy network."""
        if exploration or not self._action_to_idx:
            return action_space[np.random.randint(len(action_space))]

        if state is None:
            state = {}
        state_tensor = self.state_encoder.encode(state).unsqueeze(0)

        self.policy_net.eval()
        with torch.no_grad():
            probs = self.policy_net.get_action_probs(state_tensor)[0]

        action_probs = []
        for action in action_space:
            idx = self._get_action_idx(action)
            action_probs.append(float(probs[idx].item()))

        action_probs = np.array(action_probs)
        action_probs = action_probs / action_probs.sum()
        chosen = np.random.choice(len(action_space), p=action_probs)
        return action_space[chosen]

    def _action_to_key(self, action: Dict[str, str]) -> str:
        """Convert action to key."""
        return json.dumps(action, sort_keys=True)

    def get_policy_state(self) -> PolicyState:
        """Get policy state."""
        return self.policy_state

    def save_checkpoint(self, path: str):
        """Save checkpoint using torch.save."""
        checkpoint = {
            "policy_net_state_dict": self.policy_net.state_dict(),
            "value_net_state_dict": self.value_net.state_dict(),
            "policy_optimizer_state_dict": self.policy_optimizer.state_dict(),
            "value_optimizer_state_dict": self.value_optimizer.state_dict(),
            "action_to_idx": self._action_to_idx,
            "idx_to_action": {str(k): v for k, v in self._idx_to_action.items()},
            "next_idx": self._next_idx,
            "policy_state": self.policy_state.dict(),
            "hyperparameters": {
                "learning_rate": self.learning_rate,
                "clip_epsilon": self.clip_epsilon,
                "value_coef": self.value_coef,
                "entropy_coef": self.entropy_coef,
                "gamma": self.gamma,
                "gae_lambda": self.gae_lambda,
            },
        }
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        torch.save(checkpoint, path)
        logger.info(f"Saved PPO checkpoint to {path}")

    def load_checkpoint(self, path: str):
        """Load checkpoint using torch.load."""
        checkpoint = torch.load(path, map_location="cpu")
        self.policy_net.load_state_dict(checkpoint["policy_net_state_dict"])
        self.value_net.load_state_dict(checkpoint["value_net_state_dict"])
        self.policy_optimizer.load_state_dict(checkpoint["policy_optimizer_state_dict"])
        self.value_optimizer.load_state_dict(checkpoint["value_optimizer_state_dict"])
        self._action_to_idx = checkpoint["action_to_idx"]
        self._idx_to_action = {int(k): v for k, v in checkpoint["idx_to_action"].items()}
        self._next_idx = checkpoint["next_idx"]
        self.policy_state = PolicyState(**checkpoint["policy_state"])
        logger.info(f"Loaded PPO checkpoint from {path}")
