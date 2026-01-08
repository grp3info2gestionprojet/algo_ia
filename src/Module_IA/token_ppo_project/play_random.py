from __future__ import annotations

from envs.token_board_env import TokenBoardEnv
from pseudocode.generator import generate_pseudocode, simulate_table, format_table

def main():
    env = TokenBoardEnv(curriculum=True, seed=0)
    obs, info = env.reset()
    actions = []
    terminated = False
    truncated = False
    while not (terminated or truncated):
        a = env.action_space.sample()
        obs, r, terminated, truncated, inf = env.step(a)
        actions.append(a)
        if "error" in inf:
            break
    print(generate_pseudocode(actions, algo_name="random_policy"))
    print()
    print(format_table(simulate_table(info["init"], actions)))

if __name__ == "__main__":
    main()
