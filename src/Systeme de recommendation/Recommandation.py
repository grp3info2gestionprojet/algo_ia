"""
recommandation.py
=================
Système de recommandation de la prochaine opération pour un code partiel,
en s'appuyant sur un code de référence valide comme oracle.

Trois types d'opérations recommandées :
  - AJOUTER    : ajouter une instruction en fin de code
  - SUPPRIMER  : supprimer une instruction existante (à n'importe quelle position)
  - REMPLACER  : remplacer une instruction existante par une autre

Règles :
  1. Une seule recommandation est proposée à la fois (la meilleure).
  2. Règle de sécurité Retirer : si la meilleure action est Retirer(X) et qu'il
     n'existe pas de bloc "SI NON Est_vide(X)" ouvert et actif dans le contexte
     courant, on recommande d'abord d'ajouter "SI NON Est_vide(X)".
  3. Détection d'impasse : si aucun ajout n'améliore significativement la
     situation, des suppressions et remplacements sont aussi évalués.
"""

from Algorithme_Interpreter import AlgorithmeInterpreter
from contre_exemple import GenerateurContreExemples


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
COULEURS = ['B', 'J', 'R', 'V']
NOM_COULEURS = {'B': 'Bleu', 'J': 'Jaune', 'R': 'Rouge', 'V': 'Vert'}

ALL_ACTIONS = {
    **{i: f"Ajouter({COULEURS[i]})" for i in range(4)},
    **{i+4: f"Retirer({COULEURS[i]})" for i in range(4)},
    **{i+8: f"SI Est_vide({COULEURS[i]})" for i in range(4)},
    **{i+12: f"SI NON Est_vide({COULEURS[i]})" for i in range(4)},
    16: "FIN_SI",
    17: "STOP",
}

# Seuil en dessous duquel on considère qu'on est en situation d'impasse
# et on active automatiquement les suggestions de suppression/remplacement
SEUIL_IMPASSE = 0.05


# ---------------------------------------------------------------------------
# Utilitaires structurels
# ---------------------------------------------------------------------------

def profondeur_si(code_ids):
    """Retourne le nombre de SI ouverts non fermés."""
    depth = 0
    for aid in code_ids:
        action = ALL_ACTIONS.get(aid, "")
        if action.startswith("SI "):
            depth += 1
        elif action == "FIN_SI":
            depth -= 1
    return depth


def fermeture_minimale(code_ids):
    """Suffixe minimal pour fermer les SI ouverts et terminer avec STOP."""
    depth = profondeur_si(code_ids)
    return [16] * depth + [17]


def instructions_valides_apres(code_ids):
    """Instructions syntaxiquement légales à ajouter en fin de code."""
    depth = profondeur_si(code_ids)
    valides = []
    for aid, action in ALL_ACTIONS.items():
        if action == "FIN_SI" and depth == 0:
            continue
        if action == "STOP" and depth != 0:
            continue
        valides.append(aid)
    return valides


def code_valide_apres_suppression(code_ids, position):
    """
    Vérifie que supprimer l'instruction à `position` donne un code
    structurellement cohérent (pas de FIN_SI orphelin, profondeur >= 0).
    Retourne le code résultant ou None si invalide.
    """
    if position < 0 or position >= len(code_ids):
        return None

    code_sans = code_ids[:position] + code_ids[position + 1:]

    # Vérification : la profondeur ne doit jamais devenir négative
    depth = 0
    for aid in code_sans:
        action = ALL_ACTIONS.get(aid, "")
        if action.startswith("SI "):
            depth += 1
        elif action == "FIN_SI":
            depth -= 1
            if depth < 0:
                return None  # FIN_SI sans SI correspondant

    return code_sans


