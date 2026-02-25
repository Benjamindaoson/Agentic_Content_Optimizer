"""
RL Neural Networks Module

PyTorch neural networks for reinforcement learning:
- PolicyNetwork: MLP for discrete action probabilities
- ValueNetwork: MLP for state value estimation
- ForwardModel: Predict next state from (state, action) — for ICM
- InverseModel: Predict action from (state, next_state) — for ICM
- StateEncoder: Convert mixed-type state dict to fixed-size tensor
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# Default dimensions
DEFAULT_STATE_DIM = 64
DEFAULT_HIDDEN_DIM = 128


class StateEncoder:
    """Convert mixed-type state dict to fixed-size tensor."""

    def __init__(self, state_dim: int = DEFAULT_STATE_DIM):
        self.state_dim = state_dim
        self._vocab: Dict[str, int] = {}
        self._vocab_counter = 0

    def _hash_string(self, s: str) -> float:
        """Deterministic string to float mapping."""
        if s not in self._vocab:
            self._vocab[s] = self._vocab_counter
            self._vocab_counter += 1
        return float(self._vocab[s]) / max(self._vocab_counter, 1)

    def encode(self, state: Dict[str, Any]) -> torch.Tensor:
        """Encode a state dict into a fixed-size tensor."""
        features: List[float] = []

        for key in sorted(state.keys()):
            value = state[key]
            if isinstance(value, (int, float)):
                features.append(float(value))
            elif isinstance(value, str):
                features.append(self._hash_string(value))
            elif isinstance(value, list):
                features.append(float(len(value)))
                for item in value[:3]:
                    if isinstance(item, (int, float)):
                        features.append(float(item))
                    elif isinstance(item, str):
                        features.append(self._hash_string(item))
            elif isinstance(value, dict):
                features.append(float(len(value)))

        # Pad or truncate to state_dim
        if len(features) < self.state_dim:
            features.extend([0.0] * (self.state_dim - len(features)))
        else:
            features = features[:self.state_dim]

        return torch.FloatTensor(features)

    def encode_batch(self, states: List[Dict[str, Any]]) -> torch.Tensor:
        """Encode a batch of states."""
        return torch.stack([self.encode(s) for s in states])

    def encode_action(self, action: Dict[str, str]) -> torch.Tensor:
        """Encode an action dict into a tensor."""
        features: List[float] = []
        for key in sorted(action.keys()):
            features.append(self._hash_string(action[key]))

        if len(features) < self.state_dim:
            features.extend([0.0] * (self.state_dim - len(features)))
        else:
            features = features[:self.state_dim]

        return torch.FloatTensor(features)


class PolicyNetwork(nn.Module):
    """MLP for discrete action probabilities."""

    def __init__(
        self,
        state_dim: int = DEFAULT_STATE_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
        action_dim: int = 64,
    ):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Returns action log-probabilities."""
        logits = self.net(state)
        return F.log_softmax(logits, dim=-1)

    def get_action_probs(self, state: torch.Tensor) -> torch.Tensor:
        """Returns action probabilities."""
        logits = self.net(state)
        return F.softmax(logits, dim=-1)


class ValueNetwork(nn.Module):
    """MLP for state value estimation V(s)."""

    def __init__(
        self,
        state_dim: int = DEFAULT_STATE_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
    ):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Returns state value."""
        return self.net(state).squeeze(-1)


class ForwardModel(nn.Module):
    """Predict next state from (state, action) — for ICM."""

    def __init__(
        self,
        state_dim: int = DEFAULT_STATE_DIM,
        action_dim: int = DEFAULT_STATE_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
    ):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, state_dim),
        )

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Predict next state encoding given current state and action."""
        x = torch.cat([state, action], dim=-1)
        return self.net(x)


class InverseModel(nn.Module):
    """Predict action from (state, next_state) — for ICM."""

    def __init__(
        self,
        state_dim: int = DEFAULT_STATE_DIM,
        action_dim: int = DEFAULT_STATE_DIM,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
    ):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
        )

    def forward(self, state: torch.Tensor, next_state: torch.Tensor) -> torch.Tensor:
        """Predict action encoding given current and next state."""
        x = torch.cat([state, next_state], dim=-1)
        return self.net(x)
