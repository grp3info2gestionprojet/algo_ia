from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import re

NAMES = {"r":"rouge","v":"verte","b":"bleue","j":"jaune"}

def _n(v: str) -> str:
    return NAMES.get(v, v)

def _parse_ge_k(cond: str) -> Optional[Tuple[str,int]]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)>=(\d+)", c)
    if not m:
        return None
    return m.group(1), int(m.group(2))

def _parse_delta(expr: str, var: str) -> int | None:
    e = (expr or var).replace(" ", "")
    if e == var:
        return 0
    m = re.fullmatch(rf"{re.escape(var)}\+(\d+)", e)
    if m: return int(m.group(1))
    m = re.fullmatch(rf"{re.escape(var)}-(\d+)", e)
    if m: return -int(m.group(1))
    return None

def _updates_deltas(updates: Dict[str,str], vars_: List[str]) -> Dict[str,int]:
    out: Dict[str,int] = {}
    for v in vars_:
        d = _parse_delta(updates.get(v, v), v)
        if d is None:
            continue
        if d != 0:
            out[v] = d
    return out

def _emit_k_trick_body(var: str, k: int) -> List[str]:
    """
    k-trick (uniquement sur la variable de condition), et rien d'autre.
    Important: si x0<k, on NE DOIT PAS appliquer les autres updates (+1, autres retraits),
    car la règle 'logique' n'est pas satisfaite.
    """
    X = _n(var)
    if k <= 1:
        return [
            f"si (non est_vide({X})) alors",
            f"    retirer(→{X})",
            "finsi",
        ]

    lines: List[str] = []
    lines.append(f"si (non est_vide({X})) alors")
    lines.append(f"    retirer(→{X})")

    for _ in range(max(0, k-2)):
        lines.append(f"    si (non est_vide({X})) alors")
        lines.append(f"        retirer(→{X})")

    lines.append(f"    si (est_vide({X})) alors")
    for _ in range(k-1):
        lines.append(f"        poser(→{X})")
    lines.append(f"    sinon")
    for _ in range(max(0, k-2)):
        lines.append(f"        poser(→{X})")
    lines.append(f"    finsi")

    for _ in range(max(0, k-2)):
        lines.append(f"    sinon")
        lines.append(f"        poser(→{X})")
        lines.append(f"    finsi")

    lines.append("finsi")
    return lines

def pseudocode_for_rule(problem: Dict[str,Any], rule: Dict[str,Any], init_state: Dict[str,int]) -> str:
    vars_ = problem["vars"]
    deltas = _updates_deltas(rule.get("updates",{}), vars_)
    ge = _parse_ge_k(rule.get("condition",""))

    # If condition is x>=k and updates decrements x by 1, apply the "new principle":
    # - if x0>=k: execute full rule (all updates), guarded by non empty checks for each decrement var
    # - if 0<x0<k: generate ONLY k-trick on x (no other updates)
    # - if x0==0: do nothing
    if ge:
        xvar, k = ge
        if deltas.get(xvar) == -1:
            x0 = int(init_state.get(xvar,0))
            if x0 == 0:
                return "Algorithme algo_principal()\n1: // aucune action (vide)"
            if x0 < k:
                body = _emit_k_trick_body(xvar, k)
                out = ["Algorithme algo_principal()"]
                for i, L in enumerate(body, start=1):
                    out.append(f"{i}: {L}")
                return "\n".join(out)
            # else x0>=k -> continue to generic full-rule generation below

    # Full-rule generation: nested guards for every decrement var (unique), then apply all ops.
    dec_vars: List[str] = []
    inc_ops: List[str] = []
    dec_ops: List[str] = []

    for v, d in deltas.items():
        if d < 0:
            dec_vars.append(v)
            for _ in range(-d):
                dec_ops.append(f"retirer(→{_n(v)})")
        elif d > 0:
            for _ in range(d):
                inc_ops.append(f"poser(→{_n(v)})")

    # unique in stable order r,v,b,j
    order = [v for v in vars_ if v in dec_vars]
    # if no decrements, just do increments
    body_lines: List[str] = []
    if order:
        # open nested ifs
        for idx, v in enumerate(order):
            indent = "    " * idx
            body_lines.append(f"{indent}si (non est_vide({_n(v)})) alors")
        # actions at deepest indent
        deep = "    " * len(order)
        for op in dec_ops + inc_ops:
            body_lines.append(f"{deep}{op}")
        # close ifs
        for idx in range(len(order)-1, -1, -1):
            indent = "    " * idx
            body_lines.append(f"{indent}finsi")
    else:
        body_lines = inc_ops if inc_ops else ["// rien"]

    out = ["Algorithme algo_principal()"]
    for i, L in enumerate(body_lines, start=1):
        out.append(f"{i}: {L}")
    return "\n".join(out)

def generate_pseudocode(problem: Dict[str,Any]) -> str:
    init_state = dict(problem.get("init",{}))
    rules = problem["rules"]
    if not rules:
        return "Algorithme algo_principal()\n1: // aucune règle"
    return pseudocode_for_rule(problem, rules[0], init_state)
