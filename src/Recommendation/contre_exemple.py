import random
from Algorithme_Interpreter import AlgorithmeInterpreter


class GenerateurContreExemples:
    """
    Génère et exploite un oracle pour tester la correction d'un programme étudiant.

    Un oracle est un ensemble de paires (état_initial, état_final_attendu)
    obtenues en exécutant le code de référence (correct) sur des états initiaux
    aléatoires. Il sert de "juge" : tout code qui produit un résultat différent
    sur au moins un de ces états est considéré incorrect.

    Attributs :
      interpreter : instance d'AlgorithmeInterpreter utilisée pour exécuter
                    les codes (peut être injectée depuis l'extérieur pour
                    partager une instance commune).
    """

    def __init__(self, interpreter=None):
        """
        Paramètres :
          interpreter : AlgorithmeInterpreter (optionnel). Si None, une nouvelle
                        instance est créée automatiquement.
        """
        self.interpreter = interpreter if interpreter else AlgorithmeInterpreter()

    def generer_etats_initiaux(self, nombre_etats, max_valeur=20):
        """
        Génère une liste d'états initiaux aléatoires et uniques.

        Un état est un tuple de 4 entiers représentant le nombre de jetons
        sur chacune des 4 cases du plateau (B, J, R, V).
        Chaque valeur est tirée uniformément dans [0, max_valeur].

        La déduplication via set() garantit l'absence de doublons, ce qui
        évite de tester plusieurs fois le même état et maximise la couverture.

        Paramètres :
          nombre_etats : int, nombre d'états à générer (avant déduplication)
          max_valeur   : int, valeur maximale possible par case (défaut : 20)

        Retourne :
          list[tuple[int, int, int, int]], liste d'états uniques
          (peut être légèrement plus courte que nombre_etats après déduplication)
        """
        etats = []
        for _ in range(nombre_etats):
            # Génère un tuple de 4 entiers aléatoires indépendants
            etat = tuple(random.randint(0, max_valeur) for _ in range(4))
            etats.append(etat)

        # set() supprime les doublons (possible car les tuples sont hashables)
        return list(set(etats))

    def generer_oracle(self, code_correct, nb_etats=100, max_valeur=20):
        """
        Construit l'oracle en exécutant le code de référence sur des états aléatoires.

        Procédure :
          1. Génère nb_etats états initiaux aléatoires (uniques).
          2. Exécute le code de référence sur chacun.
          3. Ne conserve que les états pour lesquels l'exécution réussit
             (sans erreur : pas de retrait sur case vide, code bien formé, etc.).

        Paramètres :
          code_correct : list[int], le programme de référence (correct)
          nb_etats     : int, nombre d'états initiaux à générer
          max_valeur   : int, valeur maximale par case

        Retourne :
          list[dict], chaque dict contenant :
            "etat_initial" : tuple[int, int, int, int]
            "etat_final"   : tuple[int, int, int, int]
        """
        etats_initiaux = self.generer_etats_initiaux(nb_etats, max_valeur)
        exemples_reference = []

        for etat in etats_initiaux:
            plateau_final, nb_lignes, succes = self.interpreter.executer(code_correct, etat)

            # On ne garde que les exécutions réussies pour construire l'oracle
            if succes:
                exemples_reference.append({
                    "etat_initial": etat,
                    "etat_final":   tuple(plateau_final)  # converti en tuple pour la comparaison
                })

        return exemples_reference

    def formater_message_contre_exemple(self, contre_exemple):
        """
        Génère un message pédagogique expliquant le contre-exemple trouvé.

        Le message indique :
          - L'état initial qui provoque la divergence
          - L'état final obtenu par le code étudiant (ou "erreur d'exécution")
          - L'état final attendu selon l'oracle
          - Les actions correctives à effectuer case par case (différences)

        Format du message :
          "Contre exemple trouvé : Pour l'état initial X on a l'état final Y
           alors que l'on souhaite avoir l'état final Z.
           Il faut ajouter N jeton(s) à la case C1 et enlever M jeton(s) à la case C2."

        Cas particulier "Erreur d'exécution" :
          Si le code étudiant a planté (succes=False), le message signale
          l'erreur sans tenter de calculer les différences.

        Paramètres :
          contre_exemple : dict avec les clés :
            "etat_initial" : tuple, état de départ
            "obtenu"       : tuple ou "Erreur d'exécution"
            "attendu"      : tuple, état final correct

        Retourne :
          str, le message formaté
        """
        init    = contre_exemple["etat_initial"]
        obtenu  = contre_exemple["obtenu"]
        attendu = contre_exemple["attendu"]

        # Cas d'erreur d'exécution : pas de plateau final à comparer
        if obtenu == "Erreur d'exécution":
            return (f"Contre exemple trouvé : Pour l'état initial {init} "
                    f"on a une erreur d'exécution alors que l'on souhaite "
                    f"avoir l'état final {attendu}.")

        message = (f"Contre exemple trouvé : Pour l'état initial {init} "
                   f"on a l'état final {obtenu} alors que l'on souhaite "
                   f"avoir l'état final {attendu}.")

        # Noms des cases dans l'ordre des indices (B=0, J=1, R=2, V=3)
        noms_cases = ["Bleu (B)", "Jaune (J)", "Rouge (R)", "Vert (V)"]

        # Calcule les différences case par case entre obtenu et attendu
        actions_necessaires = []
        for i in range(4):
            diff = attendu[i] - obtenu[i]
            if diff > 0:
                # Il manque des jetons -> il faut en ajouter
                actions_necessaires.append(f"ajouter {diff} jeton(s) à la case {noms_cases[i]}")
            elif diff < 0:
                # Il y a des jetons en trop -> il faut en enlever
                actions_necessaires.append(f"enlever {abs(diff)} jeton(s) à la case {noms_cases[i]}")
            # diff == 0 -> case correcte, aucune action à signaler

        if actions_necessaires:
            message += f" Il faut {' et '.join(actions_necessaires)}."

        return message

    def tester_code(self, code_a_tester, exemples_reference, formater_message=True):
        """
        Teste un programme étudiant sur tous les exemples de l'oracle et
        retourne le premier contre-exemple trouvé, ou None si le code est correct.

        Un contre-exemple est détecté si :
          - L'exécution du code échoue (succes=False), ou
          - Le plateau final est différent de l'état final attendu par l'oracle.

        Paramètres :
          code_a_tester      : list[int], le programme étudiant à évaluer
          exemples_reference : list[dict], l'oracle (produit par generer_oracle)
          formater_message   : bool (défaut True)
            - True  -> retourne la chaîne formatée par formater_message_contre_exemple
            - False -> retourne le dict brut du contre-exemple

        Retourne :
          - str  (si formater_message=True)  : message pédagogique, ou None si correct
          - dict (si formater_message=False) : dict avec les clés
              "etat_initial", "attendu", "obtenu", "succes"
            ou None si aucun contre-exemple n'est trouvé
        """
        for exemple in exemples_reference:
            etat_initial       = exemple["etat_initial"]
            etat_final_attendu = exemple["etat_final"]

            plateau_final, nb_lignes, succes = self.interpreter.executer(
                code_a_tester, etat_initial
            )

            # Détection de divergence : erreur d'exécution ou résultat différent
            if not succes or tuple(plateau_final) != etat_final_attendu:
                contre_exemple = {
                    "etat_initial": etat_initial,
                    "attendu":      etat_final_attendu,
                    "obtenu":       tuple(plateau_final) if succes else "Erreur d'exécution",
                    "succes":       succes,
                }

                if formater_message:
                    return self.formater_message_contre_exemple(contre_exemple)
                return contre_exemple

        # Aucun contre-exemple trouvé sur l'ensemble de l'oracle
        return None
