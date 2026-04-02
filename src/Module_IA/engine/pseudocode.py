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

# BUG FIX #2: condition ==0
def _parse_eq_0(cond: str) -> Optional[str]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)==0", c)
    return m.group(1) if m else None

# BUG FIX #3: condition ==k (k>=1)
def _parse_eq_k(cond: str) -> Optional[Tuple[str,int]]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)==(\d+)", c)
    if not m:
        return None
    k = int(m.group(2))
    if k == 0:
        return None
    return m.group(1), k

# BUG FIX #4: condition <=k
def _parse_le_k(cond: str) -> Optional[Tuple[str,int]]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)<=(\d+)", c)
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

def _emit_ops_for_deltas(deltas: Dict[str,int]) -> Tuple[List[str], List[str]]:
    dec_ops: List[str] = []
    inc_ops: List[str] = []
    for v in sorted(deltas.keys()):
        d = deltas[v]
        if d < 0:
            for _ in range(-d):
                dec_ops.append(f"retirer(->  {_n(v)})")
        elif d > 0:
            for _ in range(d):
                inc_ops.append(f"poser(->{_n(v)})")
    return dec_ops, inc_ops

def _emit_guard_chain(dec_vars: List[str], inner_lines: List[str], base_indent: int = 0) -> List[str]:
    lines: List[str] = []
    for i, v in enumerate(dec_vars):
        lines.append(("    "*(base_indent+i)) + f"si (non est_vide({_n(v)})) alors")
    for L in inner_lines:
        lines.append(("    "*(base_indent+len(dec_vars))) + L)
    for i in range(len(dec_vars)-1, -1, -1):
        lines.append(("    "*(base_indent+i)) + "finsi")
    return lines


def _k_trick_full(rule_deltas: Dict[str,int], xvar: str, k: int) -> List[str]:
    X = _n(xvar)
    if k < 2:
        return []

    dec_ops, inc_ops = _emit_ops_for_deltas(rule_deltas)

    dec_guard_vars: List[str] = []
    for v in sorted(rule_deltas.keys()):
        d = rule_deltas[v]
        if d < 0:
            dec_guard_vars += [v] * (-d)
    if xvar in dec_guard_vars:
        dec_guard_vars.remove(xvar)

    undo_lines: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d > 0:
            for _ in range(d):
                undo_lines.append(f"retirer(->{_n(v)})")
        elif d < 0:
            for _ in range(-d):
                undo_lines.append(f"poser(->{_n(v)})")

    lines: List[str] = []
    lines.append(f"si (non est_vide({X})) alors")

    applied = dec_ops + inc_ops
    if dec_guard_vars:
        lines.extend(_emit_guard_chain(dec_guard_vars, applied, base_indent=1))
    else:
        for op in applied:
            lines.append("    " + op)

    extra = k - 2

    def emit_invalid(indent: int, removed_so_far: int):
        for _ in range(1 + removed_so_far):
            lines.append("    "*indent + f"poser(->{X})")
        for u in undo_lines:
            lines.append("    "*indent + u)

    def emit_valid(indent: int):
        for _ in range(extra):
            lines.append("    "*indent + f"poser(->{X})")

    def rec(depth: int, removed: int, indent: int):
        if depth == extra:
            lines.append("    "*indent + f"si (est_vide({X})) alors")
            emit_invalid(indent+1, removed)
            if extra > 0:
                lines.append("    "*indent + "sinon")
                emit_valid(indent+1)
            lines.append("    "*indent + "finsi")
            return
        lines.append("    "*indent + f"si (non est_vide({X})) alors")
        lines.append("    "*(indent+1) + f"retirer(->{X})")
        rec(depth+1, removed+1, indent+1)
        lines.append("    "*indent + "sinon")
        emit_invalid(indent+1, removed)
        lines.append("    "*indent + "finsi")

    rec(0, 0, 1)
    lines.append("finsi")
    return lines


