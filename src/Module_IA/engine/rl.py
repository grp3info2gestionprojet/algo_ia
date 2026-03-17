from __future__ import annotations
from typing import Any, Dict, List
import numpy as np

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from sb3_contrib.common.maskable.utils import get_action_masks

from .rl_env import TokenRulesEnv

def train_masked_ppo(problem: Dict[str, Any], timesteps: int, model_path: str, seed=None) -> Dict[str, Any]:
    env = TokenRulesEnv(problem)
    env = ActionMasker(env, lambda e: e.action_masks())

    model = MaskablePPO(
        "MlpPolicy",
        env,
        verbose=0,
        seed=seed,
        n_steps=256,
        batch_size=256,
        gamma=0.99,
        learning_rate=3e-4,
    )
    model.learn(total_timesteps=timesteps)
    model.save(model_path)

    return {
        "saved_to": model_path,
        "timesteps": timesteps,
        "n_actions": int(env.action_space.n),
        "goal": "target" if problem.get("target") else ("goal_condition" if problem.get("goal_condition") else "none"),
    }

def rollout_policy(problem: Dict[str, Any], model_path: str, n_episodes: int = 1, max_steps: int | None = None) -> Dict[str, Any]:
    env0 = TokenRulesEnv(problem)
    env = ActionMasker(env0, lambda e: e.action_masks())
    model = MaskablePPO.load(model_path, env=env)

    out = []
    for ep in range(n_episodes):
        obs, _ = env.reset()
        traj = []
        done = False
        t = 0
        while not done:
            masks = get_action_masks(env)
            action, _ = model.predict(obs, action_masks=masks, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            traj.append({
                "step": t,
                "action": int(action),
                "rule": info.get("rule"),
                "applicable": bool(info.get("applicable")),
                "reward": float(reward),
                "state": info.get("state"),
            })
            t += 1
            done = bool(terminated or truncated)
            if max_steps is not None and t >= int(max_steps):
                break
        out.append({"episode": ep, "trajectory": traj})
    return {"episodes": out}
