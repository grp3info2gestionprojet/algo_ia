from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import re

# Noms affichés (FR)
NAMES = {"b":"bleue","j":"jaune","r":"rouge","v":"verte"}

def _n(v: str) -> str:
    return NAMES.get(v, v)

def _parse_ge_k(cond: str) -> Optional[Tuple[str,int]]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)>=(\d+)", c)
    if not m:
        return None
    return m.group(1), int(m.group(2))

def _parse_lt_1(cond: str) -> Optional[str]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)<1", c)
    return m.group(1) if m else None

def _parse_ge_1(cond: str) -> Optional[str]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)>=1", c)
    return m.group(1) if m else None

def _parse_delta(expr: str, var: str) -> int | None:
    """
    Supporte les formes simples attendues: x, x+N, x-N (N entier >=1)
    """
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

def _emit_ops_for_deltas(deltas: Dict[str,int]) -> Tuple[List[str], List[str]]:
    """
    Retourne (dec_ops, inc_ops) sous forme de primitives retirer/poser.
    """
    dec_ops: List[str] = []
    inc_ops: List[str] = []
    # ordre stable alphabétique par variable
    for v in sorted(deltas.keys()):
        d = deltas[v]
        if d < 0:
            for _ in range(-d):
                dec_ops.append(f"retirer(→{_n(v)})")
        elif d > 0:
            for _ in range(d):
                inc_ops.append(f"poser(→{_n(v)})")
    return dec_ops, inc_ops

def _emit_guard_chain(dec_vars: List[str], inner_lines: List[str], base_indent: int = 0) -> List[str]:
    """
    Construit des `si (non est_vide(x)) alors` imbriqués pour sécuriser les retraits.
    - dec_vars: liste de variables (avec répétitions possibles si besoin d'en retirer plusieurs)
    """
    lines: List[str] = []
    # open ifs
    for i, v in enumerate(dec_vars):
        lines.append(("    "*(base_indent+i)) + f"si (non est_vide({_n(v)})) alors")
    # inner
    for L in inner_lines:
        lines.append(("    "*(base_indent+len(dec_vars))) + L)
    # close
    for i in range(len(dec_vars)-1, -1, -1):
        lines.append(("    "*(base_indent+i)) + "finsi")
    return lines


def _k_trick_full(rule_deltas: Dict[str,int], xvar: str, k: int) -> List[str]:
    """
    Génère un pseudo-code "k-trick" général (k>=2) pour exprimer x>=k avec seulement:
      - est_vide / non est_vide
      - retirer / poser

    Idée:
      1) On exécute *toutes* les mises à jour de la règle (retirer/poser) de manière sécurisée.
      2) On vérifie ensuite si x avait au moins k jetons en tentant de retirer (k-2) jetons supplémentaires.
         - Si on échoue (x devient vide trop tôt) => règle invalide => on annule toutes les mises à jour.
         - Si on réussit => règle valide => on restaure les retraits de test (net: x diminue de 1).
    """
    X = _n(xvar)
    if k < 2:
        return []

    # Ops de la règle
    dec_ops, inc_ops = _emit_ops_for_deltas(rule_deltas)

    # Gardes pour sécuriser les retraits initiaux (sans dupliquer le test sur x, déjà fait en externe)
    dec_guard_vars: List[str] = []
    for v in sorted(rule_deltas.keys()):
        d = rule_deltas[v]
        if d < 0:
            dec_guard_vars += [v] * (-d)
    if xvar in dec_guard_vars:
        dec_guard_vars.remove(xvar)

    # lignes d'annulation (undo) des updates hors x
    undo_lines: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d > 0:
            for _ in range(d):
                undo_lines.append(f"retirer(→{_n(v)})")
        elif d < 0:
            for _ in range(-d):
                undo_lines.append(f"poser(→{_n(v)})")

    lines: List[str] = []
    lines.append(f"si (non est_vide({X})) alors")

    # 1) appliquer la règle (sécurisée)
    applied = dec_ops + inc_ops
    if dec_guard_vars:
        lines.extend(_emit_guard_chain(dec_guard_vars, applied, base_indent=1))
    else:
        for op in applied:
            lines.append("    " + op)

    extra = k - 2  # nb de retraits de test

    def emit_invalid(indent: int, removed_so_far: int):
        # Restaurer x (1 retrait principal + removed_so_far retraits de test réussis)
        for _ in range(1 + removed_so_far):
            lines.append("    "*indent + f"poser(→{X})")
        for u in undo_lines:
            lines.append("    "*indent + u)

    def emit_valid(indent: int):
        # Restaurer uniquement les retraits de test (extra)
        for _ in range(extra):
            lines.append("    "*indent + f"poser(→{X})")

    # 2) Chaîne imbriquée de retraits de test
    def rec(depth: int, removed: int, indent: int):
        if depth == extra:
            # après avoir retiré extra jetons (si extra==0, on vient directement ici)
            lines.append("    "*indent + f"si (est_vide({X})) alors")
            emit_invalid(indent+1, removed)
            if extra > 0:
                lines.append("    "*indent + "sinon")
                emit_valid(indent+1)
            lines.append("    "*indent + "finsi")
            return

        # on tente de retirer un jeton supplémentaire
        lines.append("    "*indent + f"si (non est_vide({X})) alors")
        lines.append("    "*(indent+1) + f"retirer(→{X})")
        rec(depth+1, removed+1, indent+1)
        lines.append("    "*indent + "sinon")
        emit_invalid(indent+1, removed)  # on n'a pas pu retirer le prochain jeton
        lines.append("    "*indent + "finsi")

    rec(0, 0, 1)

    lines.append("finsi")
    return lines