# BUG FIX #1: condition >=k avec update positif (delta > 0)
def _ge_k_with_positive_delta(rule_deltas: Dict[str,int], xvar: str, k: int) -> List[str]:
    """
    Condition x>=k avec delta(x) > 0.
    Algorithme: retirer (k-1) fois pour tester x>=k, puis restaurer + appliquer le delta.

    Exemple: b>=2, b<-b+1  (attendu PDF):
      si (non est_vide(bleue)) alors
        retirer(->bleue)
        si (non est_vide(bleue)) alors
          poser(->bleue)
          poser(->bleue)
        sinon
          poser(->bleue)
        finsi
      sinon
      finsi
    """
    X = _n(xvar)
    test_removals = k - 1  # nombre de retraits de test nécessaires
    dx = rule_deltas.get(xvar, 0)

    other_ops: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d > 0:
            for _ in range(d):
                other_ops.append(f"poser(->{_n(v)})")
        elif d < 0:
            for _ in range(-d):
                other_ops.append(f"retirer(->{_n(v)})")

    lines: List[str] = []

    def rec(depth: int, indent: int):
        """
        depth = retraits de test déjà effectués (incluant le 1er retrait initial).
        Si depth == test_removals: on a fait tous les retraits de test.
          → si (non est_vide): restaurer + appliquer
          → sinon: annuler (depth-1) retraits (le dernier retrait échoue → x vide)
        Sinon: tenter un autre retrait.
        """
        if depth == test_removals:
            # On a retiré test_removals jetons. Vérifier si encore non vide (=>x>=k).
            lines.append("    "*indent + f"si (non est_vide({X})) alors")
            # restaurer les test_removals retraits + appliquer delta
            for _ in range(test_removals):
                lines.append("    "*(indent+1) + f"poser(->{X})")
            for _ in range(dx):
                lines.append("    "*(indent+1) + f"poser(->{X})")
            for op in other_ops:
                lines.append("    "*(indent+1) + op)
            lines.append("    "*indent + "sinon")
            # annuler: restaurer depth retraits
            for _ in range(depth):
                lines.append("    "*(indent+1) + f"poser(->{X})")
            lines.append("    "*indent + "finsi")
            return

        lines.append("    "*indent + f"si (non est_vide({X})) alors")
        lines.append("    "*(indent+1) + f"retirer(->{X})")
        rec(depth+1, indent+1)
        lines.append("    "*indent + "sinon")
        for _ in range(depth):
            lines.append("    "*(indent+1) + f"poser(->{X})")
        lines.append("    "*indent + "finsi")

    lines.append(f"si (non est_vide({X})) alors")
    lines.append("    " + f"retirer(->{X})")
    rec(1, 1)
    lines.append("sinon")
    lines.append("finsi")
    return lines


# BUG FIX #2: condition ==0
def _pseudocode_eq_0(xvar: str, rule_deltas: Dict[str,int]) -> List[str]:
    """Condition x==0 → si (est_vide(x)) alors <ops> finsi"""
    X = _n(xvar)
    dec_ops, inc_ops = _emit_ops_for_deltas(rule_deltas)
    actions = dec_ops + inc_ops
    if not actions:
        actions = ["// rien"]

    lines = [f"si (est_vide({X})) alors"]
    dec_guard_vars: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d < 0:
            dec_guard_vars += [v] * (-d)
    if dec_guard_vars:
        lines.extend(_emit_guard_chain(dec_guard_vars, actions, base_indent=1))
    else:
        for op in actions:
            lines.append("    " + op)
    lines.append("finsi")
    return lines


# BUG FIX #3: condition ==k (k>=1)
def _pseudocode_eq_k(xvar: str, k: int, rule_deltas: Dict[str,int]) -> List[str]:
    """
    Condition x==k: retirer k jetons, tester est_vide, puis restaurer selon résultat.

    Exemple b==2, b<-b-1 (attendu PDF):
      si (non est_vide(bleue)) alors
        retirer(->bleue)
        si (non est_vide(bleue)) alors
          retirer(->bleue)
          si (est_vide(bleue)) alors
            poser(->bleue)
            poser(->bleue)
            poser(->bleue)
          sinon
            poser(->bleue)
            poser(->bleue)
          finsi
        sinon
          poser(->bleue)
        finsi
      sinon
      finsi
    """
    X = _n(xvar)
    dx = rule_deltas.get(xvar, 0)

    other_inc: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d > 0:
            for _ in range(d):
                other_inc.append(f"poser(->{_n(v)})")
        elif d < 0:
            for _ in range(-d):
                other_inc.append(f"retirer(->{_n(v)})")

    lines: List[str] = []

    def rec(depth: int, indent: int):
        if depth == k:
            # Tester si vide: x était exactement k
            lines.append("    "*indent + f"si (est_vide({X})) alors")
            net = k + dx
            for _ in range(max(net, 0)):
                lines.append("    "*(indent+1) + f"poser(->{X})")
            for op in other_inc:
                lines.append("    "*(indent+1) + op)
            lines.append("    "*indent + "sinon")
            # x > k: annuler
            for _ in range(k):
                lines.append("    "*(indent+1) + f"poser(->{X})")
            lines.append("    "*indent + "finsi")
            return

        lines.append("    "*indent + f"si (non est_vide({X})) alors")
        lines.append("    "*(indent+1) + f"retirer(->{X})")
        rec(depth+1, indent+1)
        lines.append("    "*indent + "sinon")
        for _ in range(depth):
            lines.append("    "*(indent+1) + f"poser(->{X})")
        lines.append("    "*indent + "finsi")

    rec(0, 0)
    return lines


