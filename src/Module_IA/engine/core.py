from __future__ import annotations
from typing import Any, Dict, List

def parse_problem(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "init" not in payload or not isinstance(payload["init"], dict):
        raise ValueError("init manquant ou invalide")
    if "rules" not in payload or not isinstance(payload["rules"], dict):
        raise ValueError("rules manquant ou invalide")

    rules = payload["rules"]
    vars_ = rules.get("vars")
    if not isinstance(vars_, list) or not all(isinstance(v, str) for v in vars_):
        raise ValueError("rules.vars doit être une liste de chaînes")

    rules_list = rules.get("rules")
    if not isinstance(rules_list, list) or len(rules_list) == 0:
        raise ValueError("rules.rules doit être une liste non vide")

    init = payload["init"]
    norm_init = {}
    for v in vars_:
        val = init.get(v, 0)
        if not isinstance(val, int):
            raise ValueError(f"init.{v} doit être un entier")
        norm_init[v] = val

    for i, r in enumerate(rules_list):
        if "condition" not in r or "updates" not in r:
            raise ValueError(f"Règle {i+1}: condition et updates requis")
        if "name" not in r:
            r["name"] = f"rule_{i+1}"

    return {
        "vars": vars_,
        "init": norm_init,
        "rules": rules_list,
        "max_steps": int(payload.get("max_steps", 30)),
        "target": payload.get("target"),
        "goal_condition": payload.get("goal_condition"),
    }
