from __future__ import annotations

import argparse
import time
import torch

try:
    import gymnasium as gym
except ImportError:  # pragma: no cover
    import gym

from envs.token_board_env import TokenBoardEnv
from ppo.ppo_train_loop import train_ppo


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--total-timesteps", type=int, default=200_000)
    p.add_argument("--learning-rate", type=float, default=2.5e-4)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--num-envs", type=int, default=8)
    p.add_argument("--num-steps", type=int, default=128)
    p.add_argument("--cuda", action="store_true")
    p.add_argument("--save-path", type=str, default="checkpoints/ppo_tokenboard.pt")
    return p.parse_args()


def make_env(seed: int):
    def thunk():
        env = TokenBoardEnv(curriculum=True, seed=seed)
        env = gym.wrappers.RecordEpisodeStatistics(env)
        return env
    return thunk


def main():
    args = parse_args()
    device = torch.device("cuda" if args.cuda and torch.cuda.is_available() else "cpu")
    run_name = f"tokenboard__seed{args.seed}__{int(time.time())}"

    envs = gym.vector.SyncVectorEnv([make_env(args.seed + i) for i in range(args.num_envs)])

    agent = train_ppo(
        envs=envs,
        total_timesteps=args.total_timesteps,
        learning_rate=args.learning_rate,
        seed=args.seed,
        num_steps=args.num_steps,
        run_name=run_name,
        device=device,
    )

    import os
    os.makedirs("checkpoints", exist_ok=True)
    torch.save(agent.state_dict(), args.save_path)
    print(f"✅ Modèle sauvegardé: {args.save_path}")
    envs.close()


if __name__ == "__main__":
    main()
