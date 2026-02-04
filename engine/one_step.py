from __future__ import annotations
from typing import Dict, Any, List, Set, Tuple
from .state import cond_true, apply_updates

def one_step_transitions(problem: Dict[str, Any]) -> List[Dict[str, int]]:
    init = problem["init"]
    seen: Set[Tuple[Tuple[str,int], ...]] = set()
    out: List[Dict[str, int]] = []
    for rule in problem["rules"]:
        if cond_true(rule["condition"], init):
            s2 = apply_updates(init, rule["updates"])
            key = tuple(sorted(s2.items()))
            if key not in seen:
                seen.add(key)
                out.append(s2)
    return out