def instructions_valides_en_position(code_ids, position):
    """
    Instructions qu'il est légal de mettre à `position` dans le code,
    en tenant compte du contexte avant et après cette position.
    """
    code_avant = code_ids[:position]
    code_apres = code_ids[position + 1:]  # on ignore l'instruction actuelle

    depth_avant = profondeur_si(code_avant)

    valides = []
    for aid, action in ALL_ACTIONS.items():
        # Contraintes liées à la position
        if action == "FIN_SI" and depth_avant == 0:
            continue  # pas de SI ouvert avant cette position
        if action == "STOP" and depth_avant != 0:
            continue  # des SI sont encore ouverts

        # Vérifier que le code_apres reste cohérent après ce remplacement
        code_test = code_avant + [aid] + code_apres
        depth = depth_avant + (1 if action.startswith("SI ") else
                                -1 if action == "FIN_SI" else 0)

        # Vérifier que la profondeur ne devient jamais négative dans la suite
        depth_check = depth
        valide_suite = True
        for a in code_apres:
            act = ALL_ACTIONS.get(a, "")
            if act.startswith("SI "):
                depth_check += 1
            elif act == "FIN_SI":
                depth_check -= 1
                if depth_check < 0:
                    valide_suite = False
                    break

        if valide_suite:
            valides.append(aid)

    return valides


def couleur_si_actif(code_ids):
    """Retourne la couleur du SI le plus récent encore ouvert, ou None."""
    si_stack = []
    for aid in code_ids:
        action = ALL_ACTIONS.get(aid, "")
        if action.startswith("SI "):
            for c in COULEURS:
                if f"({c})" in action:
                    si_stack.append(c)
                    break
        elif action == "FIN_SI" and si_stack:
            si_stack.pop()
    return si_stack[-1] if si_stack else None


# ---------------------------------------------------------------------------
# Règle de sécurité : Retirer(X) doit être précédé d'un SI NON Est_vide(X)
# ---------------------------------------------------------------------------

def couleur_non_est_vide_actif(code_ids):
    """
    Retourne l'ensemble des couleurs X pour lesquelles un bloc
    'SI NON Est_vide(X)' est actuellement ouvert (empilé mais pas encore fermé).
    """
    si_stack = []
    for aid in code_ids:
        action = ALL_ACTIONS.get(aid, "")
        if action.startswith("SI NON Est_vide("):
            for c in COULEURS:
                if f"({c})" in action:
                    si_stack.append(c)
                    break
        elif action.startswith("SI Est_vide("):
            si_stack.append(None)  # SI d'une autre nature : on empile None
        elif action == "FIN_SI" and si_stack:
            si_stack.pop()
    return set(c for c in si_stack if c is not None)


def appliquer_regle_securite_retirer(meilleure_action_id, code_partiel):
    """
    Si la meilleure action est Retirer(X) et qu'il n'y a pas de
    'SI NON Est_vide(X)' ouvert dans le contexte courant, retourne l'id
    du 'SI NON Est_vide(X)' à ajouter en premier.
    Sinon retourne None (pas de substitution nécessaire).
    """
    action = ALL_ACTIONS.get(meilleure_action_id, "")
    if not action.startswith("Retirer("):
        return None

    # Quelle couleur ?
    couleur = None
    for c in COULEURS:
        if f"({c})" in action:
            couleur = c
            break
    if couleur is None:
        return None

    # Y a-t-il déjà un SI NON Est_vide(couleur) ouvert ?
    proteges = couleur_non_est_vide_actif(code_ids=code_partiel)
    if couleur in proteges:
        return None  # déjà protégé, pas besoin d'interposer un SI

    # Retourner l'id de SI NON Est_vide(couleur)
    idx_couleur = COULEURS.index(couleur)
    return 12 + idx_couleur  # ids 12-15 = SI NON Est_vide(B/J/R/V)


# ---------------------------------------------------------------------------
# Mesure comportementale
# ---------------------------------------------------------------------------

def taux_correspondance(code_ids, oracle, interpreter):
    """
    Exécute le code (complété avec fermeture minimale) sur tous les états
    de l'oracle. Retourne (nb_corrects, nb_total, taux).
    """
    code_complet = code_ids + fermeture_minimale(code_ids)
    nb_corrects = 0

    for exemple in oracle:
        etat_initial = exemple["etat_initial"]
        etat_attendu = exemple["etat_final"]
        plateau, _, succes = interpreter.executer(code_complet, etat_initial)
        if succes and tuple(plateau) == etat_attendu:
            nb_corrects += 1

    total = len(oracle)
    return nb_corrects, total, nb_corrects / total if total else 0.0


