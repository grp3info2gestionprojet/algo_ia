import gym
from gym import spaces
import numpy as np
import Algorithme_Interpreter as AI

class EnvironnementGenerique(gym.Env):
    """
    Environnement GÉNÉRIQUE qui peut résoudre différents énoncés
    L'énoncé est encodé dans l'observation pour que l'agent apprenne à généraliser
    """
    def __init__(self, enonce_config=None):
        super(EnvironnementGenerique, self).__init__()
        self.action_space = spaces.Discrete(18)
        # Observation : 4 (infos) + 20 (encodage énoncé) + 4 (si_ouverts) + 50 (code) = 78
        self.observation_space = spaces.Box(low=0, high=50, shape=(83,), dtype=np.float32)  # 4 + 25 + 4 + 50 = 83
        
        self.interpreter = AI.AlgorithmeInterpreter()
        
        # Configuration de l'énoncé (peut être changée)
        self.enonce_config = enonce_config or self._get_default_enonce()
        
        # Générer les scénarios automatiquement selon l'énoncé
        self.scenarios = self._generate_scenarios()
        
        self.episode_count = 0
        self.best_reward = -float('inf')
        self.best_code = None
    
    def _get_default_enonce(self):
        """Énoncé par défaut : Retirer de R si non vide, puis ajouter si devient vide"""
        return {
            'type': 'conditionnel_imbrique',
            'description': 'Si R non vide: retirer 1, puis si R vide: ajouter 1',
            'condition_principale': {
                'case': 0,  # R=0, B=1, V=2, J=3
                'type': 'non_vide'
            },
            'action_principale': {
                'case': 0,
                'operation': 'retirer'
            },
            'condition_secondaire': {
                'case': 0,
                'type': 'vide'
            },
            'action_secondaire': {
                'case': 0,
                'operation': 'ajouter'
            }
        }
    
    def _encode_enonce(self):
        """Encode l'énoncé en vecteur pour l'observation avec plus de détails sur imbrication"""
        config = self.enonce_config
        encoding = np.zeros(25, dtype=np.float32)  # Augmenté de 20 à 25
        
        # Type d'énoncé (one-hot)
        type_map = {
            'simple': 0,
            'conditionnel': 1,
            'conditionnel_imbrique': 2,
            'boucle': 3
        }
        encoding[type_map.get(config['type'], 0)] = 1.0
        
        # Condition principale
        if 'condition_principale' in config:
            cond = config['condition_principale']
            encoding[4 + cond['case']] = 1.0  # Quelle case (R,B,V,J)
            encoding[8] = 1.0 if cond['type'] == 'vide' else 0.0
            encoding[9] = 1.0 if cond['type'] == 'non_vide' else 0.0
        
        # Action principale
        if 'action_principale' in config:
            act = config['action_principale']
            encoding[10 + act['case']] = 1.0
            encoding[14] = 1.0 if act['operation'] == 'ajouter' else 0.0
            encoding[15] = 1.0 if act['operation'] == 'retirer' else 0.0
        
        # Condition secondaire (si imbrication)
        if 'condition_secondaire' in config:
            cond = config['condition_secondaire']
            encoding[16] = 1.0  # Indicateur d'imbrication
            encoding[17] = 1.0 if cond['type'] == 'vide' else 0.0
            encoding[18] = 1.0 if cond['type'] == 'non_vide' else 0.0
            encoding[19] = 1.0 if cond['case'] == config['condition_principale']['case'] else 0.0  # Même case
        
        # Action secondaire
        if 'action_secondaire' in config:
            act = config['action_secondaire']
            encoding[20] = 1.0 if act['operation'] == 'ajouter' else 0.0
            encoding[21] = 1.0 if act['operation'] == 'retirer' else 0.0
            encoding[22] = 1.0 if act['case'] == config['condition_principale']['case'] else 0.0  # Même case
        
        # Informations sur la séquence attendue pour imbrication
        if config['type'] == 'conditionnel_imbrique':
            encoding[23] = 1.0  # Flag pour séquence imbriquée
            # Position dans la séquence (sera mis à jour dynamiquement)
            encoding[24] = 0.0  # Sera défini dans _get_observation
        
        return encoding
    
    def _generate_scenarios(self):
        """Génère des scénarios de test variés selon l'énoncé"""
        scenarios = []
        case_idx = self.enonce_config.get('condition_principale', {}).get('case', 0)

        # Scénarios de base : toutes les cases vides
        scenarios.append([0, 0, 0, 0])

        # Scénarios avec variations sur la case concernée (0-10)
        for val in range(11):  # 0 à 10 inclus
            scenario = [0, 0, 0, 0]
            scenario[case_idx] = val
            scenarios.append(scenario)

        # Scénarios avec autres cases non vides (valeurs variées)
        for other_case in range(4):
            if other_case != case_idx:
                for val_main in [1, 2, 5]:
                    for val_other in [1, 2, 3, 5]:
                        scenario = [0, 0, 0, 0]
                        scenario[case_idx] = val_main
                        scenario[other_case] = val_other
                        scenarios.append(scenario)

        # Scénarios avec toutes les cases remplies (différentes valeurs)
        for val in [1, 2, 3, 5, 8]:
            scenarios.append([val, val, val, val])

        # Scénarios avec patterns spécifiques
        # Case concernée vide, autres variées
        for pattern in [[0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1], [0, 1, 1, 0], [0, 1, 0, 1]]:
            scenario = pattern.copy()
            scenarios.append(scenario)

        # Case concernée pleine, autres variées
        for val_main in [1, 2, 3]:
            for pattern in [[0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1], [1, 1, 0, 0], [0, 1, 1, 0]]:
                scenario = pattern.copy()
                scenario[case_idx] = val_main
                scenarios.append(scenario)

        # Scénarios avec des valeurs élevées sur case concernée
        for val in [7, 8, 9, 10, 15, 20]:
            scenario = [0, 0, 0, 0]
            scenario[case_idx] = val
            scenarios.append(scenario)

        # Scénarios mixtes avec hautes valeurs
        high_val_scenarios = [
            [10, 0, 0, 0], [0, 10, 0, 0], [0, 0, 10, 0], [0, 0, 0, 10],
            [5, 5, 0, 0], [5, 0, 5, 0], [5, 0, 0, 5], [0, 5, 5, 0],
            [3, 3, 3, 0], [3, 3, 0, 3], [3, 0, 3, 3], [0, 3, 3, 3],
            [8, 2, 0, 0], [2, 8, 0, 0], [0, 2, 8, 0], [0, 0, 2, 8]
        ]
        scenarios.extend(high_val_scenarios)

        # Scénarios edge cases pour imbrication
        if self.enonce_config.get('type') == 'conditionnel_imbrique':
            # Scénarios où la condition secondaire est critique
            edge_cases = [
                [1, 0, 0, 0],  # Condition principale vraie, secondaire dépend du résultat
                [2, 0, 0, 0],  # Même chose
                [0, 1, 0, 0],  # Condition principale fausse
                [0, 2, 0, 0],  # Condition principale fausse
            ]
            # Ajouter des variations pour chaque case
            for base_case in range(4):
                for val in [0, 1, 2, 3]:
                    scenario = [0, 0, 0, 0]
                    scenario[base_case] = val
                    if scenario not in scenarios:  # Éviter les doublons
                        scenarios.append(scenario)

        # Supprimer les doublons et limiter à 100 scénarios max pour performance
        unique_scenarios = []
        seen = set()
        for scenario in scenarios:
            scenario_tuple = tuple(scenario)
            if scenario_tuple not in seen:
                seen.add(scenario_tuple)
                unique_scenarios.append(scenario)

        # Mélanger et limiter
        np.random.shuffle(unique_scenarios)
        return unique_scenarios[:100]  # Maximum 100 scénarios pour l'entraînement
    
    def get_scenario_stats(self):
        """Retourne des statistiques sur les scénarios générés"""
        stats = {
            'total_scenarios': len(self.scenarios),
            'case_concernee_vide': sum(1 for s in self.scenarios if s[self.enonce_config.get('condition_principale', {}).get('case', 0)] == 0),
            'case_concernee_non_vide': sum(1 for s in self.scenarios if s[self.enonce_config.get('condition_principale', {}).get('case', 0)] > 0),
            'valeurs_max': [max(s) for s in self.scenarios],
            'valeurs_min': [min(s) for s in self.scenarios]
        }
        return stats
    
    def _generate_random_scenario(self):
        """Génère un scénario aléatoire pour plus de variété pendant l'entraînement"""
        case_idx = self.enonce_config.get('condition_principale', {}).get('case', 0)

        # Probabilités pour différents types de scénarios
        scenario_type = np.random.choice(['focused', 'mixed', 'edge', 'high'], p=[0.4, 0.3, 0.2, 0.1])

        if scenario_type == 'focused':
            # Focus sur la case principale avec valeurs variées
            scenario = [0, 0, 0, 0]
            scenario[case_idx] = np.random.randint(0, 21)  # 0-20
            # Parfois ajouter une petite valeur sur une autre case
            if np.random.random() < 0.3:
                other_case = np.random.choice([i for i in range(4) if i != case_idx])
                scenario[other_case] = np.random.randint(1, 6)

        elif scenario_type == 'mixed':
            # Valeurs mixtes sur toutes les cases
            scenario = [np.random.randint(0, 11) for _ in range(4)]

        elif scenario_type == 'edge':
            # Scénarios edge cases
            if self.enonce_config.get('type') == 'conditionnel_imbrique':
                # Pour imbrication, focus sur les transitions critiques
                scenario = [0, 0, 0, 0]
                scenario[case_idx] = np.random.choice([0, 1, 2, 3, 5, 8, 10])
            else:
                scenario = [np.random.randint(0, 6) for _ in range(4)]

        else:  # high
            # Valeurs élevées
            scenario = [np.random.randint(5, 21) for _ in range(4)]

        return scenario
    
    def _compute_expected_result(self, scenario):
        """Calcule le résultat attendu selon l'énoncé"""
        expected = scenario.copy()
        config = self.enonce_config
        
        if config['type'] == 'conditionnel_imbrique':
            case_idx = config['condition_principale']['case']
            
            # Vérifier condition principale
            if config['condition_principale']['type'] == 'non_vide':
                if scenario[case_idx] > 0:
                    # Exécuter action principale
                    if config['action_principale']['operation'] == 'retirer':
                        expected[case_idx] -= 1
                    else:
                        expected[case_idx] += 1
                    
                    # Vérifier condition secondaire
                    if 'condition_secondaire' in config:
                        condition_met = False
                        if config['condition_secondaire']['type'] == 'vide':
                            condition_met = (expected[case_idx] == 0)
                        elif config['condition_secondaire']['type'] == 'non_vide':
                            condition_met = (expected[case_idx] > 0)
                        
                        if condition_met:
                            # Exécuter action secondaire
                            if config['action_secondaire']['operation'] == 'ajouter':
                                expected[case_idx] += 1
                            elif config['action_secondaire']['operation'] == 'retirer':
                                if expected[case_idx] > 0:
                                    expected[case_idx] -= 1
        
        elif config['type'] == 'conditionnel':
            # Logique simple sans imbrication
            case_idx = config['condition_principale']['case']
            
            if config['condition_principale']['type'] == 'non_vide':
                if scenario[case_idx] > 0:
                    if config['action_principale']['operation'] == 'retirer':
                        expected[case_idx] -= 1
                    else:
                        expected[case_idx] += 1
            elif config['condition_principale']['type'] == 'vide':
                if scenario[case_idx] == 0:
                    if config['action_principale']['operation'] == 'retirer':
                        expected[case_idx] -= 1
                    else:
                        expected[case_idx] += 1
        
        elif config['type'] == 'simple':
            # Action inconditionnelle
            case_idx = config['action_principale']['case']
            if config['action_principale']['operation'] == 'ajouter':
                expected[case_idx] += 1
            elif config['action_principale']['operation'] == 'retirer' and scenario[case_idx] > 0:
                expected[case_idx] -= 1
        
        return expected
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.current_step = 0
        self.code = []
        self.depth_stack = []
        self.episode_count += 1
        
        if options and 'plateau' in options:
            self.plateau_initial = options['plateau'].copy()
        else:
            # Alterner entre scénarios prédéfinis et scénarios aléatoires pour plus de variété
            if np.random.random() < 0.7:  # 70% du temps, utiliser scénarios prédéfinis
                self.scenario_idx = np.random.randint(0, len(self.scenarios))
                self.plateau_initial = self.scenarios[self.scenario_idx].copy()
            else:  # 30% du temps, générer un scénario aléatoire
                self.plateau_initial = self._generate_random_scenario()
        
        self.target_plateau = self._compute_expected_result(self.plateau_initial)
        
        return self._get_observation(), {}
    
    def _get_observation(self):
        """Observation enrichie avec encodage de l'énoncé"""
        depth = len(self.depth_stack)
        code_length = len(self.code)
        
        # Compter les SI ouverts par type
        si_ouverts = [0, 0, 0, 0]
        for action in self.depth_stack:
            case_idx = action % 4
            si_ouverts[case_idx] += 1
        
        last_action = self.code[-1] if self.code else -1
        
        # Encodage de l'énoncé
        enonce_encoded = self._encode_enonce()
        
        # Pour les énoncés imbriqués, ajouter la position dans la séquence
        if self.enonce_config['type'] == 'conditionnel_imbrique':
            code_len = len(self.code)
            if code_len == 0:
                enonce_encoded[24] = 0.0  # Attendre SI principal
            elif code_len == 1:
                enonce_encoded[24] = 0.2  # Attendre action principale
            elif code_len == 2:
                enonce_encoded[24] = 0.4  # Attendre SI secondaire
            elif code_len == 3:
                enonce_encoded[24] = 0.6  # Attendre action secondaire
            elif code_len == 4:
                enonce_encoded[24] = 0.8  # Attendre premier FIN_SI
            elif code_len == 5:
                enonce_encoded[24] = 0.9  # Attendre deuxième FIN_SI
            else:
                enonce_encoded[24] = 1.0  # Attendre STOP
        
        # Code paddé
        code_padded = (self.code + [0] * 50)[:50]
        
        obs = np.array([
            self.current_step,
            depth,
            code_length,
            last_action,
            *enonce_encoded,  # 20 valeurs
            *si_ouverts,      # 4 valeurs
            *code_padded      # 50 valeurs
        ], dtype=np.float32)
        
        return obs
    
    def step(self, action):
        if isinstance(action, np.ndarray):
            action = action.item()
        else:
            action = int(action)
        
        self.code.append(action)
        self.current_step += 1
        
        terminated = False
        truncated = False
        reward = 0.0
        
        # Mettre à jour la pile de profondeur
        if 8 <= action <= 15:  # SI
            self.depth_stack.append(action)
        elif action == 16:  # FIN_SI
            if self.depth_stack:
                self.depth_stack.pop()
        
        # PÉNALITÉ IMMÉDIATE pour actions parasites
        config = self.enonce_config
        case_idx = config.get('condition_principale', {}).get('case', 0)
        depth = len(self.depth_stack)
        code_len = len(self.code)
        
        if action < 16 and action != 17:  # Si ce n'est pas STOP ou FIN_SI
            action_case = action % 4
            # Action sur mauvaise case
            if action_case != case_idx:
                reward -= 100.0
            
            # Action parasite après structure complète - TERMINER L'ÉPISODE IMMÉDIATEMENT
            if config['type'] == 'conditionnel' and depth == 0 and code_len >= 4:
                reward -= 1000.0  # Pénalité énorme
                terminated = True  # TERMINER L'ÉPISODE
                truncated = False
            elif config['type'] == 'conditionnel_imbrique' and depth == 0 and code_len >= 7:
                reward -= 1000.0  # Pénalité énorme
                terminated = True  # TERMINER L'ÉPISODE
                truncated = False
        
        # Reward structurel
        reward += self._compute_structural_reward(action)
        
        # Validation par simulation
        plateau_simule, _, succes = self.interpreter.executer(self.code, self.plateau_initial)
        
        if not succes:
            reward -= 50.0
        
        # Fin d'épisode
        if action == 17:  # STOP
            terminated = True
            reward += self._compute_final_reward(plateau_simule, succes)
        elif self.current_step >= 49:
            terminated = True
            truncated = True
            reward -= 100.0
        
        return self._get_observation(), reward, terminated, truncated, {}
    
    def _compute_structural_reward(self, action):
        """Récompenses structurelles adaptées à l'énoncé avec focus sur imbrication"""
        reward = 0.0
        depth = len(self.depth_stack)
        code_len = len(self.code)
        config = self.enonce_config
        
        # Récupérer les actions attendues selon l'énoncé
        case_idx = config.get('condition_principale', {}).get('case', 0)
        
        # Action SI attendue
        if config.get('condition_principale', {}).get('type') == 'non_vide':
            expected_si = 12 + case_idx
        else:
            expected_si = 8 + case_idx
        
        # Action principale attendue
        if config.get('action_principale', {}).get('operation') == 'retirer':
            expected_action = 4 + case_idx
        else:
            expected_action = case_idx
        
        # Récompenses selon la progression
        if code_len == 1 and action == expected_si:
            reward += 300.0  # Bon départ - augmenté
        
        elif code_len == 2 and action == expected_action and depth == 1:
            reward += 300.0  # Bonne action principale - augmenté
        
        # Pour imbrication - récompenses plus fortes
        if config['type'] == 'conditionnel_imbrique':
            if config.get('condition_secondaire', {}).get('type') == 'vide':
                expected_si_2 = 8 + case_idx
            else:
                expected_si_2 = 12 + case_idx
            
            if code_len == 3 and action == expected_si_2 and depth == 1:
                reward += 400.0  # Bonne condition secondaire - augmenté
            
            # Action secondaire
            if config.get('action_secondaire', {}).get('operation') == 'ajouter':
                expected_action_2 = case_idx
            else:
                expected_action_2 = 4 + case_idx
            
            if code_len == 4 and action == expected_action_2 and depth == 2:
                reward += 500.0  # Bonne action secondaire - augmenté
            
            # Récompenses pour fermer les structures correctement
            if code_len == 5 and action == 16 and depth == 2:  # Premier FIN_SI
                reward += 300.0
            elif code_len == 6 and action == 16 and depth == 1:  # Deuxième FIN_SI
                reward += 400.0
        
        # FIN_SI général
        if action == 16:
            if depth > 0:
                reward += 50.0 + depth * 20.0  # Récompense progressive selon profondeur
            else:
                reward -= 200.0  # Pénalité plus forte pour FIN_SI incorrect
        
        # STOP
        elif action == 17:
            min_length = 7 if config['type'] == 'conditionnel_imbrique' else 4
            if depth == 0 and code_len >= min_length:
                reward += 150.0
            elif code_len < 3:
                reward -= 600.0
            else:
                reward -= 150.0
        
        # Pénalités renforcées pour actions parasites
        if config['type'] == 'conditionnel' and code_len >= 4:
            reward -= 200.0  # Pénalité très forte pour toute action après la structure complète
        
        if config['type'] == 'conditionnel_imbrique' and code_len >= 8:
            reward -= 200.0  # Même chose pour imbriqué
        
        # Pénalité pour actions sur mauvaises cases à n'importe quelle étape
        if action < 16:  # Si c'est une action (pas SI, FIN_SI, STOP)
            action_case = action % 4
            if action_case != case_idx:
                reward -= 150.0  # Pénalité renforcée pour actions sur mauvaises cases
        
        # Pénalité pour actions inutiles (Ajouter/Retirer) quand la structure est complète
        if config['type'] == 'conditionnel' and depth == 0 and code_len >= 3 and action < 8:
            reward -= 300.0  # Actions directes interdites après fermeture de la structure
        
        if config['type'] == 'conditionnel_imbrique' and depth == 0 and code_len >= 6 and action < 8:
            reward -= 300.0  # Même chose pour imbriqué
        
        # Récompense bonus pour code concis correct
        if config['type'] == 'conditionnel' and code_len == 4 and depth == 0 and action == 17:
            reward += 200.0  # Code parfait pour énoncé simple
        
        if config['type'] == 'conditionnel_imbrique' and code_len == 7 and depth == 0 and action == 17:
            reward += 300.0  # Code parfait pour énoncé imbriqué
            
            # Pénalité pour SI imbriqué trop tôt
            if config['type'] == 'conditionnel_imbrique' and action >= 8 and action <= 15:
                if code_len < 2:  # Pas de SI imbriqué avant action principale
                    reward -= 100.0
        
        return reward
    
    def _compute_final_reward(self, plateau_simule, succes):
        """Récompense finale basée sur tous les scénarios"""
        reward = 0.0
        
        if not succes:
            return -500.0
        
        scenarios_corrects = 0
        
        for scenario in self.scenarios:
            s_final, _, ok = self.interpreter.executer(self.code, scenario)
            expected = self._compute_expected_result(scenario)
            
            if ok and s_final == expected:
                scenarios_corrects += 1
        
        taux = scenarios_corrects / len(self.scenarios)
        reward += taux * 2000.0
        
        if scenarios_corrects == len(self.scenarios):
            reward += 5000.0
            
            min_length = 7 if self.enonce_config['type'] == 'conditionnel_imbrique' else 4
            optimal_length = min_length
            length_penalty = abs(len(self.code) - optimal_length) * 500.0  # Pénalité beaucoup plus forte
            reward += 2000.0 - length_penalty
            
            if len(self.code) == optimal_length:
                reward += 2000.0  # Bonus doublé pour longueur optimale
            
            if reward > self.best_reward:
                self.best_reward = reward
                self.best_code = self.code.copy()
        
        reward -= len(self.code) * 5.0  # Pénalité de longueur augmentée
        
        return reward
    
    def action_masks(self):
        """Masques plus stricts pour guider l'agent dans les imbrications"""
        mask = np.ones(18, dtype=np.bool_)
        depth = len(self.depth_stack)
        code_len = len(self.code)
        
        # Règles de base
        if depth == 0:
            mask[16] = False  # Pas de FIN_SI si pas de SI ouvert
        
        if depth >= 3:
            mask[8:16] = False  # Maximum 3 niveaux d'imbrication
        
        if self.current_step >= 49:
            mask[:] = False
            mask[17] = True  # Forcer STOP en fin d'épisode
            return mask
        
        config = self.enonce_config
        case_idx = config.get('condition_principale', {}).get('case', 0)
        
        # Logique spécifique selon le type d'énoncé
        if config['type'] == 'conditionnel_imbrique':
            # Séquence stricte pour imbrication
            if code_len == 0:
                # Seulement le SI principal attendu
                mask[:] = False
                if config.get('condition_principale', {}).get('type') == 'non_vide':
                    mask[12 + case_idx] = True  # SI NON Est_vide
                else:
                    mask[8 + case_idx] = True   # SI Est_vide
                mask[17] = True  # STOP toujours possible
            
            elif code_len == 1 and depth == 1:
                # Après SI principal, seulement action sur la bonne case
                mask[:] = False
                if config.get('action_principale', {}).get('operation') == 'retirer':
                    mask[4 + case_idx] = True
                else:
                    mask[case_idx] = True
                mask[17] = True
            
            elif code_len == 2 and depth == 1:
                # Après action principale, seulement SI secondaire sur même case
                mask[:] = False
                if config.get('condition_secondaire', {}).get('type') == 'vide':
                    mask[8 + case_idx] = True
                else:
                    mask[12 + case_idx] = True
                mask[16] = True  # Possibilité de fermer prématurément
                mask[17] = True
            
            elif code_len == 3 and depth == 2:
                # Après SI secondaire, seulement action secondaire
                mask[:] = False
                if config.get('action_secondaire', {}).get('operation') == 'retirer':
                    mask[4 + case_idx] = True
                else:
                    mask[case_idx] = True
                mask[17] = True
            
            elif code_len == 4 and depth == 2:
                # Après action secondaire, seulement FIN_SI
                mask[:] = False
                mask[16] = True
                mask[17] = True
            
            elif code_len == 5 and depth == 1:
                # Après premier FIN_SI, seulement deuxième FIN_SI ou STOP
                mask[:] = False
                mask[16] = True  # FIN_SI
                mask[17] = True  # STOP
            
            elif code_len >= 6 and depth == 0:
                # APRÈS fermeture complète de toutes les structures imbriquées, UNIQUEMENT STOP - AUCUNE EXCEPTION
                mask[:] = False
                mask[17] = True  # SEULEMENT STOP
                # Vérification supplémentaire : s'assurer qu'aucune action n'est permise
                for i in range(17):
                    mask[i] = False
        
        elif config['type'] == 'conditionnel':
            # Logique simple pour conditionnels non imbriqués
            if code_len == 0:
                mask[:] = False
                if config.get('condition_principale', {}).get('type') == 'non_vide':
                    mask[12 + case_idx] = True
                else:
                    mask[8 + case_idx] = True
                mask[17] = True
            
            elif code_len == 1 and depth == 1:
                mask[:] = False
                if config.get('action_principale', {}).get('operation') == 'retirer':
                    mask[4 + case_idx] = True
                else:
                    mask[case_idx] = True
                mask[17] = True
            
            elif code_len >= 2 and depth == 1:
                mask[:] = False
                mask[16] = True  # FIN_SI
                mask[17] = True  # STOP
            
            elif code_len >= 3 and depth == 0:
                # APRÈS fermeture complète de la structure, UNIQUEMENT STOP - AUCUNE EXCEPTION
                mask[:] = False
                mask[17] = True  # SEULEMENT STOP
                # Vérification supplémentaire : s'assurer qu'aucune action n'est permise
                for i in range(17):
                    mask[i] = False
        
        # Interdire STOP si code trop court pour énoncés imbriqués
        min_length = 7 if config['type'] == 'conditionnel_imbrique' else 4
        if code_len < min_length:
            mask[17] = False
        
        # TEMPORAIRE: Permettre plus d'actions pour faciliter l'apprentissage
        # SÉCURITÉ: S'assurer qu'au moins STOP et quelques actions de base sont possibles
        if not np.any(mask):
            mask[17] = True  # Forcer STOP si rien d'autre n'est possible
            # Permettre aussi quelques actions de base pour éviter les blocages
            if config['type'] == 'conditionnel':
                mask[16] = True  # FIN_SI
            elif config['type'] == 'conditionnel_imbrique':
                mask[16] = True  # FIN_SI
        
        return mask
    
    def set_enonce(self, enonce_config):
        """Change l'énoncé pour un nouvel entraînement"""
        self.enonce_config = enonce_config
        self.scenarios = self._generate_scenarios()
        self.best_reward = -float('inf')
        self.best_code = None