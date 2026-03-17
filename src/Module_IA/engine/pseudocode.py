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
    Génère un pseudo-code "k-trick" général (k>=1) pour exprimer x>=k avec seulement:
      - est_vide / non est_vide
      - retirer / poser

    Généralisation pour tout delta d négatif sur xvar (pas seulement -1) :
    Soit d = rule_deltas[xvar] (ex: -2 pour b-2).

    Stratégie en deux phases :
    Phase 1 — vérification de x >= k via k retraits de test consécutifs :
      On tente de retirer k jetons un par un depuis x.
      - Si l'un des retraits échoue (x est vide) => condition fausse => on repose les jetons déjà retirés.
      - Si tous réussissent => condition vraie.
    Phase 2 — application des updates de la règle (si condition vraie) :
      On a déjà retiré k jetons de x (test). L'update veut retirer |d| jetons de x au total.
      - Si d == -k : les k retraits de test font exactement l'update => rien à faire de plus sur x.
      - Si |d| < k  : on a trop retiré => reposer (k - |d|) jetons sur x.
      - Si |d| > k  : on n'a pas assez retiré => retirer (|d| - k) jetons de plus sur x
                      (sécurisé par des gardes non est_vide).
      On applique ensuite les updates sur les autres variables (sécurisés par gardes).
    """
    X = _n(xvar)
    dx = rule_deltas.get(xvar, 0)   # delta sur la variable de condition (négatif ou nul)
    abs_dx = abs(dx) if dx < 0 else 0

    # lignes d'annulation (undo) des updates hors x (pour le cas condition fausse)
    undo_x_lines: List[str] = []  # annulation de x si on avait avancé
    undo_other_lines: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d > 0:
            for _ in range(d):
                undo_other_lines.append(f"retirer(→{_n(v)})")
        elif d < 0:
            for _ in range(-d):
                undo_other_lines.append(f"poser(→{_n(v)})")

    # ops sur les autres variables (updates hors x)
    other_dec_ops: List[str] = []
    other_inc_ops: List[str] = []
    for v in sorted(rule_deltas.keys()):
        if v == xvar:
            continue
        d = rule_deltas[v]
        if d < 0:
            for _ in range(-d):
                other_dec_ops.append(f"retirer(→{_n(v)})")
        elif d > 0:
            for _ in range(d):
                other_inc_ops.append(f"poser(→{_n(v)})")

    lines: List[str] = []

    # ── Phase 1 : tenter de retirer k jetons de test depuis x ──────────────────
    # On construit une chaîne imbriquée de k blocs si (non est_vide(X)) alors
    # Après k retraits réussis :
    #   - Appliquer les autres updates
    #   - Ajuster x selon la différence entre k retraits de test et |d| souhaité
    # En cas d'échec au i-ème retrait : reposer i jetons déjà retirés

    def build_test_chain(depth: int, indent: int) -> None:
        """
        depth = nombre de retraits de test déjà effectués avec succès.
        On tente d'en effectuer un de plus si depth < k.
        """
        if depth == k:
            # Tous les k retraits de test ont réussi => condition x >= k vérifiée
            # Appliquer les updates sur les autres variables (retraits sécurisés)
            other_vars_dec = [v for v in sorted(rule_deltas.keys())
                              if v != xvar and rule_deltas[v] < 0]
            dec_guard_vars: List[str] = []
            for v in other_vars_dec:
                dec_guard_vars += [v] * (-rule_deltas[v])

            other_ops = other_dec_ops + other_inc_ops
            if dec_guard_vars:
                guarded = _emit_guard_chain(dec_guard_vars, other_ops, base_indent=indent)
                lines.extend(guarded)
            else:
                for op in other_ops:
                    lines.append("    "*indent + op)

            # Ajuster x : on a retiré k jetons de test, on veut un effet net de |d|
            net_x = k - abs_dx   # positif => trop retiré => reposer ; négatif => pas assez => retirer
            if net_x > 0:
                # reposer net_x jetons
                for _ in range(net_x):
                    lines.append("    "*indent + f"poser(→{X})")
            elif net_x < 0:
                # retirer (-net_x) jetons de plus (sécurisé par gardes)
                extra_removes = [xvar] * (-net_x)
                extra_ops = [f"retirer(→{X})"] * (-net_x)
                guarded = _emit_guard_chain(extra_removes, extra_ops, base_indent=indent)
                lines.extend(guarded)
            # si net_x == 0 : rien à faire, les k retraits de test suffisent
            return

        # Tenter le (depth+1)-ième retrait de test
        lines.append("    "*indent + f"si (non est_vide({X})) alors")
        lines.append("    "*(indent+1) + f"retirer(→{X})")
        build_test_chain(depth + 1, indent + 1)
        lines.append("    "*indent + "sinon")
        # Échec : reposer les `depth` jetons déjà retirés
        for _ in range(depth):
            lines.append("    "*(indent+1) + f"poser(→{X})")
        lines.append("    "*indent + "finsi")

    build_test_chain(0, 0)

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

    # Cas condition x>=k avec update qui retire des jetons de x (delta négatif quelconque)
    # Généralisation : tout delta négatif sur xvar (pas seulement -1)
    # On utilise toujours le k-trick pour traduire x>=k en est_vide/non est_vide
    if ge:
        xvar, k = ge
        dx = deltas.get(xvar, 0)
        if dx < 0 and k >= 1:
            return _k_trick_full(deltas, xvar, k)

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