# ---------------------------------------------------------------------------
# Heuristiques contextuelles
# ---------------------------------------------------------------------------

def bonus_contexte_ajout(action_id, code_partiel):
    """Bonus/malus pour un ajout en fin de code."""
    action = ALL_ACTIONS.get(action_id, "")
    score = 0.0
    depth = profondeur_si(code_partiel)
    c_si = couleur_si_actif(code_partiel)
    derniere = ALL_ACTIONS.get(code_partiel[-1], "") if code_partiel else ""

    if c_si and f"({c_si})" in action:
        score += 0.2
    if action == "FIN_SI" and derniere.startswith("SI "):
        score -= 0.4  # bloc SI vide
    if action.startswith("SI ") and depth >= 3:
        score -= 0.3  # trop imbriqué
    if action.startswith("SI ") and derniere.startswith("SI "):
        score -= 0.2  # deux SI consécutifs sans action

    return score


# ---------------------------------------------------------------------------
# Génération des opérations candidates
# ---------------------------------------------------------------------------

def candidats_ajout(code_partiel, oracle, interpreter, taux_base):
    """Génère tous les candidats de type AJOUTER."""
    candidats = []
    for aid in instructions_valides_apres(code_partiel):
        code_candidat = code_partiel + [aid]
        nb_corrects, nb_total, taux = taux_correspondance(code_candidat, oracle, interpreter)
        delta = taux - taux_base

        score_comportemental = taux * 2.0 + delta * 3.0
        score_structural = 0.0
        if ALL_ACTIONS[aid] == "STOP" and taux > 0:
            score_structural += 0.3
        if ALL_ACTIONS[aid] == "FIN_SI":
            score_structural += 0.1
        score_contexte = bonus_contexte_ajout(aid, code_partiel)

        score = score_comportemental + score_structural + score_contexte

        candidats.append({
            "type": "AJOUTER",
            "action_id": aid,
            "action_nom": ALL_ACTIONS[aid],
            "position": len(code_partiel),
            "score": round(score, 4),
            "taux": round(taux, 4),
            "delta": round(delta, 4),
            "nb_corrects": nb_corrects,
            "nb_total": nb_total,
            "code_resultant": code_candidat,
        })
    return candidats


def candidats_suppression(code_partiel, oracle, interpreter, taux_base):
    """Génère tous les candidats de type SUPPRIMER."""
    candidats = []
    for pos in range(len(code_partiel)):
        code_sans = code_valide_apres_suppression(code_partiel, pos)
        if code_sans is None:
            continue  # suppression invalide structurellement

        nb_corrects, nb_total, taux = taux_correspondance(code_sans, oracle, interpreter)
        delta = taux - taux_base

        # On ne suggère une suppression que si elle améliore ou au moins ne dégrade pas
        if delta < -0.02:
            continue

        score = taux * 2.0 + delta * 3.0
        # Léger bonus si on supprime une instruction récente (plus intuitive pour l'élève)
        recence = (pos / len(code_partiel)) if code_partiel else 0
        score += recence * 0.1

        candidats.append({
            "type": "SUPPRIMER",
            "action_id": code_partiel[pos],
            "action_nom": ALL_ACTIONS.get(code_partiel[pos], "?"),
            "position": pos,
            "score": round(score, 4),
            "taux": round(taux, 4),
            "delta": round(delta, 4),
            "nb_corrects": nb_corrects,
            "nb_total": nb_total,
            "code_resultant": code_sans,
        })
    return candidats


