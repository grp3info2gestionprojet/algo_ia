import random
from Algorithme_Interpreter import AlgorithmeInterpreter

class GenerateurContreExemples:
    def __init__(self, interpreter=None):
        self.interpreter = interpreter if interpreter else AlgorithmeInterpreter()

    def generer_etats_initiaux(self, nombre_etats, max_valeur=20):
        """
        Génère une liste d'états initiaux aléatoires.
        Dans ce contexte (selon Algorithme_Interpreter), un état du plateau est 
        apparemment représenté par une liste de 4 entiers (pour 4 cases/couleurs).
        """
        etats = []
        for _ in range(nombre_etats):
            # Génération d'un état avec 4 entiers entre 0 et max_valeur
            etat = tuple(random.randint(0, max_valeur) for _ in range(4))
            etats.append(etat)
        
        # Utilisation de set pour s'assurer qu'il n'y a pas de doublons
        return list(set(etats))

    def generer_oracle(self, code_correct, nb_etats=100, max_valeur=20):
        """
        Prend un code de référence (correct) et génère les états finaux correspondants
        pour un ensemble d'états initiaux générés aléatoirement.
        Retourne une liste de dictionnaires contenant l'état initial et l'état final attendu.
        """
        etats_initiaux = self.generer_etats_initiaux(nb_etats, max_valeur)
        exemples_reference = []

        for etat in etats_initiaux:
            plateau_final, nb_lignes, succes = self.interpreter.executer(code_correct, etat)
            
            # On ne conserve que les états initiaux pour lesquels le code correct
            # fonctionne sans erreur (par exemple sans retirer sur une case vide)
            if succes:
                exemples_reference.append({
                    "etat_initial": etat,
                    "etat_final": tuple(plateau_final)
                })

        return exemples_reference

    def formater_message_contre_exemple(self, contre_exemple):
        """
        Génère une phrase explicative du type: 
        "Contre exemple trouvé : Pour l'état initial X on a l'état final Y 
        alors que l'on souhaite avoir l'état final Z. Il faut enlever (ou ajouter) 
        un nombre n de jeton à la case x"
        """
        init = contre_exemple["etat_initial"]
        obtenu = contre_exemple["obtenu"]
        attendu = contre_exemple["attendu"]

        if obtenu == "Erreur d'exécution":
            return f"Contre exemple trouvé : Pour l'état initial {init} on a une erreur d'exécution alors que l'on souhaite avoir l'état final {attendu}."

        message = f"Contre exemple trouvé : Pour l'état initial {init} on a l'état final {obtenu} alors que l'on souhaite avoir l'état final {attendu}."
        
        noms_cases = ["Bleu (B)", "Jaune (J)", "Rouge (R)", "Vert (V)"]
        
        actions_necessaires = []
        for i in range(4):
            diff = attendu[i] - obtenu[i]
            if diff > 0:
                actions_necessaires.append(f"ajouter {diff} jeton(s) à la case {noms_cases[i]}")
            elif diff < 0:
                actions_necessaires.append(f"enlever {abs(diff)} jeton(s) à la case {noms_cases[i]}")

        if actions_necessaires:
            message += f" Il faut {' et '.join(actions_necessaires)}."

        return message

    def tester_code(self, code_a_tester, exemples_reference, formater_message=True):
        """
        Prend un code à évaluer et le teste sur tous les algorithmes de l'oracle (exemples_reference).
        S'il produit un résultat différent ou génère une erreur, la fonction 
        retourne immédiatement le premier contre-exemple trouvé.
        """
        for exemple in exemples_reference:
            etat_initial = exemple["etat_initial"]
            etat_final_attendu = exemple["etat_final"]

            plateau_final, nb_lignes, succes = self.interpreter.executer(code_a_tester, etat_initial)

            # Il y a un problème si l'exécution échoue ou si le plateau final est différent
            if not succes or tuple(plateau_final) != etat_final_attendu:
                contre_exemple = {
                    "etat_initial": etat_initial,
                    "attendu": etat_final_attendu,
                    "obtenu": tuple(plateau_final) if succes else "Erreur d'exécution",
                    "succes": succes
                }
                
                if formater_message:
                    return self.formater_message_contre_exemple(contre_exemple)
                return contre_exemple

        # Si on arrive ici, aucun contre-exemple n'a été trouvé
        return None

# ==========================================
# Exemple d'utilisation
# ==========================================
if __name__ == "__main__":
    generateur = GenerateurContreExemples()
    
    # Exemple de code correct : [0, 17] -> Ajouter(Rouge), STOP
    code_correct = [12, 4, 8, 0, 16, 16, 17]
    
    print("1. Génération de l'oracle (les exemples de référence) pour le code correct...")
    oracle = generateur.generer_oracle(code_correct, nb_etats=20, max_valeur=3)
    
    for item in oracle:
        print(f"   Initial: {item['etat_initial']} => Final attendu: {item['etat_final']}")
        
    code_incorrect = [12, 0, 0, 0, 4, 4, 8, 0, 16, 16, 17]
    
    print("\n2. Test d'un autre code qui est incorrect sur notre oracle...")
    contre_exemple = generateur.tester_code(code_incorrect, oracle)
    
    if contre_exemple:
        print(f"\n[!] {contre_exemple}")
    else:
        print("\n[✓] Aucun contre-exemple trouvé ! Les deux codes semblent équivalents.")
