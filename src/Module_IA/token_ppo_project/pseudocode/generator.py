from __future__ import annotations

from typing import List, Dict, Any
import numpy as np

COLORS = ["bleue", "jaune", "rouge", "verte"]

def action_to_line(action: int) -> str:
    color = COLORS[action % 4]
    if action < 4:
        return f"poser(→ {color})"
    return f"retirer(→ {color})"

def generate_pseudocode(actions: List[int], algo_name: str = "solution") -> str:
    lines = [f"Algorithme {algo_name}()"]
    for i, a in enumerate(actions, start=1):
        lines.append(f"{i}: {action_to_line(int(a))}")
    return "\n".join(lines)

def simulate_table(init: np.ndarray, actions: List[int]) -> List[Dict[str, Any]]:
    state = init.astype(int).copy()
    table: List[Dict[str, Any]] = []
    table.append({"ligne": "initial", **{c: int(state[i]) for i, c in enumerate(COLORS)}})
    for k, a in enumerate(actions, start=1):
        a = int(a)
        idx = a % 4
        if a < 4:
            state[idx] += 1
        else:
            if state[idx] <= 0:
                table.append({"ligne": k, "error": f"retirer sur case vide ({COLORS[idx]})"})
                break
            state[idx] -= 1
        table.append({"ligne": k, **{c: int(state[i]) for i, c in enumerate(COLORS)}})
    table.append({"ligne": "final", **{c: int(state[i]) for i, c in enumerate(COLORS)}})
    return table

def format_table(table: List[Dict[str, Any]]) -> str:
    header = "Ligne\tBleue\tJaune\tRouge\tVerte"
    lines = [header]
    for row in table:
        if "error" in row:
            lines.append(f"{row['ligne']}\tERROR: {row['error']}")
            continue
        lines.append(f"{row['ligne']}\t{row['bleue']}\t{row['jaune']}\t{row['rouge']}\t{row['verte']}")
    return "\n".join(lines)