def candidats_remplacement(code_partiel, oracle, interpreter, taux_base):
    """Génère tous les candidats de type REMPLACER."""
    candidats = []
    for pos in range(len(code_partiel)):
        action_actuelle = ALL_ACTIONS.get(code_partiel[pos], "")
        for aid in instructions_valides_en_position(code_partiel, pos):
            if aid == code_partiel[pos]:
                continue  # pas de remplacement par la même instruction

            code_remplace = code_partiel[:pos] + [aid] + code_partiel[pos + 1:]
            nb_corrects, nb_total, taux = taux_correspondance(
                code_remplace, oracle, interpreter
            )
            delta = taux - taux_base

            # On ne suggère un remplacement que s'il améliore
            if delta <= 0.02:
                continue

            score = taux * 2.0 + delta * 3.5  # poids légèrement plus fort que l'ajout
            # Bonus si le remplacement est sur une position récente
            recence = (pos / len(code_partiel)) if code_partiel else 0
            score += recence * 0.1

            candidats.append({
                "type": "REMPLACER",
                "action_id": aid,
                "action_nom": ALL_ACTIONS[aid],
                "position": pos,
                "action_remplacee": action_actuelle,
                "score": round(score, 4),
                "taux": round(taux, 4),
                "delta": round(delta, 4),
                "nb_corrects": nb_corrects,
                "nb_total": nb_total,
                "code_resultant": code_remplace,
            })
    return candidats


# ---------------------------------------------------------------------------
# Détection d'impasse
# ---------------------------------------------------------------------------

def est_en_impasse(taux_base, meilleur_delta_ajout):
    """
    Retourne True si aucun ajout n'améliore significativement la situation,
    ce qui indique qu'il faut probablement corriger une erreur antérieure.
    """
    return meilleur_delta_ajout < SEUIL_IMPASSE and taux_base < 0.95


# ---------------------------------------------------------------------------
# Système de recommandation
# ---------------------------------------------------------------------------