def _simple_condition_to_if(cond: str) -> Optional[str]:
    """
    Transforme les conditions simples en tests est_vide/non est_vide pour le pseudo-code.
    """
    v = _parse_ge_1(cond)
    if v:
        return f"si (non est_vide({_n(v)})) alors"
    v = _parse_lt_1(cond)
    if v:
        return f"si (est_vide({_n(v)})) alors"
    return None

def pseudocode_for_rule(problem: Dict[str,Any], rule: Dict[str,Any], init_state: Dict[str,int]) -> List[str]:
    vars_ = list(problem["vars"])
    deltas = _updates_deltas(rule.get("updates",{}), vars_)
    ge = _parse_ge_k(rule.get("condition",""))

    # Cas condition x>=k avec update x<-x-1
    if ge:
        xvar, k = ge
        if deltas.get(xvar) == -1 and k >= 2:
            x0 = int(init_state.get(xvar,0))
            if x0 == 0:
                return []  # aucune action générée
            if x0 < k:
                return _k_trick_full(deltas, xvar, k)
            # x0>=k: on peut générer un pseudo-code simple (règle valide)
            # => appliquer la règle avec des gardes sur les retraits
            dec_guard_vars: List[str] = []
            for v in sorted(deltas.keys()):
                d = deltas[v]
                if d < 0:
                    dec_guard_vars += [v] * (-d)
            dec_ops, inc_ops = _emit_ops_for_deltas(deltas)
            inner = dec_ops + inc_ops
            if dec_guard_vars:
                return _emit_guard_chain(dec_guard_vars, inner, base_indent=0)
            return inner

    # Autres conditions simples : convertir si possible
    if_line = _simple_condition_to_if(rule.get("condition",""))
    dec_guard_vars: List[str] = []
    for v in sorted(deltas.keys()):
        d = deltas[v]
        if d < 0:
            dec_guard_vars += [v] * (-d)
    dec_ops, inc_ops = _emit_ops_for_deltas(deltas)
    actions = dec_ops + inc_ops
    if not actions:
        actions = ["// rien"]

    if if_line:
        lines = [if_line]
        # sécuriser les retraits par des gardes imbriqués dans ce if
        # (évite le double test sur la même variable que celle testée dans la condition)
        ge1 = _parse_ge_1(rule.get("condition",""))
        if ge1 and ge1 in dec_guard_vars:
            dec_guard_vars.remove(ge1)
        if dec_guard_vars:
            guarded = _emit_guard_chain(dec_guard_vars, actions, base_indent=1)
            lines.extend(guarded)
        else:
            for op in actions:
                lines.append("    " + op)
        lines.append("finsi")
        return lines

    # fallback : on affiche la condition brute
    lines = [f"si ({rule.get('condition','')}) alors"]
    for op in actions:
        lines.append("    " + op)
    lines.append("finsi")
    return lines

def generate_pseudocode(problem: Dict[str,Any]) -> str:
    init_state = dict(problem.get("init",{}))
    rules = problem.get("rules", {}).get("rules", []) if "rules" in problem and isinstance(problem["rules"], dict) else problem.get("rules", [])
    # compat: problem["rules"] peut être une liste (ancienne structure) ou dict contenant "rules"
    if isinstance(problem.get("rules"), dict):
        vars_ = problem["rules"].get("vars", [])
        rules_list = problem["rules"].get("rules", [])
    else:
        vars_ = problem.get("vars", [])
        rules_list = problem.get("rules", [])
    if not vars_:
        vars_ = sorted(init_state.keys())
    if not rules_list:
        return "Algorithme algo_principal()\n1: // aucune règle"

    # normaliser problem pour pseudocode_for_rule
    prob_norm = {"vars": vars_}
    blocks: List[str] = []
    line_no = 1
    out_lines = ["Algorithme algo_principal()"]
    for r in rules_list:
        lines = pseudocode_for_rule(prob_norm, r, init_state)
        if not lines:
            continue
        for L in lines:
            out_lines.append(f"{line_no}: {L}")
            line_no += 1
    if line_no == 1:
        out_lines.append("1: // aucune action générée")
    return "\n".join(out_lines)