# BUG FIX #4: condition <=k
def _pseudocode_le_k(xvar: str, k: int, rule_deltas: Dict[str,int]) -> List[str]:
    """
    Condition x<=k.
    Exemple b<=1, b<-b+1 (attendu PDF):
      si (est_vide(bleue)) alors
        pose(->bleue)
      sinon
        retirer(->bleue)
        si (est_vide(bleue)) alors   <- x était 1
          pose(->bleue)
          pose(->bleue)
        sinon                         <- x > 1
          pose(->bleue)              <- restaurer
        finsi
    """
    X = _n(xvar)
    dx = rule_deltas.get(xvar, 0)

    other_ops: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d > 0:
            for _ in range(d):
                other_ops.append(f"poser(->{_n(v)})")
        elif d < 0:
            for _ in range(-d):
                other_ops.append(f"retirer(->{_n(v)})")

    lines: List[str] = []

    def emit_apply(indent: int, depth: int):
        net = depth + dx
        for _ in range(max(net, 0)):
            lines.append("    "*indent + f"poser(->{X})")
        for op in other_ops:
            lines.append("    "*indent + op)

    def rec(depth: int, indent: int):
        """
        À ce point on vient de retirer 1 jeton (depth retraits au total).
        On teste si vide → x était exactement depth → appliquer.
        Sinon → si depth < k, retirer encore et récurser.
                sinon x > k → restaurer tous les retraits.
        """
        lines.append("    "*indent + f"si (est_vide({X})) alors")
        emit_apply(indent+1, depth)
        lines.append("    "*indent + "sinon")
        if depth < k:
            # retirer avant le prochain si(est_vide), au niveau sinon courant
            lines.append("    "*(indent+1) + f"retirer(->{X})")
            rec(depth+1, indent+1)
            lines.append("    "*indent + "finsi")
        else:
            # x > k: annuler les depth retraits effectués
            for _ in range(depth):
                lines.append("    "*(indent+1) + f"poser(->{X})")
            lines.append("    "*indent + "finsi")

    lines.append(f"si (est_vide({X})) alors")
    emit_apply(1, 0)
    lines.append("sinon")
    lines.append("    " + f"retirer(->{X})")
    rec(1, 1)
    lines.append("finsi")
    return lines


def _simple_condition_to_if(cond: str) -> Optional[str]:
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
    cond = rule.get("condition","")

    # BUG FIX #2: ==0
    eq0_var = _parse_eq_0(cond)
    if eq0_var:
        return _pseudocode_eq_0(eq0_var, deltas)

    # BUG FIX #3: ==k
    eq_k = _parse_eq_k(cond)
    if eq_k:
        xvar, k = eq_k
        return _pseudocode_eq_k(xvar, k, deltas)

    # BUG FIX #4: <=k
    le_k = _parse_le_k(cond)
    if le_k:
        xvar, k = le_k
        return _pseudocode_le_k(xvar, k, deltas)

    # Condition >=k
    ge = _parse_ge_k(cond)
    if ge:
        xvar, k = ge
        dx = deltas.get(xvar)

        # BUG FIX #1: delta positif avec >=k
        if dx is not None and dx > 0 and k >= 2:
            x0 = int(init_state.get(xvar, 0))
            if x0 == 0:
                return []
            return _ge_k_with_positive_delta(deltas, xvar, k)

        # Cas original: delta == -1 avec >=k
        if dx == -1 and k >= 2:
            x0 = int(init_state.get(xvar,0))
            if x0 == 0:
                return []
            if x0 < k:
                return _k_trick_full(deltas, xvar, k)
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

        # Fallback >=k autres cas
        dec_guard_vars_g: List[str] = []
        for v in sorted(deltas.keys()):
            d = deltas[v]
            if d < 0:
                dec_guard_vars_g += [v] * (-d)
        dec_ops, inc_ops = _emit_ops_for_deltas(deltas)
        actions = dec_ops + inc_ops
        if not actions:
            actions = ["// rien"]
        if dec_guard_vars_g:
            return _emit_guard_chain(dec_guard_vars_g, actions, base_indent=0)
        return actions

    # Conditions simples >=1 / <1
    if_line = _simple_condition_to_if(cond)
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
        ge1 = _parse_ge_1(cond)
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

    # fallback brut
    lines = [f"si ({cond}) alors"]
    for op in actions:
        lines.append("    " + op)
    lines.append("finsi")
    return lines

def generate_pseudocode(problem: Dict[str,Any]) -> str:
    init_state = dict(problem.get("init",{}))
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

    prob_norm = {"vars": vars_}
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
