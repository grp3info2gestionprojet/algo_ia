import numpy as np


class AlgorithmeInterpreter:
    """
    Interpréteur du mini-langage de manipulation de plateau.

    Le plateau est une liste de 4 entiers représentant le nombre de jetons
    sur chacune des 4 cases colorées : B (Bleu), J (Jaune), R (Rouge), V (Vert).

    Un programme est une liste d'entiers (action_ids), chacun correspondant
    à une instruction du langage :
      0-3   -> Ajouter(B/J/R/V)        : dépose un jeton sur la case
      4-7   -> Retirer(B/J/R/V)        : retire un jeton de la case
                                         (erreur si la case est déjà vide)
      8-11  -> SI Est_vide(B/J/R/V)    : branche SI si la case est vide
      12-15 -> SI NON Est_vide(B/J/R/V): branche SI si la case n'est pas vide
      16    -> FIN_SI                  : ferme le bloc conditionnel courant
      17    -> STOP                    : termine l'exécution normalement
      18    -> SINON                   : branche alternative d'un bloc SI

    Les blocs conditionnels peuvent être imbriqués arbitrairement.
    """

    def __init__(self):
        """
        Initialise la table de correspondance action_id -> nom d'action.

        La chaîne 'BJRV' associe chaque indice (0..3) à une couleur.
        Les compressions de dict permettent de générer les 4×4 = 16 premières
        entrées en une seule expression, puis les cas spéciaux sont ajoutés.
        """
        color = 'BJRV'
        self.actions = {
            # Ajouter(B)=0, Ajouter(J)=1, Ajouter(R)=2, Ajouter(V)=3
            **{i: f"Ajouter({color[i]})" for i in range(4)},
            # Retirer(B)=4, Retirer(J)=5, Retirer(R)=6, Retirer(V)=7
            **{i+4: f"Retirer({color[i]})" for i in range(4)},
            # SI Est_vide(B)=8 … SI Est_vide(V)=11
            **{i+8: f"SI Est_vide({color[i]})" for i in range(4)},
            # SI NON Est_vide(B)=12 … SI NON Est_vide(V)=15
            **{i+12: f"SI NON Est_vide({color[i]})" for i in range(4)},
            16: "FIN_SI",
            17: "STOP",
            18: "SINON",
        }

    def executer(self, code_ids, etat_initial):
        """
        Exécute un programme et retourne l'état final du plateau.

        Gère les structures SI / SINON / FIN_SI imbriquées grâce à une pile
        (stack_conditions). Chaque niveau de la pile correspond à un bloc SI
        encore ouvert et contient un tuple à trois éléments :
          (condition_vraie, dans_sinon, doit_skip)
          - condition_vraie : bool, résultat évalué de la condition du SI
          - dans_sinon      : bool, True si on est dans la branche SINON de ce SI
          - doit_skip       : bool, True si les instructions de ce niveau
                              doivent être ignorées (condition fausse, ou
                              héritage d'un parent déjà en skip)

        Paramètres :
          code_ids     : list[int], liste des action_ids constituant le programme
          etat_initial : tuple/list de 4 int, nombre de jetons initiaux par case

        Retourne :
          (plateau_final, nb_lignes, succès)
          - plateau_final : list[int] ou None en cas d'erreur
          - nb_lignes     : int, nombre d'instructions parcourues
          - succès        : bool, True si l'exécution s'est terminée normalement

        Cas d'échec (succès=False, plateau_final=None) :
          - code_ids vide
          - action_id inconnu
          - STOP avec des SI encore ouverts (structure non fermée)
          - FIN_SI ou SINON sans SI correspondant
          - Double SINON pour un même SI
          - Retirer sur une case vide
          - Dépassement de la limite d'itérations (boucle infinie détectée)
          - Fin de code sans STOP avec des SI ouverts
        """
        if not code_ids:
            return None, 0, False

        # Copie de l'état initial pour ne pas modifier l'original
        plateau = list(etat_initial)
        stack_conditions = []   # Pile de (condition_vraie, dans_sinon, doit_skip)
        lignes_executees = 0
        max_iterations = 1000   # Garde-fou contre les boucles infinies éventuelles

        i = 0  # Indice courant dans code_ids (progression linéaire, pas de boucle dans le langage)
        while i < len(code_ids):
            lignes_executees += 1

            # Protection contre un code anormalement long ou une boucle infinie
            if lignes_executees > max_iterations:
                return None, lignes_executees, False

            action_id = code_ids[i]

            # Vérifie que l'action_id est connu dans la table
            if action_id not in self.actions:
                return None, lignes_executees, False

            action = self.actions[action_id]

            # ── Traitement de STOP ──────────────────────────────────────────
            if action == "STOP":
                # Un STOP valide ne doit pas laisser de SI ouverts :
                # tous les blocs conditionnels doivent avoir été fermés par FIN_SI.
                if len(stack_conditions) != 0:
                    return None, lignes_executees, False
                return plateau, lignes_executees, True

            # ── Traitement d'un SI (ou SI NON) ─────────────────────────────
            if action.startswith("SI "):
                # L'indice de la case (0..3) s'obtient par modulo 4 :
                #   SI Est_vide     : ids 8-11  -> 8%4=0, 9%4=1, 10%4=2, 11%4=3
                #   SI NON Est_vide : ids 12-15 -> 12%4=0, 13%4=1, 14%4=2, 15%4=3
                case_idx = action_id % 4

                # Évaluation de la condition sur l'état courant du plateau
                if "NON Est_vide" in action:
                    condition_vraie = plateau[case_idx] > 0   # case non vide
                else:
                    condition_vraie = plateau[case_idx] == 0  # case vide

                # Héritage du skip parent : si le bloc englobant est déjà en skip,
                # le bloc enfant l'est aussi (quelle que soit sa propre condition).
                parent_skip = stack_conditions[-1][2] if stack_conditions else False
                doit_skip = parent_skip or not condition_vraie

                # Empile ce nouveau niveau conditionnel
                # dans_sinon=False : on entre d'abord dans la branche SI
                stack_conditions.append((condition_vraie, False, doit_skip))
                i += 1
                continue

            # ── Traitement de SINON ─────────────────────────────────────────
            if action == "SINON":
                # SINON sans SI ouvert -> erreur structurelle
                if len(stack_conditions) == 0:
                    return None, lignes_executees, False

                condition_vraie, dans_sinon, _ = stack_conditions[-1]

                # Un même SI ne peut avoir qu'un seul SINON
                if dans_sinon:
                    return None, lignes_executees, False

                # Pour la branche SINON, on skip si le parent skippait OU si la
                # condition du SI était vraie (dans ce cas on exécutait la branche SI,
                # donc on ignore la branche SINON, et vice-versa).
                parent_skip = stack_conditions[-2][2] if len(stack_conditions) >= 2 else False
                doit_skip = parent_skip or condition_vraie

                # Met à jour le niveau courant pour marquer l'entrée dans SINON
                stack_conditions[-1] = (condition_vraie, True, doit_skip)
                i += 1
                continue

            # ── Traitement de FIN_SI ────────────────────────────────────────
            if action == "FIN_SI":
                # FIN_SI sans SI correspondant -> erreur structurelle
                if len(stack_conditions) == 0:
                    return None, lignes_executees, False
                # Ferme le niveau conditionnel le plus récent
                stack_conditions.pop()
                i += 1
                continue

            # ── Actions normales : Ajouter / Retirer ────────────────────────
            # Ces instructions ne s'exécutent que si le niveau courant n'est pas en skip.
            doit_skip = stack_conditions[-1][2] if stack_conditions else False

            if not doit_skip:
                # case_idx : même logique modulo 4 que pour les SI
                #   Ajouter : ids 0-3  -> 0%4=0, 1%4=1, 2%4=2, 3%4=3
                #   Retirer : ids 4-7  -> 4%4=0, 5%4=1, 6%4=2, 7%4=3
                case_idx = action_id % 4

                if "Ajouter" in action:
                    plateau[case_idx] += 1          # dépose un jeton

                elif "Retirer" in action:
                    if plateau[case_idx] > 0:
                        plateau[case_idx] -= 1      # retire un jeton
                    else:
                        # Tentative de retrait sur une case vide -> erreur d'exécution
                        return None, lignes_executees, False

            i += 1

        # ── Fin de liste sans STOP ───────────────────────────────────────────
        # Si on arrive ici, c'est que le programme ne contient pas de STOP.
        # On accepte ce cas uniquement si tous les SI sont fermés.
        if len(stack_conditions) != 0:
            return None, lignes_executees, False

        return plateau, lignes_executees, True

    def print_algo(self, code_ids):
        """
        Affiche le programme dans un encadré ASCII avec indentation selon
        la profondeur des blocs conditionnels.

        L'indentation suit ces règles d'affichage :
          - SI     : affiché au niveau courant, puis la profondeur augmente
          - SINON  : affiché un niveau en retrait (même niveau que son SI),
                     puis la profondeur ré-augmente pour le corps du SINON
          - FIN_SI : la profondeur diminue avant l'affichage (retour au niveau parent)
          - STOP   : affiché puis la boucle s'arrête

        Les action_ids inconnus sont affichés avec un message d'erreur.

        Paramètres :
          code_ids : list[int], le programme à afficher
        """
        if not code_ids:
            print("Code vide")
            return

        print("┌" + "─"*60 + "┐")
        print("│" + " "*22 + "ALGORITHME" + " "*28 + "│")
        print("├" + "─"*60 + "┤")

        depth = 0  # profondeur d'indentation courante
        for i, action_id in enumerate(code_ids):
            if action_id not in self.actions:
                # Action inconnue : affiche un message d'erreur et continue
                print(f"│ {i:2d} │ ERROR: Invalid action {action_id}" + " "*30 + "│")
                continue

            action = self.actions[action_id]
            tab = "  " * depth  # chaîne d'espaces correspondant à la profondeur

            if action == "STOP":
                print(f"│ {i:2d} │ {tab}STOP" + " "*(54-len(tab)) + "│")
                break  # on s'arrête ici, le reste du code après STOP n'est pas affiché

            if action == "FIN_SI":
                # FIN_SI se place au niveau du SI correspondant -> on décrément avant
                depth = max(0, depth - 1)
                tab = "  " * depth
                print(f"│ {i:2d} │ {tab}{action}" + " "*(54-len(tab)-len(action)) + "│")

            elif action == "SINON":
                # SINON s'affiche au même niveau que son SI :
                # on décrémente pour rejoindre le niveau du SI, on affiche,
                # puis on incrémente pour le corps du SINON
                depth = max(0, depth - 1)
                tab = "  " * depth
                print(f"│ {i:2d} │ {tab}{action}" + " "*(54-len(tab)-len(action)) + "│")
                depth += 1

            else:
                # Action normale ou SI : affichage puis incrémentation si SI
                print(f"│ {i:2d} │ {tab}{action}" + " "*(54-len(tab)-len(action)) + "│")
                if action.startswith("SI "):
                    depth += 1  # le corps du SI est indenté d'un niveau supplémentaire

        print("└" + "─"*60 + "┘")

    def analyser_structure(self, code_ids):
        """
        Analyse la structure de contrôle du programme sans l'exécuter.

        Parcourt code_ids et compte les structures conditionnelles pour
        détecter des déséquilibres (SI sans FIN_SI, ou FIN_SI en excès).

        Retourne un dictionnaire contenant :
          'equilibre'   : bool, True si le nombre de SI == nombre de FIN_SI
                          (tous les blocs conditionnels sont correctement fermés)
          'si_count'    : int, nombre total de SI (y compris SI NON Est_vide)
          'finsi_count' : int, nombre total de FIN_SI
          'sinon_count' : int, nombre total de SINON
          'max_depth'   : int, profondeur maximale d'imbrication atteinte
          'final_depth' : int, profondeur finale (0 si tous les SI sont fermés,
                          valeur positive si des SI restent ouverts,
                          valeur négative si des FIN_SI sont en excès)

        Note : les action_ids inconnus sont simplement ignorés.

        Paramètres :
          code_ids : list[int], le programme à analyser
        """
        depth = 0        # profondeur courante (nb de SI ouverts)
        max_depth = 0    # profondeur maximale observée
        si_count = 0     # nombre de SI rencontrés
        finsi_count = 0  # nombre de FIN_SI rencontrés
        sinon_count = 0  # nombre de SINON rencontrés

        for action_id in code_ids:
            if action_id not in self.actions:
                continue  # action inconnue -> ignorée

            action = self.actions[action_id]

            if action.startswith("SI "):
                si_count += 1
                depth += 1
                max_depth = max(max_depth, depth)   # mise à jour du pic
            elif action == "SINON":
                sinon_count += 1                    # SINON ne change pas la profondeur
            elif action == "FIN_SI":
                finsi_count += 1
                depth -= 1                          # ferme le SI le plus récent

        return {
            'equilibre':   si_count == finsi_count, # True = structure bien équilibrée
            'si_count':    si_count,
            'finsi_count': finsi_count,
            'sinon_count': sinon_count,
            'max_depth':   max_depth,
            'final_depth': depth,                   # != 0 -> code mal formé
        }