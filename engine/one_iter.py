from __future__ import annotations
from typing import Dict, Any, Optional
from .state import cond_true
from .pseudocode import pseudocode_for_rule, _parse_ge_k, _parse_delta

def _apply_full_rule(updates: Dict[str,str], state: Dict[str,int], guard_vars: list[str]) -> Dict[str,int]:
    s = state.copy()
    # check all guards
    for gv in guard_vars:
        if int(s.get(gv,0)) <= 0:
            return s
    # apply decrements then increments
    for var, expr in updates.items():
        d = _parse_delta(expr, var)
        if d is None or d == 0:
            continue
        if d < 0:
            x = int(s.get(var,0))
            if x > 0:
                s[var] = max(0, x + d)
    for var, expr in updates.items():
        d = _parse_delta(expr, var)
        if d is None or d == 0:
            continue
        if d > 0:
            s[var] = int(s.get(var,0)) + d
    return s

def one_iteration(problem: Dict[str,Any]) -> Dict[str,Any]:
    vars_ = problem["vars"]
    rules = problem["rules"]
    state0 = dict(problem["init"])

    chosen_idx: Optional[int] = None
    for i, r in enumerate(rules):
        ge = _parse_ge_k(r.get("condition",""))
        if ge:
            var, _k = ge
            if int(state0.get(var,0)) > 0:
                chosen_idx = i
                break
        if cond_true(r.get("condition",""), state0):
            chosen_idx = i
            break

    if chosen_idx is None:
        pseudo = "Algorithme algo_principal()\n1: // aucune règle applicable"
        table = [{"step": 0, **state0}, {"step": 1, **state0}]
        return {"pseudocode": pseudo, "table": table, "rule": None}

    rule = rules[chosen_idx]
    updates = rule.get("updates", {}) or {}
    ge = _parse_ge_k(rule.get("condition",""))

    # apply according to the same principle as pseudocode:
    state1 = state0.copy()
    if ge:
        xvar, k = ge
        d = _parse_delta(updates.get(xvar, xvar), xvar)
        x0 = int(state0.get(xvar,0))
        if d == -1 and x0 > 0 and x0 < k:
            # k-trick => net 0 and NO other updates
            state1 = state0.copy()
        else:
            # full rule with guards on all decrement vars
            guard_vars = [v for v in vars_ if (_parse_delta(updates.get(v,v), v) or 0) < 0]
            state1 = _apply_full_rule(updates, state0, guard_vars)
    else:
        guard_vars = [v for v in vars_ if (_parse_delta(updates.get(v,v), v) or 0) < 0]
        state1 = _apply_full_rule(updates, state0, guard_vars)

    pseudo = pseudocode_for_rule(problem, rule, state0)
    table = [{"step": 0, **state0}, {"step": 1, **state1}]
    return {"pseudocode": pseudo, "table": table, "rule": rule.get("name", f"rule_{chosen_idx+1}")}
