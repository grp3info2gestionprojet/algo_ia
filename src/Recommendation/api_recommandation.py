from .Recommandation import SystemeRecommandation, ALL_ACTIONS

# ---------------------------------------------------------------------------
# Tables de correspondance frontend <-> backend
# ---------------------------------------------------------------------------

# Associe le code couleur (lettre minuscule) utilisé côté frontend
# à l'indice numérique (0..3) utilisé dans AlgorithmeInterpreter.
# L'ordre correspond à : B=0 (Bleu), J=1 (Jaune), R=2 (Rouge), V=3 (Vert).
COLOR_MAP = {'b': 0, 'j': 1, 'r': 2, 'v': 3}

# Correspondance inverse : indice -> nom complet de la couleur en français.
# Utilisé pour produire le pseudocode lisible affiché à l'élève.
COLOR_NAMES = {0: 'bleue', 1: 'jaune', 2: 'rouge', 3: 'verte'}


# ---------------------------------------------------------------------------
# Conversion blocs JS -> code_ids
# ---------------------------------------------------------------------------

def blocks_to_code_ids(blocks):
    """
    Convertit la liste de blocs envoyée par le frontend (format JSON/JS)
    en une liste de code_ids (entiers) attendue par AlgorithmeInterpreter.

    Le frontend représente le programme de l'élève comme une liste plate de
    dicts, chacun ayant au moins les champs :
      "type"  : str, type de l'instruction (voir tableau ci-dessous)
      "color" : str, couleur cible ('b', 'j', 'r' ou 'v') — ignoré pour
                     les instructions sans couleur (sinon, finsi)

    Correspondance type -> action_id :
      "poser"              -> 0-3   (Ajouter)
      "retirer"            -> 4-7   (Retirer)
      "if_empty"           -> 8-11  (SI Est_vide)
      "if_empty_else"      -> 8-11  (SI Est_vide, variante avec SINON prévu)
      "if_not_empty"       -> 12-15 (SI NON Est_vide)
      "if_not_empty_else"  -> 12-15 (idem, variante avec SINON)
      "sinon"              -> 18
      "finsi"              -> 16

    Note : le STOP (17) est ajouté automatiquement en fin de liste, car
    le frontend ne gère pas ce token (la fermeture est implicite).

    Paramètres :
      blocks : list[dict], blocs envoyés par le frontend

    Retourne :
      list[int], liste de code_ids prête pour AlgorithmeInterpreter
    """
    code_ids = []
    for b in blocks:
        # Récupère l'indice de couleur (défaut : 0 = Bleu si couleur inconnue)
        c = COLOR_MAP.get(b.get('color'), 0)
        t = b.get('type', '')

        if t == 'poser':
            code_ids.append(c)           # Ajouter(couleur) : ids 0-3
        elif t == 'retirer':
            code_ids.append(c + 4)       # Retirer(couleur) : ids 4-7
        elif t in ('if_empty', 'if_empty_else'):
            code_ids.append(c + 8)       # SI Est_vide(couleur) : ids 8-11
        elif t in ('if_not_empty', 'if_not_empty_else'):
            code_ids.append(c + 12)      # SI NON Est_vide(couleur) : ids 12-15
        elif t == 'sinon':
            code_ids.append(18)          # SINON
        elif t == 'finsi':
            code_ids.append(16)          # FIN_SI

    code_ids.append(17)  # STOP ajouté automatiquement en fin de programme
    return code_ids


# ---------------------------------------------------------------------------
# Conversion code_ids -> pseudocode lisible
# ---------------------------------------------------------------------------

