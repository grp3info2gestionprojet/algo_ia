from __future__ import annotations
from typing import Dict

def cond_true(condition: str, state: Dict[str, int]) -> bool:
    return bool(eval(condition, {}, dict(state)))

def apply_updates(state: Dict[str, int], updates: Dict[str, str]) -> Dict[str, int]:
    new_state = dict(state)
    for var, expr in updates.items():
        new_state[var] = int(eval(expr, {}, dict(new_state)))
    return new_state

def reached_target(state: Dict[str, int], target: Dict[str, int] | None) -> bool:
    if not target:
        return False
    return all(state.get(k) == v for k, v in target.items())

def reached_goal_condition(state: Dict[str, int], goal_condition: str | None) -> bool:
    if not goal_condition:
        return False
    return bool(eval(goal_condition, {}, dict(state)))
