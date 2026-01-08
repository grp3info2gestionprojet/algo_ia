from __future__ import annotations

import argparse
import json
import torch

from envs.token_board_env import TokenBoardEnv, TokenBoardSpec, parse_counts, spec_from_json
from ppo.ppo_agent import Agent
from pseudocode.generator import generate_pseudocode, simulate_table, format_table


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=str, default="checkpoints/ppo_tokenboard.pt")
    p.add_argument("--init", type=str, default=None, help='ex: "1,3,5,7"')
    p.add_argument("--target", type=str, default=None, help='ex: "2,2,4,6"')
    p.add_argument("--spec", type=str, default=None, help="chemin JSON d'énoncé machine")
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--deterministic", action="store_true")
    return p.parse_args()


@torch.no_grad()
def solve(env: TokenBoardEnv, agent: Agent, deterministic: bool = False):
    obs, info = env.reset()
    obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)

    actions = []
    terminated = False
    truncated = False
    while not (terminated or truncated):
        logits = agent.actor(obs_t)
        dist = torch.distributions.Categorical(logits=logits)
        if deterministic:
            action = int(torch.argmax(dist.logits, dim=-1).item())
        else:
            action = int(dist.sample().item())

        next_obs, reward, terminated, truncated, step_info = env.step(action)
        actions.append(action)
        obs_t = torch.as_tensor(next_obs, dtype=torch.float32).unsqueeze(0)

        if "error" in step_info:
            break
        if len(actions) >= env.max_steps:
            break

    return info, actions


def main():
    args = parse_args()

    if args.spec:
        with open(args.spec, "r", encoding="utf-8") as f:
            d = json.load(f)
        spec = spec_from_json(d)
    else:
        if args.init is None or args.target is None:
            raise SystemExit("Donne soit --spec, soit --init et --target.")
        init = parse_counts(args.init)
        target = parse_counts(args.target)
        spec = TokenBoardSpec(init=init, target=target, max_steps=args.max_steps)

    env = TokenBoardEnv(curriculum=False, spec=spec, max_steps=spec.max_steps)

    obs_dim = env.observation_space.shape[0]
    act_dim = env.action_space.n
    agent = Agent(obs_dim=obs_dim, act_dim=act_dim)
    agent.load_state_dict(torch.load(args.model, map_location="cpu"))
    agent.eval()

    info, actions = solve(env, agent, deterministic=args.deterministic)

    print("=== Instance ===")
    print("init   :", info["init"])
    print("target :", info["target"])
    print("max_steps:", info["max_steps"])

    print("\n=== Pseudo-code généré ===")
    print(generate_pseudocode(actions, algo_name="ppo_solution"))

    print("\n=== Tableau de simulation ===")
    table = simulate_table(info["init"], actions)
    print(format_table(table))


if __name__ == "__main__":
    main()
