from __future__ import annotations
from typing import Dict, Any, Optional

from .state import cond_true
from .pseudocode import _parse_ge_k, _parse_delta, pseudocode_for_rule

def _has_enough_for_decrements(updates: Dict[str,str], state: Dict[str,int]) -> bool:
    """
    Vérifie qu'on peut exécuter tous les retraits (sans négatif).
    """
    for var, expr in updates.items():
        d = _parse_delta(expr, var)
        if d is None or d >= 0:
            continue
        if int(state.get(var,0)) < (-d):
            return False
    return True

def _apply_full_rule(updates: Dict[str,str], state: Dict[str,int]) -> Dict[str,int]:
    """
    Applique les updates en deux phases:
    - retraits (sécurisés)
    - ajouts
    """
    if not _has_enough_for_decrements(updates, state):
        return state.copy()

    s = state.copy()
    # retraits
    for var, expr in updates.items():
        d = _parse_delta(expr, var)
        if d is None or d >= 0:
            continue
        s[var] = int(s.get(var,0)) + d
    # ajouts
    for var, expr in updates.items():
        d = _parse_delta(expr, var)
        if d is None or d <= 0:
            continue
        s[var] = int(s.get(var,0)) + d
    return s

def one_iteration(problem: Dict[str,Any]) -> Dict[str,Any]:
    vars_ = problem["vars"]
    rules = problem["rules"]
    state0 = dict(problem["init"])

    chosen_idx: Optional[int] = None

    # Choix simple (1 itération) :
    # - si condition x>=k (k>1) : on considère "choisissable" si x>0 (pour illustrer le k-trick)
    # - sinon : condition vraie
    for i, r in enumerate(rules):
        ge = _parse_ge_k(r.get("condition",""))
        if ge:
            x, _k = ge
            if int(state0.get(x,0)) > 0:
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

    state1 = state0.copy()

    # Cohérent avec la génération pseudo-code :
    # - si x>=k avec update x<-x-1 :
    #   * si x0>=k : appliquer la règle complète (si les retraits sont possibles)
    #   * si 0<x0<k : k-trick => effet net 0 (on annule)
    #   * si x0=0 : rien
    if ge:
        xvar, k = ge
        d = _parse_delta(updates.get(xvar, xvar), xvar)
        x0 = int(state0.get(xvar,0))
        if d == -1 and k >= 2:
            if x0 >= k:
                state1 = _apply_full_rule(updates, state0)
            else:
                state1 = state0.copy()
        else:
            # condition numérique mais pas le pattern attendu -> fallback : règle si condition vraie
            if cond_true(rule.get("condition",""), state0):
                state1 = _apply_full_rule(updates, state0)
    else:
        if cond_true(rule.get("condition",""), state0):
            state1 = _apply_full_rule(updates, state0)

    pseudo_lines = pseudocode_for_rule(problem, rule, state0)
    pseudo = "Algorithme algo_principal()\n"
    if not pseudo_lines:
        pseudo += "1: // aucune action générée"
    else:
        pseudo += "\n".join(f"{i}: {L}" for i, L in enumerate(pseudo_lines, start=1))

    table = [{"step": 0, **state0}, {"step": 1, **state1}]
    return {"pseudocode": pseudo, "table": table, "rule": rule.get("name", f"rule_{chosen_idx+1}")}
