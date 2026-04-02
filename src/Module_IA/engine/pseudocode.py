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

# BUG FIX 2 : condition ==0
def _parse_eq_0(cond: str) -> Optional[str]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)==0", c)
    return m.group(1) if m else None

# BUG FIX 3 : condition ==N (N>0)
def _parse_eq_k(cond: str) -> Optional[Tuple[str,int]]:
    c = (cond or "").replace(" ", "")
    m = re.fullmatch(r"([a-zA-Z_]\w*)==(\d+)", c)
    if not m:
        return None
    k = int(m.group(2))
    if k == 0:
        return None
    return m.group(1), k

# BUG FIX 4 : condition <=N
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
                dec_ops.append(f"retirer(→{_n(v)})")
        elif d > 0:
            for _ in range(d):
                inc_ops.append(f"poser(→{_n(v)})")
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
                undo_lines.append(f"retirer(→{_n(v)})")
        elif d < 0:
            for _ in range(-d):
                undo_lines.append(f"poser(→{_n(v)})")
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
            lines.append("    "*indent + f"poser(→{X})")
        for u in undo_lines:
            lines.append("    "*indent + u)

    def emit_valid(indent: int):
        for _ in range(extra):
            lines.append("    "*indent + f"poser(→{X})")

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
        lines.append("    "*(indent+1) + f"retirer(→{X})")
        rec(depth+1, removed+1, indent+1)
        lines.append("    "*indent + "sinon")
        emit_invalid(indent+1, removed)
        lines.append("    "*indent + "finsi")

    rec(0, 0, 1)
    lines.append("finsi")
    return lines


# BUG FIX 1 : condition >=k avec update + (delta positif sur x)
def _ge_k_with_positive_delta(rule_deltas: Dict[str,int], xvar: str, k: int) -> List[str]:
    """
    Condition x>=k, update x <- x+N (delta>0).

    Logique (ex. k=2, dx=+1) :
      si (non est_vide(x)) alors       ← x >= 1
        retirer(→x)                    ← test: retire 1 jeton
        si (non est_vide(x)) alors     ← x >= 2 confirmé
          poser(→x)                    ← restaure retrait de test
          poser(→x) * dx               ← applique l'update (+dx)
          [autres ops]
        sinon                          ← x était 1 < k, invalide
          poser(→x)                    ← restaure
        finsi
      sinon
      finsi

    Généralisation : (k-1) retraits imbriqués de test.
    """
    X = _n(xvar)
    dx = rule_deltas.get(xvar, 0)

    other_ops: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d < 0:
            for _ in range(-d):
                other_ops.append(f"retirer(→{_n(v)})")
        elif d > 0:
            for _ in range(d):
                other_ops.append(f"poser(→{_n(v)})")

    tests_needed = k - 1  # nb de retraits de test
    lines: List[str] = []

    def emit_apply(indent: int, tokens_removed: int):
        """Restaure les retraits de test + applique dx posers + autres ops."""
        for _ in range(tokens_removed + dx):
            lines.append("    "*indent + f"poser(→{X})")
        for op in other_ops:
            lines.append("    "*indent + op)

    def emit_restore(indent: int, tokens_removed: int):
        """Restaure les retraits de test (invalide)."""
        for _ in range(tokens_removed):
            lines.append("    "*indent + f"poser(→{X})")

    def rec(depth: int, removed: int, indent: int):
        """depth = nb de retraits déjà faits."""
        if depth == tests_needed:
            # On a retiré (k-1) jetons. x>=k ssi x non vide maintenant.
            lines.append("    "*indent + f"si (non est_vide({X})) alors")
            emit_apply(indent+1, removed)
            lines.append("    "*indent + "sinon")
            emit_restore(indent+1, removed)
            lines.append("    "*indent + "finsi")
            return
        # Besoin d'un retrait de test supplémentaire
        lines.append("    "*indent + f"si (non est_vide({X})) alors")
        lines.append("    "*(indent+1) + f"retirer(→{X})")
        rec(depth+1, removed+1, indent+1)
        lines.append("    "*indent + "sinon")
        emit_restore(indent+1, removed)
        lines.append("    "*indent + "finsi")

    if tests_needed == 0:
        # k=1 : x>=1 => juste vérifier non vide puis appliquer
        lines.append(f"si (non est_vide({X})) alors")
        emit_apply(1, 0)
        lines.append("sinon")
        lines.append("finsi")
    else:
        # Premier test : x >= 1
        lines.append(f"si (non est_vide({X})) alors")
        lines.append("    " + f"retirer(→{X})")
        rec(1, 1, 1)
        lines.append("sinon")
        lines.append("finsi")
    return lines


