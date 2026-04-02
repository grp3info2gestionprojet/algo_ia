from __future__ import annotations
from typing import Any, Dict, List
import re
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from .state import cond_true, apply_updates, reached_target, reached_goal_condition

def _required_min_from_updates(updates: Dict[str, str], vars_: List[str]) -> Dict[str, int]:
    """
    Pour éviter des états négatifs: si update contient x <- x-k alors exiger x >= k.
    Renvoie dict var -> k minimal.
    """
    req: Dict[str, int] = {}
    for v in vars_:
        expr = updates.get(v, v)
        e = expr.replace(" ", "")
        m = re.fullmatch(rf"{re.escape(v)}-(\d+)", e)
        if m:
            k = int(m.group(1))
            if k >= 1:
                req[v] = max(req.get(v, 0), k)
        elif e == f"{v}-1":
            req[v] = max(req.get(v, 0), 1)
    return req

class TokenRulesEnv(gym.Env):
    def __init__(self, problem: Dict[str, Any]):
        super().__init__()
        self.problem = problem
        self.vars: List[str] = problem["vars"]
        self.rules = problem["rules"]
        self.max_steps = int(problem["max_steps"])
        self.target = problem.get("target")
        self.goal_condition = problem.get("goal_condition")

        init = problem["init"]
        hi = max([init[v] for v in self.vars] + [0]) + self.max_steps + 5
        hi = max(hi, 50)

        self.observation_space = spaces.Box(
            low=np.zeros(len(self.vars), dtype=np.int32),
            high=np.full(len(self.vars), hi, dtype=np.int32),
            dtype=np.int32
        )
        self.action_space = spaces.Discrete(len(self.rules))

        # pré-calcul des contraintes minimales (x>=k) induites par les updates
        self._req_by_rule: List[Dict[str, int]] = [
            _required_min_from_updates(r.get("updates", {}), self.vars) for r in self.rules
        ]

        self.state: Dict[str,int] = {}
        self.steps = 0

    def _obs(self):
        return np.array([self.state[v] for v in self.vars], dtype=np.int32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.state = dict(self.problem["init"])
        self.steps = 0
        return self._obs(), {}

    def _feasible_by_updates(self, rule_idx: int) -> bool:
        req = self._req_by_rule[rule_idx]
        for v, k in req.items():
            if self.state.get(v, 0) < k:
                return False
        return True

    def action_masks(self) -> np.ndarray:
        masks = []
        for idx, r in enumerate(self.rules):
            try:
                ok = bool(cond_true(r["condition"], self.state)) and self._feasible_by_updates(idx)
                masks.append(ok)
            except Exception:
                masks.append(False)
        if not any(masks):
            masks = [True] * len(self.rules)
        return np.array(masks, dtype=bool)

    def step(self, action: int):
        self.steps += 1
        action = int(action)
        rule = self.rules[action]

        applicable = bool(cond_true(rule["condition"], self.state)) and self._feasible_by_updates(action)

        reward = -0.01
        if applicable:
            self.state = apply_updates(self.state, rule["updates"])
        else:
            # devrait être rare grâce au masque
            reward -= 0.1

        terminated = False
        truncated = False
        if reached_target(self.state, self.target) or reached_goal_condition(self.state, self.goal_condition):
            reward += 1.0
            terminated = True
        if self.steps >= self.max_steps:
            truncated = True

        info = {"state": dict(self.state), "rule": rule.get("name"), "applicable": applicable}
        return self._obs(), float(reward), terminated, truncated, info
