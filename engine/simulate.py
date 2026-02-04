from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import re
from .state import cond_true, apply_updates, reached_goal_condition, reached_target
from .pseudocode import pseudocode_for_rule

def _parse_ge_k(cond: str) -> Optional[Tuple[str,int]]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)>=(\d+)", c)
    if not m:
        return None
    return m.group(1), int(m.group(2))

def _required_min_from_updates(updates: Dict[str, str], vars_: List[str]) -> Dict[str, int]:
    req: Dict[str, int] = {}
    for v in vars_:
        expr = (updates.get(v, v) or v).replace(" ", "")
        m = re.fullmatch(rf"{re.escape(v)}-(\d+)", expr)
        if m:
            k = int(m.group(1))
            if k >= 1:
                req[v] = max(req.get(v, 0), k)
    return req

def _feasible(state: Dict[str, int], req: Dict[str, int]) -> bool:
    return all(state.get(v, 0) >= k for v, k in req.items())

def _delta(expr: str, var: str) -> Optional[int]:
    e = (expr or var).replace(" ","")
    if e == var:
        return 0
    m = re.fullmatch(rf"{re.escape(var)}\+(\d+)", e)
    if m: return int(m.group(1))
    m = re.fullmatch(rf"{re.escape(var)}-(\d+)", e)
    if m: return -int(m.group(1))
    return None

def _apply_safe_ge_k(problem: Dict[str,Any], rule: Dict[str,Any], state: Dict[str,int]) -> Dict[str,int]:
    """
    Safety wrapper demanded by user:
    For rule with condition x>=k when current x<k but x>0:
      - try apply updates (e.g., x <- x-1)
      - if x becomes 0 after the update, restore 1 token (pose) => x <- x+1
    This matches the pseudo-code:
      if non empty then retirer; if empty then poser
    Generalized to the condition variable only.
    """
    ge = _parse_ge_k(rule.get("condition",""))
    if not ge:
        return apply_updates(state, rule.get("updates",{}))

    var, k = ge
    x = int(state.get(var,0))
    if x >= k or x <= 0:
        return apply_updates(state, rule.get("updates",{}))

    # x in (0, k-1): apply update then repair if emptied
    s2 = apply_updates(state, rule.get("updates",{}))

    # Only repair if the rule decremented the condition var
    d = _delta((rule.get("updates",{}) or {}).get(var, var), var)
    if d is not None and d < 0 and int(s2.get(var,0)) == 0:
        s2[var] = s2.get(var,0) + 1
    return s2

def simulate(problem: Dict[str, Any], chooser: str = "first") -> Dict[str, Any]:
    vars_ = problem["vars"]
    rules = problem["rules"]
    max_steps = int(problem.get("max_steps", 30))
    target = problem.get("target")
    goal_condition = problem.get("goal_condition")
    model_id = problem.get("model_id")

    req_by_rule = [_required_min_from_updates(r.get("updates", {}), vars_) for r in rules]

    state = dict(problem["init"])
    table: List[Dict[str, Any]] = [{"step": 0, **state, "rule": None, "pseudocode": None}]

    def is_goal(s: Dict[str,int]) -> bool:
        return reached_target(s, target) or reached_goal_condition(s, goal_condition)

    if is_goal(state):
        return {"table": table, "stopped_reason": "goal_reached"}

    # optional RL chooser
    policy = None
    if chooser == "rl" and model_id:
        try:
            from .rl import load_policy
            policy = load_policy(model_id)
        except Exception:
            policy = None

    def is_soft_valid(rule: Dict[str,Any], st: Dict[str,int]) -> bool:
        """
        Normal validity: cond_true AND feasible.
        Soft validity (requested): for condition x>=k, if x>0 then consider selectable
        even when x<k. (Because pseudo-code wraps with non-vide + repair).
        """
        if cond_true(rule.get("condition",""), st) and _feasible(st, _required_min_from_updates(rule.get("updates",{}), vars_)):
            return True
        ge = _parse_ge_k(rule.get("condition",""))
        if ge:
            var, k = ge
            x = int(st.get(var,0))
            # allow selection if non-empty (x>0), regardless of k
            return x > 0
        return False

    for step in range(1, max_steps + 1):
        valid_idxs = [i for i, rule in enumerate(rules) if is_soft_valid(rule, state)]

        if not valid_idxs:
            table.append({"step": step, **state, "rule": None, "pseudocode": "Algorithme algo_principal()\n1: // aucune règle applicable"})
            return {"table": table, "stopped_reason": "no_applicable_rule"}

        # choose rule
        applied_idx: int
        if policy is not None:
            try:
                obs = [state.get(v,0) for v in vars_]
                mask = [1 if i in valid_idxs else 0 for i in range(len(rules))]
                a = int(policy.predict(obs, mask))
                applied_idx = a if a in valid_idxs else valid_idxs[0]
            except Exception:
                applied_idx = valid_idxs[0]
        else:
            applied_idx = valid_idxs[0]

        rule = rules[applied_idx]
        pseudo = pseudocode_for_rule(problem, rule, state)

        # apply with safety wrapper for >=k rules when x<k but x>0
        state = _apply_safe_ge_k(problem, rule, state)

        table.append({"step": step, **state, "rule": rule.get("name", f"rule_{applied_idx+1}"), "pseudocode": pseudo})

        if is_goal(state):
            return {"table": table, "stopped_reason": "goal_reached"}

    return {"table": table, "stopped_reason": "max_steps"}
