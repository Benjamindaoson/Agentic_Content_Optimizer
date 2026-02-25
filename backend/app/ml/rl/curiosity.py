"""
Curiosity-Driven Exploration Module — PyTorch ICM Implementation

Intrinsic Curiosity Module (ICM):
1. ForwardModel predicts next state encoding
2. InverseModel predicts action from (state, next_state)
3. Forward prediction error serves as intrinsic reward
4. Total reward = extrinsic + beta * intrinsic
"""

from typing import Dict, Any, List
import numpy as np
import logging

import torch
import torch.nn as nn
import torch.optim as optim

from app.ml.rl.networks import ForwardModel, InverseModel, StateEncoder, DEFAULT_STATE_DIM, DEFAULT_HIDDEN_DIM

logger = logging.getLogger(__name__)


class CuriosityModule:
    """
    ICM-based curiosity module with PyTorch neural networks.

    Intrinsic reward = ||predicted_next_state - actual_next_state||^2
    Total reward = extrinsic + beta * intrinsic
    """

    def __init__(
        self,
        intrinsic_reward_coef: float = 0.1,
        learning_rate: float = 1e-3,
        state_dim: int = DEFAULT_STATE_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
    ):
        self.intrinsic_reward_coef = intrinsic_reward_coef
        self.learning_rate = learning_rate
        self.state_dim = state_dim

        # Neural networks for ICM
        self.forward_model = ForwardModel(state_dim, state_dim, hidden_dim)
        self.inverse_model = InverseModel(state_dim, state_dim, hidden_dim)
        self.state_encoder = StateEncoder(state_dim)

        # Optimizers
        self.forward_optimizer = optim.Adam(self.forward_model.parameters(), lr=learning_rate)
        self.inverse_optimizer = optim.Adam(self.inverse_model.parameters(), lr=learning_rate)

        # Exploration statistics
        self.exploration_stats = {
            "total_intrinsic_reward": 0.0,
            "avg_prediction_error": 0.0,
            "num_predictions": 0,
        }

        logger.info(
            f"Curiosity Module initialized (PyTorch ICM): "
            f"intrinsic_coef={intrinsic_reward_coef}"
        )

    def _encode_state(self, state: Dict[str, Any]) -> torch.Tensor:
        """Encode state dict to tensor."""
        return self.state_encoder.encode(state)

    def _encode_action(self, action: Dict[str, str]) -> torch.Tensor:
        """Encode action dict to tensor."""
        return self.state_encoder.encode_action(action)

    def calculate_intrinsic_reward(
        self,
        state: Dict[str, Any],
        action: Dict[str, str],
        next_state: Dict[str, Any],
    ) -> float:
        """
        Calculate intrinsic reward (forward prediction error).
        """
        state_t = self._encode_state(state).unsqueeze(0)
        action_t = self._encode_action(action).unsqueeze(0)
        next_state_t = self._encode_state(next_state).unsqueeze(0)

        # Forward model prediction
        self.forward_model.eval()
        with torch.no_grad():
            predicted_next = self.forward_model(state_t, action_t)

        # Prediction error as intrinsic reward
        prediction_error = float(nn.functional.mse_loss(predicted_next, next_state_t).item())
        intrinsic_reward = prediction_error * self.intrinsic_reward_coef

        # Update models
        self.update(state_t, action_t, next_state_t)

        # Update stats
        self.exploration_stats["total_intrinsic_reward"] += intrinsic_reward
        self.exploration_stats["num_predictions"] += 1
        self.exploration_stats["avg_prediction_error"] = (
            self.exploration_stats["total_intrinsic_reward"]
            / self.exploration_stats["num_predictions"]
        )

        return intrinsic_reward

    def augment_reward(
        self,
        extrinsic_reward: float,
        state: Dict[str, Any],
        action: Dict[str, str],
        next_state: Dict[str, Any],
    ) -> float:
        """Augment reward: total = extrinsic + beta * intrinsic."""
        intrinsic_reward = self.calculate_intrinsic_reward(state, action, next_state)
        total_reward = extrinsic_reward + intrinsic_reward
        return total_reward

    def update(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        next_state: torch.Tensor,
    ):
        """Train both forward and inverse models on experience."""
        # Forward model update
        self.forward_model.train()
        self.forward_optimizer.zero_grad()
        predicted_next = self.forward_model(state, action)
        forward_loss = nn.functional.mse_loss(predicted_next, next_state.detach())
        forward_loss.backward()
        self.forward_optimizer.step()

        # Inverse model update
        self.inverse_model.train()
        self.inverse_optimizer.zero_grad()
        predicted_action = self.inverse_model(state.detach(), next_state.detach())
        inverse_loss = nn.functional.mse_loss(predicted_action, action.detach())
        inverse_loss.backward()
        self.inverse_optimizer.step()

    def get_exploration_stats(self) -> Dict[str, Any]:
        """Get exploration statistics."""
        return self.exploration_stats.copy()

    def reset_stats(self):
        """Reset statistics."""
        self.exploration_stats = {
            "total_intrinsic_reward": 0.0,
            "avg_prediction_error": 0.0,
            "num_predictions": 0,
        }

    def get_most_novel_actions(
        self,
        state: Dict[str, Any],
        actions: List[Dict[str, str]],
        top_k: int = 3,
    ) -> List[Dict[str, str]]:
        """Get actions with highest predicted novelty (forward prediction error)."""
        state_t = self._encode_state(state).unsqueeze(0)
        novelty_scores = []

        self.forward_model.eval()
        with torch.no_grad():
            for action in actions:
                action_t = self._encode_action(action).unsqueeze(0)
                predicted_next = self.forward_model(state_t, action_t)
                # Use prediction magnitude as proxy for novelty
                novelty = float(torch.norm(predicted_next).item())
                novelty_scores.append((action, novelty))

        novelty_scores.sort(key=lambda x: x[1], reverse=True)
        return [action for action, _ in novelty_scores[:top_k]]