# BUG FIX 3 : condition ==N (N>0)
def _eq_k_pseudocode(rule_deltas: Dict[str,int], xvar: str, k: int) -> List[str]:
    """
    Condition x==k (k>=1).
    On retire k jetons. Si x vide après => x était exactement k => valide.
    Si x non vide après => x > k => invalide. Si on échoue avant => x < k => invalide.
    """
    X = _n(xvar)
    dx = rule_deltas.get(xvar, 0)

    other_ops: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d < 0:
            for _ in range(-d):
                other_ops.append(f"retirer(→{_n(v)})")
        elif d > 0:
            for _ in range(d):
                other_ops.append(f"poser(→{_n(v)})")

    lines: List[str] = []

    def emit_apply(indent: int, tokens_removed: int):
        net = tokens_removed + dx
        if net > 0:
            for _ in range(net):
                lines.append("    "*indent + f"poser(→{X})")
        elif net < 0:
            for _ in range(-net):
                lines.append("    "*indent + f"retirer(→{X})")
        for op in other_ops:
            lines.append("    "*indent + op)

    def emit_restore(indent: int, tokens_removed: int):
        for _ in range(tokens_removed):
            lines.append("    "*indent + f"poser(→{X})")

    def rec(depth: int, removed: int, indent: int):
        if depth == k:
            lines.append("    "*indent + f"si (est_vide({X})) alors")
            emit_apply(indent+1, removed)
            lines.append("    "*indent + "sinon")
            emit_restore(indent+1, removed)
            lines.append("    "*indent + "finsi")
            return
        lines.append("    "*indent + f"si (non est_vide({X})) alors")
        lines.append("    "*(indent+1) + f"retirer(→{X})")
        rec(depth+1, removed+1, indent+1)
        lines.append("    "*indent + "sinon")
        emit_restore(indent+1, removed)
        lines.append("    "*indent + "finsi")

    rec(0, 0, 0)
    return lines


# BUG FIX 4 : condition <=N
def _le_k_pseudocode(rule_deltas: Dict[str,int], xvar: str, k: int) -> List[str]:
    """
    Condition x<=k.
    Si x est vide => valide directement.
    Sinon on retire jusqu'à k jetons ; si vide avant/à k => valide ; sinon => invalide.
    """
    X = _n(xvar)
    dx = rule_deltas.get(xvar, 0)

    other_ops: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d < 0:
            for _ in range(-d):
                other_ops.append(f"retirer(→{_n(v)})")
        elif d > 0:
            for _ in range(d):
                other_ops.append(f"poser(→{_n(v)})")

    lines: List[str] = []

    def emit_apply(indent: int, tokens_removed: int):
        net = tokens_removed + dx
        if net > 0:
            for _ in range(net):
                lines.append("    "*indent + f"poser(→{X})")
        elif net < 0:
            for _ in range(-net):
                lines.append("    "*indent + f"retirer(→{X})")
        for op in other_ops:
            lines.append("    "*indent + op)

    def emit_restore(indent: int, tokens_removed: int):
        for _ in range(tokens_removed):
            lines.append("    "*indent + f"poser(→{X})")

    if k == 0:
        lines.append(f"si (est_vide({X})) alors")
        emit_apply(1, 0)
        lines.append("finsi")
        return lines

    lines.append(f"si (est_vide({X})) alors")
    emit_apply(1, 0)
    lines.append("sinon")

    def rec(depth: int, removed: int, indent: int):
        if depth == k:
            lines.append("    "*indent + f"si (est_vide({X})) alors")
            emit_apply(indent+1, removed)
            lines.append("    "*indent + "sinon")
            emit_restore(indent+1, removed)
            lines.append("    "*indent + "finsi")
            return
        lines.append("    "*indent + f"retirer(→{X})")
        lines.append("    "*indent + f"si (est_vide({X})) alors")
        emit_apply(indent+1, removed+1)
        lines.append("    "*indent + "sinon")
        rec(depth+1, removed+1, indent+1)
        lines.append("    "*indent + "finsi")

    rec(1, 1, 1)
    lines.append("finsi")
    return lines