class SystemeRecommandation:
    def __init__(self, interpreter=None):
        self.interpreter = interpreter if interpreter else AlgorithmeInterpreter()
        self.generateur = GenerateurContreExemples(self.interpreter)

    def construire_oracle(self, code_reference, nb_etats=150, max_valeur=5):
        """Génère l'oracle depuis le code de référence."""
        oracle = self.generateur.generer_oracle(
            code_reference, nb_etats=nb_etats, max_valeur=max_valeur
        )
        if not oracle:
            raise ValueError(
                "Le code de référence n'a produit aucun résultat valide. "
                "Vérifiez qu'il est correct."
            )
        return oracle

    def recommander(self, code_partiel, oracle, verbose=False):
        """
        Analyse le code partiel et retourne LA meilleure opération à effectuer.

        En situation normale : évalue uniquement les ajouts.
        En situation d'impasse (aucun ajout n'améliore) : évalue aussi
        les suppressions et les remplacements.

        Règle de sécurité : si la meilleure action est Retirer(X) sans bloc
        SI NON Est_vide(X) ouvert, on substitue la recommandation par
        SI NON Est_vide(X) à ajouter en premier.

        Paramètres
        ----------
        code_partiel : list[int]
        oracle : list[dict]
        verbose : bool

        Retourne
        --------
        dict avec :
          - "taux_base"         : float, correspondance actuelle
          - "impasse"           : bool
          - "recommandation"    : dict, la meilleure opération unique
          - "substituee"        : bool, True si règle de sécurité appliquée
          - "recommandation_originale" : dict|None, l'action voulue avant substitution
        """
        _, _, taux_base = taux_correspondance(code_partiel, oracle, self.interpreter)

        # --- Code déjà correct : pas de recommandation ---
        if taux_base >= 1.0:
            return {
                "taux_base": taux_base,
                "impasse": False,
                "recommandation": None,
                "substituee": False,
                "recommandation_originale": None,
                "code_correct": True,
            }

        # --- Candidats ajout (toujours calculés) ---
        ajouts = candidats_ajout(code_partiel, oracle, self.interpreter, taux_base)
        meilleur_delta_ajout = max((c["delta"] for c in ajouts), default=0.0)

        impasse = est_en_impasse(taux_base, meilleur_delta_ajout) and len(code_partiel) > 0

        # --- Candidats suppression et remplacement (si impasse) ---
        suppressions = []
        remplacements = []
        if impasse:
            suppressions = candidats_suppression(
                code_partiel, oracle, self.interpreter, taux_base
            )
            remplacements = candidats_remplacement(
                code_partiel, oracle, self.interpreter, taux_base
            )

        tous_candidats = ajouts + suppressions + remplacements
        tous_candidats.sort(key=lambda x: x["score"], reverse=True)

        if verbose:
            self._afficher_tableau(tous_candidats[:8], taux_base, impasse)

        if not tous_candidats:
            return {
                "taux_base": taux_base,
                "impasse": impasse,
                "recommandation": None,
                "substituee": False,
                "recommandation_originale": None,
            }

        meilleure = tous_candidats[0]

        # --- Règle de sécurité Retirer(X) ---
        substituee = False
        originale = None
        if meilleure["type"] == "AJOUTER":
            id_si = appliquer_regle_securite_retirer(meilleure["action_id"], code_partiel)
            if id_si is not None:
                # On substitue par SI NON Est_vide(X)
                originale = meilleure
                substituee = True
                couleur = ALL_ACTIONS[id_si].replace("SI NON Est_vide(", "").rstrip(")")
                meilleure = {
                    "type": "AJOUTER",
                    "action_id": id_si,
                    "action_nom": ALL_ACTIONS[id_si],
                    "position": len(code_partiel),
                    "score": meilleure["score"],  # hérite du score de Retirer(X)
                    "taux": meilleure["taux"],
                    "delta": meilleure["delta"],
                    "nb_corrects": meilleure["nb_corrects"],
                    "nb_total": meilleure["nb_total"],
                    "code_resultant": code_partiel + [id_si],
                    "_substitution_reason": (
                        f"Retirer({couleur}) nécessite d'abord une protection "
                        f"SI NON Est_vide({couleur})"
                    ),
                }

        return {
            "taux_base": taux_base,
            "impasse": impasse,
            "recommandation": meilleure,
            "substituee": substituee,
            "recommandation_originale": originale,
            "code_correct": False,
        }

    def afficher_recommandations(self, code_partiel, oracle):
        """Affiche la recommandation unique de façon lisible pour l'élève."""
        print("\n" + "─" * 68)
        print(f"  Code partiel ({len(code_partiel)} instruction(s)) :")
        if code_partiel:
            depth = 0
            for i, aid in enumerate(code_partiel):
                action = ALL_ACTIONS.get(aid, "?")
                if action == "FIN_SI":
                    depth = max(0, depth - 1)
                indent = "  " * depth
                print(f"    [{i}] {indent}{action}")
                if action.startswith("SI "):
                    depth += 1
        else:
            print("    (vide)")

        resultat = self.recommander(code_partiel, oracle, verbose=True)

        taux_base = resultat["taux_base"]
        impasse = resultat["impasse"]
        rec = resultat["recommandation"]
        substituee = resultat["substituee"]
        originale = resultat["recommandation_originale"]

        print(f"\n  Correspondance actuelle : {self._barre_progression(taux_base)} "
              f"{taux_base*100:.1f}%")

        # --- Code déjà correct ---
        if resultat.get("code_correct"):
            print("\n  ✅ Le code est correct ! Il produit exactement le même")
            print("     comportement que le code de référence sur tous les états.")
            print()
            return resultat

        if impasse:
            print(f"\n  ⚠️  IMPASSE : aucun ajout n'améliore la situation.")
            print(f"     Une correction du code existant est nécessaire.")

        if rec is None:
            print("\n  ✅ Aucune recommandation : le code semble déjà optimal.")
            print()
            return resultat

        print(f"\n  💡 Recommandation :\n")

        type_label = {"AJOUTER": "➕", "SUPPRIMER": "🗑️ ", "REMPLACER": "🔄"}.get(
            rec["type"], "  "
        )

        if rec["type"] == "AJOUTER":
            print(f"     {type_label} Ajouter  [{rec['action_id']:2d}] {rec['action_nom']}")
        elif rec["type"] == "SUPPRIMER":
            print(f"     {type_label} Supprimer la ligne {rec['position']} "
                  f"[{rec['action_id']:2d}] {rec['action_nom']}")
        else:
            print(f"     {type_label} Remplacer la ligne {rec['position']} : "
                  f"{rec['action_remplacee']} → {rec['action_nom']}")

        barre = self._barre_progression(rec["taux"])
        signe = "+" if rec["delta"] >= 0 else ""
        print(f"\n     Résultat attendu : {barre} {rec['taux']*100:.1f}%  "
              f"({signe}{rec['delta']*100:.1f}% par rapport à maintenant)")
        print(f"     {rec['nb_corrects']}/{rec['nb_total']} états de l'oracle "
              f"correctement reproduits après cette opération.")

        # Message de substitution si règle de sécurité appliquée
        if substituee and originale:
            print(f"\n     ⚠️  Note : l'action optimale serait "
                  f"'{originale['action_nom']}', mais celle-ci risque")
            print(f"        d'échouer si la case est vide. On recommande d'abord")
            print(f"        de protéger l'action avec un bloc conditionnel.")

        print()
        return resultat

    # ------------------------------------------------------------------
    # Méthodes privées
    # ------------------------------------------------------------------

    def _afficher_tableau(self, candidats, taux_base, impasse):
        titre = "IMPASSE — ajouts + suppressions + remplacements" if impasse else "AJOUTS"
        print(f"\n  [{titre}]")
        print(f"  {'Type':<10} {'Opération':<38} {'Correct':>9} {'Delta':>8} {'Score':>8}")
        print("  " + "─" * 73)
        for r in candidats:
            if r["type"] == "AJOUTER":
                op = f"+ {r['action_nom']}"
            elif r["type"] == "SUPPRIMER":
                op = f"- ligne {r['position']} {r['action_nom']}"
            else:
                op = f"~ ligne {r['position']} {r['action_remplacee']} → {r['action_nom']}"
            delta_str = f"+{r['delta']*100:.1f}%" if r['delta'] >= 0 else f"{r['delta']*100:.1f}%"
            print(f"  {r['type']:<10} {op:<38} "
                  f"{r['nb_corrects']:>4}/{r['nb_total']:<4} "
                  f"{delta_str:>8} {r['score']:>8.4f}")
        nb_total = candidats[0]["nb_total"] if candidats else "?"
        print(f"  {'[actuel]':<10} {'':38} "
              f"{'':>4}/{nb_total:<4} {'(base)':>8} {taux_base:>8.4f}")

    @staticmethod
    def _barre_progression(taux, largeur=10):
        n = round(taux * largeur)
        return "[" + "█" * n + "░" * (largeur - n) + "]"


# ---------------------------------------------------------------------------
# Exemple d'utilisation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    interpreter = AlgorithmeInterpreter()
    systeme = SystemeRecommandation(interpreter)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          SYSTÈME DE RECOMMANDATION D'INSTRUCTIONS            ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # ------------------------------------------------------------------
    # Référence : SI NON Est_vide(B) → Retirer(B) → FIN_SI → STOP
    # ------------------------------------------------------------------
    code_reference = [12, 4, 16, 17]
    print(f"\nCode de référence :")
    interpreter.print_algo(code_reference)
    oracle = systeme.construire_oracle(code_reference, nb_etats=150, max_valeur=5)
    print(f"Oracle : {len(oracle)} états valides.")

    # ------------------------------------------------------------------
    # CAS 1 : construction correcte pas à pas
    # ------------------------------------------------------------------
    print("\n" + "═"*68)
    print("  CAS 1 : construction correcte pas à pas")
    print("═"*68)
    systeme.afficher_recommandations([], oracle)
    systeme.afficher_recommandations([12], oracle)
    systeme.afficher_recommandations([12, 4], oracle)
    systeme.afficher_recommandations([12, 4, 16], oracle)
