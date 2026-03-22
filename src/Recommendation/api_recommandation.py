from .Recommandation import SystemeRecommandation, ALL_ACTIONS

# ---------------------------------------------------------------------------
# Conversion blocs JS ↔ code_ids
# ---------------------------------------------------------------------------

COLOR_MAP = {'b': 0, 'j': 1, 'r': 2, 'v': 3}
COLOR_NAMES = {0: 'bleue', 1: 'jaune', 2: 'rouge', 3: 'verte'}


def blocks_to_code_ids(blocks):
    """
    Convertit la liste de blocs plats envoyée par le frontend
    en liste de code_ids attendue par AlgorithmeInterpreter.

    Types de blocs reconnus :
      poser         → 0-3   (Ajouter)
      retirer       → 4-7   (Retirer)
      if_empty      → 8-11  (SI Est_vide)
      if_not_empty  → 12-15 (SI NON Est_vide)
      sinon         → 18    (SINON)
      finsi         → 16
    Le STOP (17) est ajouté automatiquement en fin de liste.
    """
    code_ids = []
    for b in blocks:
        c = COLOR_MAP.get(b.get('color'), 0)
        t = b.get('type', '')
        if t == 'poser':
            code_ids.append(c)
        elif t == 'retirer':
            code_ids.append(c + 4)
        elif t in ('if_empty', 'if_empty_else'):
            code_ids.append(c + 8)
        elif t in ('if_not_empty', 'if_not_empty_else'):
            code_ids.append(c + 12)
        elif t == 'sinon':
            code_ids.append(18)
        elif t == 'finsi':
            code_ids.append(16)
    code_ids.append(17)  # STOP
    return code_ids


def code_ids_to_pseudocode(code_ids):
    """
    Convertit une liste de code_ids en pseudocode lisible pour le frontend.
    Retourne une chaîne multi-lignes numérotée.
    """
    lines = []
    depth = 0
    line_no = 1

    for action_id in code_ids:
        action = ALL_ACTIONS.get(action_id, '')
        if not action:
            continue

        if action == 'STOP':
            break

        indent = '    ' * depth

        if action == 'FIN_SI':
            depth = max(0, depth - 1)
            indent = '    ' * depth
            lines.append(f"{line_no}: {indent}finsi")
            line_no += 1

        elif action == 'SINON':
            depth = max(0, depth - 1)
            indent = '    ' * depth
            lines.append(f"{line_no}: {indent}sinon")
            line_no += 1
            depth += 1

        elif action.startswith('SI NON Est_vide('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}si non est_vide({c}) alors")
            line_no += 1
            depth += 1

        elif action.startswith('SI Est_vide('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}si est_vide({c}) alors")
            line_no += 1
            depth += 1

        elif action.startswith('Poser('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}poser(→{c})")
            line_no += 1

        elif action.startswith('Retirer('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}retirer(→{c})")
            line_no += 1

    return '\n'.join(lines) if lines else '(algorithme vide)'


def tronquer_code_partiel(code_ids):
    """
    Retire le STOP final et tous les FIN_SI qui le précèdent immédiatement,
    afin que le système de recommandation reçoive uniquement les instructions
    réellement saisies par l'étudiant, sans la fermeture automatique.
    """
    ids = list(code_ids)
    if ids and ids[-1] == 17:
        ids.pop()
    while ids and ids[-1] == 16:
        ids.pop()
    return ids


def recommandation_to_message(resultat):
    """
    Transforme le dict retourné par SystemeRecommandation.recommander()
    en un message lisible pour l'élève (affiché dans feedbackText).
    """
    if resultat.get("code_correct"):
        return "✅ Votre algorithme est correct !"

    rec = resultat.get("recommandation")
    if rec is None:
        return "Aucune recommandation disponible pour le moment."

    type_labels = {"AJOUTER": "➕ Ajouter", "SUPPRIMER": "🗑️ Supprimer", "REMPLACER": "🔄 Remplacer"}
    label = type_labels.get(rec["type"], rec["type"])

    if rec["type"] == "AJOUTER":
        return f"💡 <b>Prochaine action :</b> {label} <code>{rec['action_nom']}</code>"
    elif rec["type"] == "SUPPRIMER":
        return (f"💡 <b>Prochaine action :</b> {label} la ligne {rec['position']} "
                f"(<code>{rec['action_nom']}</code>)")
    else:
        return (f"💡 <b>Prochaine action :</b> {label} la ligne {rec['position']} : "
                f"<code>{rec['action_remplacee']}</code> → <code>{rec['action_nom']}</code>")


# ---------------------------------------------------------------------------
# Fonction principale appelée par les routes Flask
# ---------------------------------------------------------------------------

def analyser_code_etudiant(blocks, code_ids_correct, nb_etats=50, max_valeur=5):
    """
    Point d'entrée unique pour les routes Flask.

    Paramètres
    ----------
    blocks          : list[dict], blocs plats envoyés par le frontend
    code_ids_correct: list[int],  code de référence de l'exercice
    nb_etats        : int,        taille de l'oracle
    max_valeur      : int,        valeur max des cases dans l'oracle

    Retourne
    --------
    dict avec :
      "contre_exemple" : str | None   — message du contre-exemple trouvé
      "message"        : str          — recommandation lisible pour l'élève
      "pseudocode"     : str | None   — pseudocode du code de référence (si erreur)
      "student_code"   : str          — pseudocode du code de l'étudiant
    """
    code_ids_etudiant = blocks_to_code_ids(blocks)
    student_pseudocode = code_ids_to_pseudocode(code_ids_etudiant)

    systeme = SystemeRecommandation()
    oracle  = systeme.construire_oracle(code_ids_correct, nb_etats=nb_etats, max_valeur=max_valeur)

    # Contre-exemple (code complet avec STOP)
    contre_exemple_msg = systeme.generateur.tester_code(
        code_ids_etudiant, oracle, formater_message=True
    )

    # Recommandation (code partiel sans STOP ni FIN_SI de fermeture)
    code_partiel = tronquer_code_partiel(code_ids_etudiant)
    resultat = systeme.recommander(code_partiel, oracle, verbose=False)
    message  = recommandation_to_message(resultat)

    # Pseudocode de référence (seulement si le code est incorrect)
    pseudocode_ref = None
    if not resultat.get("code_correct"):
        pseudocode_ref = code_ids_to_pseudocode(code_ids_correct)

    return {
        "contre_exemple": contre_exemple_msg,
        "message":        message,
        "pseudocode":     pseudocode_ref,
        "student_code":   student_pseudocode,
    }