def _simple_condition_to_if(cond: str) -> Optional[str]:
    v = _parse_ge_1(cond)
    if v:
        return f"si (non est_vide({_n(v)})) alors"
    v = _parse_lt_1(cond)
    if v:
        return f"si (est_vide({_n(v)})) alors"
    # BUG FIX 2 : ==0 → est_vide
    v = _parse_eq_0(cond)
    if v:
        return f"si (est_vide({_n(v)})) alors"
    return None

def pseudocode_for_rule(problem: Dict[str,Any], rule: Dict[str,Any], init_state: Dict[str,int]) -> List[str]:
    vars_ = list(problem["vars"])
    deltas = _updates_deltas(rule.get("updates",{}), vars_)
    cond = rule.get("condition","")

    ge = _parse_ge_k(cond)
    eq_k = _parse_eq_k(cond)
    le_k = _parse_le_k(cond)
    eq_0 = _parse_eq_0(cond)

    # Condition x>=k
    if ge:
        xvar, k = ge
        dx = deltas.get(xvar)

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

        # BUG FIX 1 : delta positif sur x
        if dx is not None and dx > 0:
            return _ge_k_with_positive_delta(deltas, xvar, k)

        # Fallback >=k autres cas
        dec_guard_vars2: List[str] = []
        for v in sorted(deltas.keys()):
            d = deltas[v]
            if d < 0:
                dec_guard_vars2 += [v] * (-d)
        dec_ops2, inc_ops2 = _emit_ops_for_deltas(deltas)
        inner2 = dec_ops2 + inc_ops2
        if dec_guard_vars2:
            return _emit_guard_chain(dec_guard_vars2, inner2, base_indent=0)
        return inner2 if inner2 else [f"// {cond}"]

    # BUG FIX 3 : condition ==N (N>0)
    if eq_k:
        xvar, k = eq_k
        return _eq_k_pseudocode(deltas, xvar, k)

    # BUG FIX 4 : condition <=N
    if le_k:
        xvar, k = le_k
        return _le_k_pseudocode(deltas, xvar, k)

    # BUG FIX 2 : condition ==0 (sécurité si non capturé par _simple_condition_to_if)
    if eq_0:
        xvar = eq_0
        dec_ops3, inc_ops3 = _emit_ops_for_deltas(deltas)
        actions3 = dec_ops3 + inc_ops3 or ["// rien"]
        lines3 = [f"si (est_vide({_n(xvar)})) alors"]
        for op in actions3:
            lines3.append("    " + op)
        lines3.append("finsi")
        return lines3

    # Conditions simples (>=1, <1)
    if_line = _simple_condition_to_if(cond)
    dec_guard_vars_s: List[str] = []
    for v in sorted(deltas.keys()):
        d = deltas[v]
        if d < 0:
            dec_guard_vars_s += [v] * (-d)
    dec_ops_s, inc_ops_s = _emit_ops_for_deltas(deltas)
    actions = dec_ops_s + inc_ops_s
    if not actions:
        actions = ["// rien"]

    if if_line:
        lines = [if_line]
        ge1 = _parse_ge_1(cond)
        if ge1 and ge1 in dec_guard_vars_s:
            dec_guard_vars_s.remove(ge1)
        if dec_guard_vars_s:
            guarded = _emit_guard_chain(dec_guard_vars_s, actions, base_indent=1)
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
