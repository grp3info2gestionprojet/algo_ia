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
        elif t == 'if_empty':
            code_ids.append(c + 8)
        elif t == 'if_not_empty':
            code_ids.append(c + 12)
        elif t == 'sinon':
            code_ids.append(18)   # SINON n'a pas de couleur associée
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

        elif action.startswith('Ajouter('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}poser(→{c})")
            line_no += 1

        elif action.startswith('Retirer('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}retirer(→{c})")
            line_no += 1

    return '\n'.join(lines) if lines else '(algorithme vide)'


def recommandation_to_message(resultat):
    """
    Transforme le dict retourné par SystemeRecommandation.recommander()
    en un message lisible pour l'élève (affiché dans feedbackText).
    """
    if resultat.get("code_correct"):
        return "✅ Votre algorithme est correct ! Il produit exactement le même comportement que la solution de référence."

    rec = resultat.get("recommandation")
    if rec is None:
        return "Aucune recommandation disponible pour le moment."

    taux_base = resultat.get("taux_base", 0)
    impasse   = resultat.get("impasse", False)
    substituee = resultat.get("substituee", False)
    originale  = resultat.get("recommandation_originale")

    parties = []

    # Taux de correspondance actuel
    pct = round(taux_base * 100, 1)
    parties.append(f"Correspondance actuelle avec la solution : <b>{pct}%</b> "
                   f"({rec['nb_corrects']}/{rec['nb_total']} cas corrects).")

    # Avertissement impasse
    if impasse:
        parties.append("⚠️ <b>Impasse détectée</b> : aucun ajout n'améliore la situation. "
                       "Il faut corriger ou supprimer une instruction existante.")

    # Recommandation principale
    type_labels = {"AJOUTER": "➕ Ajouter", "SUPPRIMER": "🗑️ Supprimer", "REMPLACER": "🔄 Remplacer"}
    label = type_labels.get(rec["type"], rec["type"])

    if rec["type"] == "AJOUTER":
        parties.append(f"💡 <b>Recommandation :</b> {label} <code>{rec['action_nom']}</code>")
    elif rec["type"] == "SUPPRIMER":
        parties.append(f"💡 <b>Recommandation :</b> {label} la ligne {rec['position']} "
                       f"(<code>{rec['action_nom']}</code>)")
    else:
        parties.append(f"💡 <b>Recommandation :</b> {label} la ligne {rec['position']} : "
                       f"<code>{rec['action_remplacee']}</code> → <code>{rec['action_nom']}</code>")

    delta_pct = round(rec["delta"] * 100, 1)
    signe = "+" if delta_pct >= 0 else ""
    parties.append(f"Après cette opération : <b>{round(rec['taux']*100,1)}%</b> de cas corrects "
                   f"({signe}{delta_pct}%).")

    # Note substitution règle de sécurité
    if substituee and originale:
        parties.append(f"⚠️ <i>Note : l'action optimale serait <code>{originale['action_nom']}</code>, "
                       f"mais elle risque d'échouer si la case est vide. "
                       f"Il est recommandé de la protéger avec un bloc conditionnel d'abord.</i>")

    return "<br>".join(parties)


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

    # Contre-exemple via GenerateurContreExemples
    contre_exemple_msg = systeme.generateur.tester_code(
        code_ids_etudiant, oracle, formater_message=True
    )

    # Recommandation via le système principal
    resultat = systeme.recommander(code_ids_etudiant, oracle, verbose=False)
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