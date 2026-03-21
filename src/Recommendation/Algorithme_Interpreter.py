import numpy as np


class AlgorithmeInterpreter:
    def __init__(self):
        color = 'BJRV'
        self.actions = {
            **{i: f"Ajouter({color[i]})" for i in range(4)},
            **{i+4: f"Retirer({color[i]})" for i in range(4)},
            **{i+8: f"SI Est_vide({color[i]})" for i in range(4)},
            **{i+12: f"SI NON Est_vide({color[i]})" for i in range(4)},
            16: "FIN_SI",
            17: "STOP",
            18: "SINON",
        }

    def executer(self, code_ids, etat_initial):
        """
        Exécute le code et retourne (plateau_final, nb_lignes, succès).
        Gère les structures SI / SINON / FIN_SI imbriquées.

        La pile stack_conditions stocke des tuples :
            (condition_vraie, dans_sinon, doit_skip)
        - condition_vraie : résultat de la condition du SI
        - dans_sinon      : True si on est dans le bloc SINON
        - doit_skip       : True si les instructions courantes doivent être ignorées
        """
        if not code_ids:
            return None, 0, False

        plateau = list(etat_initial)
        stack_conditions = []
        lignes_executees = 0
        max_iterations = 1000

        i = 0
        while i < len(code_ids):
            lignes_executees += 1

            if lignes_executees > max_iterations:
                return None, lignes_executees, False

            action_id = code_ids[i]

            if action_id not in self.actions:
                return None, lignes_executees, False

            action = self.actions[action_id]

            # ── STOP
            if action == "STOP":
                if len(stack_conditions) != 0:
                    return None, lignes_executees, False
                return plateau, lignes_executees, True

            # ── SI / SI NON
            if action.startswith("SI "):
                case_idx = action_id % 4

                if "NON Est_vide" in action:
                    condition_vraie = plateau[case_idx] > 0
                else:
                    condition_vraie = plateau[case_idx] == 0

                parent_skip = stack_conditions[-1][2] if stack_conditions else False
                # Dans le bloc SI on skip si : le parent skippait OU la condition est fausse
                doit_skip = parent_skip or not condition_vraie

                stack_conditions.append((condition_vraie, False, doit_skip))
                i += 1
                continue

            # ── SINON
            if action == "SINON":
                if len(stack_conditions) == 0:
                    # SINON sans SI correspondant
                    return None, lignes_executees, False

                condition_vraie, dans_sinon, _ = stack_conditions[-1]

                if dans_sinon:
                    # On ne peut pas avoir deux SINON pour un même SI
                    return None, lignes_executees, False

                parent_skip = stack_conditions[-2][2] if len(stack_conditions) >= 2 else False
                # Dans le bloc SINON on skip si : le parent skippait OU la condition était vraie
                doit_skip = parent_skip or condition_vraie

                stack_conditions[-1] = (condition_vraie, True, doit_skip)
                i += 1
                continue

            # ── FIN_SI
            if action == "FIN_SI":
                if len(stack_conditions) == 0:
                    return None, lignes_executees, False
                stack_conditions.pop()
                i += 1
                continue

            # ── Actions normales (Ajouter / Retirer)
            doit_skip = stack_conditions[-1][2] if stack_conditions else False

            if not doit_skip:
                case_idx = action_id % 4

                if "Ajouter" in action:
                    plateau[case_idx] += 1

                elif "Retirer" in action:
                    if plateau[case_idx] > 0:
                        plateau[case_idx] -= 1
                    else:
                        return None, lignes_executees, False

            i += 1

        # Fin de code sans STOP
        if len(stack_conditions) != 0:
            return None, lignes_executees, False

        return plateau, lignes_executees, True

    def print_algo(self, code_ids):
        if not code_ids:
            print("Code vide")
            return

        print("┌" + "─"*60 + "┐")
        print("│" + " "*22 + "ALGORITHME" + " "*28 + "│")
        print("├" + "─"*60 + "┤")

        depth = 0
        for i, action_id in enumerate(code_ids):
            if action_id not in self.actions:
                print(f"│ {i:2d} │ ERROR: Invalid action {action_id}" + " "*30 + "│")
                continue

            action = self.actions[action_id]
            tab = "  " * depth

            if action == "STOP":
                print(f"│ {i:2d} │ {tab}STOP" + " "*(54-len(tab)) + "│")
                break

            if action == "FIN_SI":
                depth = max(0, depth - 1)
                tab = "  " * depth
                print(f"│ {i:2d} │ {tab}{action}" + " "*(54-len(tab)-len(action)) + "│")

            elif action == "SINON":
                # SINON s'affiche au même niveau que son SI
                depth = max(0, depth - 1)
                tab = "  " * depth
                print(f"│ {i:2d} │ {tab}{action}" + " "*(54-len(tab)-len(action)) + "│")
                depth += 1

            else:
                print(f"│ {i:2d} │ {tab}{action}" + " "*(54-len(tab)-len(action)) + "│")
                if action.startswith("SI "):
                    depth += 1

        print("└" + "─"*60 + "┘")

    def analyser_structure(self, code_ids):
        depth = 0
        max_depth = 0
        si_count = 0
        finsi_count = 0
        sinon_count = 0

        for action_id in code_ids:
            if action_id not in self.actions:
                continue

            action = self.actions[action_id]

            if action.startswith("SI "):
                si_count += 1
                depth += 1
                max_depth = max(max_depth, depth)
            elif action == "SINON":
                sinon_count += 1
            elif action == "FIN_SI":
                finsi_count += 1
                depth -= 1

        return {
            'equilibre': si_count == finsi_count,
            'si_count': si_count,
            'finsi_count': finsi_count,
            'sinon_count': sinon_count,
            'max_depth': max_depth,
            'final_depth': depth
        }

