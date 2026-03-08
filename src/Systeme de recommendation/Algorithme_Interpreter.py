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
            17: "STOP"
        }

    def executer(self, code_ids, etat_initial):
        """
        Exécute le code et retourne (plateau_final, nb_lignes, succès)
        CORRECTION: Gestion correcte de la profondeur et du skip
        """
        if not code_ids:
            return None, 0, False
        
        plateau = list(etat_initial)
        stack_conditions = []  # Pile pour gérer les conditions imbriquées
        lignes_executees = 0
        max_iterations = 1000
        
        i = 0
        while i < len(code_ids):
            lignes_executees += 1
            
            if lignes_executees > max_iterations:
                return None, lignes_executees, False
            
            action_id = code_ids[i]
            
            if action_id >= len(self.actions):
                return None, lignes_executees, False
            
            action = self.actions[action_id]
            
            # STOP termine l'exécution
            if action == "STOP":
                # Vérifier que toutes les structures sont fermées
                if len(stack_conditions) != 0:
                    return None, lignes_executees, False
                return plateau, lignes_executees, True
            
            # Gestion des SI
            if action.startswith("SI "):
                case_idx = action_id % 4
                
                # Évaluer la condition
                if "NON Est_vide" in action:
                    condition_vraie = plateau[case_idx] > 0
                else:  # Est_vide
                    condition_vraie = plateau[case_idx] == 0
                
                # Empiler la condition avec son résultat
                # Format: (condition_vraie, doit_skip_actuel)
                parent_skip = stack_conditions[-1][1] if stack_conditions else False
                doit_skip = parent_skip or not condition_vraie
                
                stack_conditions.append((condition_vraie, doit_skip))
                i += 1
                continue
            
            # Gestion des FIN_SI
            if action == "FIN_SI":
                if len(stack_conditions) == 0:
                    # Erreur: FIN_SI sans SI correspondant
                    return None, lignes_executees, False
                stack_conditions.pop()
                i += 1
                continue
            
            # Exécuter les actions seulement si pas en mode skip
            doit_skip = stack_conditions[-1][1] if stack_conditions else False
            
            if not doit_skip:
                case_idx = action_id % 4
                
                if "Ajouter" in action:
                    plateau[case_idx] += 1
                    
                elif "Retirer" in action:
                    if plateau[case_idx] > 0:
                        plateau[case_idx] -= 1
                    else:
                        # Erreur: retrait sur case vide
                        return None, lignes_executees, False
            
            i += 1
        
        # Si on arrive ici, le code n'a pas de STOP
        # Vérifier quand même que les structures sont fermées
        if len(stack_conditions) != 0:
            return None, lignes_executees, False
        
        return plateau, lignes_executees, True

    def print_algo(self, code_ids):
        """Affiche l'algorithme de manière lisible"""
        if not code_ids:
            print("Code vide")
            return
        
        print("┌" + "─"*60 + "┐")
        print("│" + " "*22 + "ALGORITHME" + " "*28 + "│")
        print("├" + "─"*60 + "┤")
        
        depth = 0
        for i, action_id in enumerate(code_ids):
            if action_id >= len(self.actions):
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
            else:
                print(f"│ {i:2d} │ {tab}{action}" + " "*(54-len(tab)-len(action)) + "│")
                
                if action.startswith("SI "):
                    depth += 1
        
        print("└" + "─"*60 + "┘")
    
    def analyser_structure(self, code_ids):
        """Analyse la structure du code pour debugging"""
        depth = 0
        max_depth = 0
        si_count = 0
        finsi_count = 0
        
        for action_id in code_ids:
            if action_id >= len(self.actions):
                continue
            
            action = self.actions[action_id]
            
            if action.startswith("SI "):
                si_count += 1
                depth += 1
                max_depth = max(max_depth, depth)
            elif action == "FIN_SI":
                finsi_count += 1
                depth -= 1
        
        return {
            'equilibre': si_count == finsi_count,
            'si_count': si_count,
            'finsi_count': finsi_count,
            'max_depth': max_depth,
            'final_depth': depth
        }