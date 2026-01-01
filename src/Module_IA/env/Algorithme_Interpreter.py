import numpy as np



class AlgorithmeInterpreter:
    def __init__(self):
        color = 'RBVJ'
        self.actions = {
            **{i: f"Ajouter({color[i]})" for i in range(4)},
            **{i+4: f"Retirer({color[i]})" for i in range(4)},
            **{i+8: f"SI Est_vide({color[i]})" for i in range(4)},
            **{i+12: f"SI NON Est_vide({color[i]})" for i in range(4)},
            16: "FIN_SI",
            17: "STOP"
        }


    def executer(self, code_ids, etat_initial):
        plateau = list(etat_initial)
        depth = 0
        skip_level = 0
        lignes_executees = 0

        for action_id in code_ids:
            lignes_executees += 1
            action = self.actions[action_id]

            if action == "STOP":
                break

            if action.startswith("SI "):
                case_idx = action_id % 4
                condition_vraie = False
                
                if "NON Est_vide" in action:
                    condition_vraie = plateau[case_idx] > 0
                else:
                    condition_vraie = plateau[case_idx] == 0

                if skip_level > 0 or not condition_vraie:
                    skip_level += 1
                depth += 1

            if action == "FIN_SI":
                if depth > 0:
                    if skip_level > 0:
                        skip_level -= 1
                    depth -= 1
                else:
                    return None, -100

            if skip_level == 0:
                case_idx = action_id % 4
                if "Ajouter" in action:
                    plateau[case_idx] += 1
                elif "Retirer" in action:
                    if plateau[case_idx] > 0:
                        plateau[case_idx] = plateau[case_idx] - 1
                    else:
                        return None, -100

        if depth != 0:
            return None, -100

        return plateau, lignes_executees


    def evaluer_agent(self, code_ids):
        scenarios = [
            [0, 0, 0, 0], [0, 1, 1, 0], [1, 0, 0, 5], 
            [0, 1, 0, 0], [0, 0, 1, 2]
        ]
        
        reussites = 0
        total_lignes = 0
        
        for s in scenarios:
            res_plateau, info = self.executer(code_ids, s)
            
            if res_plateau is None:
                return -100
            
            #Comparer avec les sorties attendu.
            #if self.verifier_succes(res_plateau,_,_):
            #    reussites += 1
            
            total_lignes = max(total_lignes, info)

        reward = (reussites * 20) - (total_lignes * 0.5)
        if reussites == 5:
            reward += 50 
            
        return reward
    

    def verifier_succes(self, plateau_final, cible_valeurs, cible_types):
        for i in range(4):
            val_reelle = plateau_final[i]
            val_cible = cible_valeurs[i]
            type_cible = cible_types[i]

            if type_cible == 0:
                if not (val_reelle == val_cible): return False
            elif type_cible == 1:
                if not (val_reelle >= val_cible): return False
            elif type_cible == 2:
                if not (val_reelle <= val_cible): return False
        
        return True
    

    def print_algo(self, code_ids):
        print("def function():")
        tab = "\t"
        for action_id in code_ids:
            action = self.actions[action_id]

            if action == "STOP":
                print("FIN_ALGO")
                break

            if action == "FIN_SI":
                tab = tab[:-1]
            
            print(tab + action)

            if action.startswith("SI "):
                tab += "\t"