def code_ids_to_pseudocode(code_ids):
    """
    Convertit une liste de code_ids en pseudocode lisible numéroté,
    destiné à être affiché dans l'interface.

    Le pseudocode est une chaîne multi-lignes au format :
      "N: [indentation]instruction"

    Règles d'indentation :
      - SI / SI NON : affiché au niveau courant, puis profondeur +1
      - SINON       : profondeur -1 avant affichage, puis profondeur +1
      - FIN_SI      : profondeur -1 avant affichage
      - STOP        : arrête la conversion (le reste est ignoré)

    La numérotation des lignes commence à 1 et ne compte que les instructions
    visibles (pas le STOP, qui n'est pas affiché).

    Paramètres :
      code_ids : list[int], le programme à convertir

    Retourne :
      str, pseudocode multi-lignes ou "(algorithme vide)" si aucune instruction
    """
    lines = []
    depth = 0    # profondeur d'indentation courante
    line_no = 1  # numéro de ligne affiché (commence à 1)

    for action_id in code_ids:
        action = ALL_ACTIONS.get(action_id, '')
        if not action:
            continue  # action_id inconnu -> ignoré

        if action == 'STOP':
            break  # fin du programme, on s'arrête

        indent = '    ' * depth  # 4 espaces par niveau d'indentation

        if action == 'FIN_SI':
            # FIN_SI se place au niveau du SI -> décrémente avant l'affichage
            depth = max(0, depth - 1)
            indent = '    ' * depth
            lines.append(f"{line_no}: {indent}finsi")
            line_no += 1

        elif action == 'SINON':
            # SINON se place au même niveau que son SI -> décrémente, affiche, réincrémente
            depth = max(0, depth - 1)
            indent = '    ' * depth
            lines.append(f"{line_no}: {indent}sinon")
            line_no += 1
            depth += 1  # le corps du SINON est indenté

        elif action.startswith('SI NON Est_vide('):
            # Extrait la couleur et formate la ligne
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}si non est_vide({c}) alors")
            line_no += 1
            depth += 1  # le corps du SI est indenté

        elif action.startswith('SI Est_vide('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}si est_vide({c}) alors")
            line_no += 1
            depth += 1

        elif action.startswith('Poser('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}poser(->{c})")
            line_no += 1

        elif action.startswith('Retirer('):
            c = COLOR_NAMES[action_id % 4]
            lines.append(f"{line_no}: {indent}retirer(->{c})")
            line_no += 1

    return '\n'.join(lines) if lines else '(algorithme vide)'


# ---------------------------------------------------------------------------
# Troncature du code pour le système de recommandation
# ---------------------------------------------------------------------------

def tronquer_code_partiel(code_ids):
    """
    Prépare le code de l'élève pour le système de recommandation en retirant
    le STOP final et les FIN_SI qui le précèdent immédiatement.

    Procédure :
      1. Retire le STOP final (id=17) s'il est présent.
      2. Retire tous les FIN_SI (id=16) qui se trouvent maintenant en fin de liste
         (ces FIN_SI étaient uniquement là pour "fermer" avant le STOP).

    Paramètres :
      code_ids : list[int], le programme complet (avec STOP)

    Retourne :
      list[int], le code partiel sans STOP ni FIN_SI de fermeture
    """
    ids = list(code_ids)
    if ids and ids[-1] == 17:
        ids.pop()                    # retire le STOP
    while ids and ids[-1] == 16:
        ids.pop()                    # retire les FIN_SI terminaux
    return ids


# ---------------------------------------------------------------------------
# Mise en forme de la recommandation pour l'interface
# ---------------------------------------------------------------------------

def recommandation_to_message(resultat):
    """
    Transforme le dict retourné par SystemeRecommandation.recommander()
    en un message HTML lisible pour l'élève, affiché dans la zone feedbackText.

    Cas traités :
      1. Code correct (taux == 1.0) : message de succès ✅
      2. Aucune recommandation disponible : message générique
      3. Recommandation de type AJOUTER  : indique l'action à ajouter
      4. Recommandation de type SUPPRIMER : indique la ligne à supprimer
      5. Recommandation de type REMPLACER : indique le remplacement à effectuer

    Le message utilise des balises HTML légères (<b>, <code>) compatibles
    avec l'affichage dans la plupart des interfaces web.

    Paramètres :
      resultat : dict, retour de SystemeRecommandation.recommander()

    Retourne :
      str, message HTML destiné à l'élève
    """
    # Cas 1 : le code est déjà fonctionnellement correct
    if resultat.get("code_correct"):
        return "✅ Votre algorithme est correct !"

    rec = resultat.get("recommandation")
    if rec is None:
        return "Aucune recommandation disponible pour le moment."

    # Libellés courts associés à chaque type d'opération
    type_labels = {
        "AJOUTER":   "➕ Ajouter",
        "SUPPRIMER": "🗑️ Supprimer",
        "REMPLACER": "🔄 Remplacer"
    }
    label = type_labels.get(rec["type"], rec["type"])

    if rec["type"] == "AJOUTER":
        # Indique simplement l'action à ajouter à la suite du code
        return f"💡 <b>Prochaine action :</b> {label} <code>{rec['action_nom']}</code>"

    elif rec["type"] == "SUPPRIMER":
        # Indique la ligne et l'action à supprimer
        return (f"💡 <b>Prochaine action :</b> {label} la ligne {rec['position']} "
                f"(<code>{rec['action_nom']}</code>)")

    else:
        # REMPLACER : indique l'ancienne et la nouvelle action
        return (f"💡 <b>Prochaine action :</b> {label} la ligne {rec['position']} : "
                f"<code>{rec['action_remplacee']}</code> -> <code>{rec['action_nom']}</code>")


