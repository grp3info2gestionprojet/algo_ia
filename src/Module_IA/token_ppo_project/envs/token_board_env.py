from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any

import numpy as np

# Compat gymnasium/gym
try:
    import gymnasium as gym
except ImportError:  # pragma: no cover
    import gym


COLORS = ["bleue", "jaune", "rouge", "verte"]
COLOR_TO_IDX = {c: i for i, c in enumerate(COLORS)}


@dataclass
class TokenBoardSpec:
    init: np.ndarray          # shape (4,)
    target: np.ndarray        # shape (4,)
    max_steps: int = 20


def parse_counts(text: str) -> np.ndarray:
    """Parse "1,3,5,7" -> array([1,3,5,7])"""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("format attendu: 'b,j,r,v' (4 entiers séparés par virgule)")
    vals = np.array([int(x) for x in parts], dtype=np.int32)
    if (vals < 0).any():
        raise ValueError("les valeurs doivent être >= 0")
    return vals


def spec_from_json(d: Dict[str, Any]) -> TokenBoardSpec:
    init = np.array([d["init"][c] for c in COLORS], dtype=np.int32)
    target = np.array([d["target"][c] for c in COLORS], dtype=np.int32)
    max_steps = int(d.get("max_steps", 20))
    return TokenBoardSpec(init=init, target=target, max_steps=max_steps)


class TokenBoardEnv(gym.Env):
    """
    Plateau à 4 cases (bleue, jaune, rouge, verte) et actions :
      0..3  : poser sur couleur i
      4..7  : retirer sur couleur i

    Objectif : atteindre un état cible depuis un état initial en <= max_steps.
    Retirer sur une case vide => erreur => épisode terminé.

    Observation (float32, taille 8) :
      [b, j, r, v, tb, tj, tr, tv]  (état courant + cible)
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        max_count: int = 10,
        max_steps: int = 20,
        curriculum: bool = True,
        spec: Optional[TokenBoardSpec] = None,
        render_mode: Optional[str] = None,
        seed: Optional[int] = None,
    ):
        super().__init__()
        self.max_count = int(max_count)
        self.max_steps_default = int(max_steps)
        self.curriculum = bool(curriculum)
        self._fixed_spec = spec
        self.render_mode = render_mode

        self.action_space = gym.spaces.Discrete(8)
        high = np.array([self.max_count] * 8, dtype=np.float32)
        self.observation_space = gym.spaces.Box(low=0.0, high=high, shape=(8,), dtype=np.float32)

        self._rng = np.random.default_rng(seed)
        self.state = np.zeros(4, dtype=np.int32)
        self.target = np.zeros(4, dtype=np.int32)
        self.steps = 0
        self.max_steps = self.max_steps_default

    def _sample_problem(self) -> Tuple[np.ndarray, np.ndarray, int]:
        init = self._rng.integers(0, 6, size=(4,), dtype=np.int32)
        target = self._rng.integers(0, 6, size=(4,), dtype=np.int32)
        min_steps = int(np.abs(target - init).sum())
        max_steps = max(self.max_steps_default, min_steps + 4)
        return init, target, max_steps

    def _get_obs(self) -> np.ndarray:
        return np.concatenate([self.state, self.target]).astype(np.float32)

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        self.steps = 0

        if self._fixed_spec is not None:
            self.state = self._fixed_spec.init.copy()
            self.target = self._fixed_spec.target.copy()
            self.max_steps = int(self._fixed_spec.max_steps)
        elif self.curriculum:
            init, target, ms = self._sample_problem()
            self.state = init
            self.target = target
            self.max_steps = ms
        else:
            self.state = np.zeros(4, dtype=np.int32)
            self.target = np.array([2, 0, 1, 1], dtype=np.int32)
            self.max_steps = self.max_steps_default

        obs = self._get_obs()
        info = {"init": self.state.copy(), "target": self.target.copy(), "max_steps": self.max_steps}
        return obs, info

    def step(self, action: int):
        self.steps += 1
        action = int(action)

        terminated = False
        truncated = False

        reward = -0.1

        color_idx = action % 4
        is_remove = action >= 4

        if is_remove:
            if self.state[color_idx] <= 0:
                reward = -5.0
                terminated = True
                info = {"error": "remove_on_empty", "color": COLORS[color_idx]}
                return self._get_obs(), reward, terminated, truncated, info
            self.state[color_idx] -= 1
        else:
            self.state[color_idx] += 1
            if self.state[color_idx] > self.max_count:
                self.state[color_idx] = self.max_count
                reward -= 0.5

        dist = int(np.abs(self.target - self.state).sum())
        reward += 0.05 * (8.0 - min(8.0, float(dist)))

        if np.array_equal(self.state, self.target):
            reward = 10.0
            terminated = True

        if self.steps >= self.max_steps and not terminated:
            truncated = True
            reward -= 1.0

        info = {"steps": self.steps, "dist": dist}
        return self._get_obs(), reward, terminated, truncated, info

    def render(self):
        if self.render_mode != "human":
            return
        b, j, r, v = self.state.tolist()
        tb, tj, tr, tv = self.target.tolist()
        print(f"State: bleue={b} jaune={j} rouge={r} verte={v} | Target: {tb},{tj},{tr},{tv} | step={self.steps}")