# ---------------------------------------------------------------------------
# Point d'entrée principal pour les routes Flask
# ---------------------------------------------------------------------------

def analyser_code_etudiant(blocks, code_ids_correct, nb_etats=50, max_valeur=5):
    """
    Fonction principale appelée par les routes Flask pour analyser le code
    soumis par l'élève et produire un retour pédagogique complet.

    Elle orchestre toute la chaîne de traitement :
      1. Conversion des blocs frontend en code_ids
      2. Génération du pseudocode de l'élève
      3. Construction de l'oracle depuis le code de référence
      4. Recherche d'un contre-exemple (code complet avec STOP)
      5. Génération de la recommandation (code partiel sans STOP)
      6. Formatage des messages pour l'interface

    Pourquoi distinguer "code complet" et "code partiel" ?
      - Le contre-exemple nécessite le code complet (avec STOP) pour l'exécuter
        jusqu'au bout et comparer le plateau final à l'oracle.
      - La recommandation travaille sur le code partiel (sans STOP ni FIN_SI
        de fermeture) pour simuler le point d'avancement de l'élève et suggérer
        la prochaine instruction à ajouter.

    Paramètres :
      blocks           : list[dict], blocs plats envoyés par le frontend
                         (chaque dict a au moins "type" et "color")
      code_ids_correct : list[int], code de référence de l'exercice
      nb_etats         : int (défaut 50), taille de l'oracle
                         (plus grand = plus fiable mais plus lent)
      max_valeur       : int (défaut 5), valeur max des cases dans l'oracle
                         (adapter selon la complexité de l'exercice)

    Retourne :
      dict avec quatre clés :
        "contre_exemple" : str | None
            Message pédagogique décrivant le premier contre-exemple trouvé,
            ou None si le code est correct sur tout l'oracle.
        "message" : str
            Recommandation formatée en HTML pour l'interface élève.
        "pseudocode" : str | None
            Pseudocode lisible du code de référence, fourni uniquement si
            le code étudiant est incorrect (pour aider l'élève à se repérer).
            None si le code est correct.
        "student_code" : str
            Pseudocode lisible du code de l'élève (toujours fourni).
    """
    # ── Étape 1 : Conversion des blocs en code_ids ──────────────────────────
    code_ids_etudiant = blocks_to_code_ids(blocks)

    # ── Étape 2 : Génération du pseudocode étudiant pour l'affichage ────────
    student_pseudocode = code_ids_to_pseudocode(code_ids_etudiant)

    # ── Étape 3 : Construction de l'oracle depuis le code de référence ──────
    systeme = SystemeRecommandation()
    oracle  = systeme.construire_oracle(code_ids_correct, nb_etats=nb_etats, max_valeur=max_valeur)

    # ── Étape 4 : Recherche d'un contre-exemple (code complet avec STOP) ────
    # tester_code() s'arrête dès le premier état qui donne un résultat différent.
    contre_exemple_msg = systeme.generateur.tester_code(
        code_ids_etudiant, oracle, formater_message=True
    )

    # ── Étape 5 : Génération de la recommandation (code partiel) ────────────
    # On tronque le STOP et les FIN_SI terminaux pour que le système
    # recommande la "prochaine instruction" à ajouter, plutôt que de
    # considérer le programme comme terminé.
    code_partiel = tronquer_code_partiel(code_ids_etudiant)
    resultat     = systeme.recommander(code_partiel, oracle, verbose=False)

    # ── Étape 6 : Mise en forme du message pour l'interface ─────────────────
    message = recommandation_to_message(resultat)

    # Le pseudocode de référence n'est fourni qu'en cas d'erreur,
    # pour ne pas "donner la réponse" si le code est déjà correct.
    pseudocode_ref = None
    if not resultat.get("code_correct"):
        pseudocode_ref = code_ids_to_pseudocode(code_ids_correct)

    return {
        "contre_exemple": contre_exemple_msg,
        "message":        message,
        "pseudocode":     pseudocode_ref,
        "student_code":   student_pseudocode,
    }