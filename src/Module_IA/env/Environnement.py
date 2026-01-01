import gym
from gym import spaces
import numpy as np
import Algorithme_Interpreter as AI

class Environnement(gym.Env):
    def __init__(self):
        super(Environnement, self).__init__()
        self.action_space = spaces.Discrete(18)
        self.observation_space = spaces.Box(low=0, high=50, shape=(8,), dtype=np.int32)
        
        self.interpreter = AI.AlgorithmeInterpreter()
        
        self.scenarios = [
            [0, 0, 0, 0], [0, 1, 1, 0], [1, 0, 0, 5], 
            [0, 1, 0, 0], [0, 0, 1, 2]
        ]
    

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
    
        self.current_step = 0
        self.depth = 0
        self.last_cond = 0
        self.is_not = 0
        self.code = []

        # Il faut modifier le vecteur obs en lui ajoutant les états finaux et les indicateurs de type (=, <, >).
        # C'est un total de 8 elm à ajouter (attendre que l'équipe de traduction fini)
        obs = np.array([*self.scenarios[0], 0, 0, 0, 0], dtype=np.int32)
        return obs, {}
    

    def step(self, action):
        if isinstance(action, np.ndarray):
            action = action.item()
        else:
            action = int(action)

        self.code.append(action)
    
        terminated = False
        truncated = False
        reward = 0
    
        # Actions 8-11: SI Est_vide, Actions 12-15: SI NON Est_vide
        if 8 <= action <= 15:
            self.depth += 1
            self.last_cond = action % 4
            self.is_not = 1 if action >= 12 else 0
        elif action == 16: # FIN_SI
            self.depth = max(0, self.depth - 1)

        # Vérifier si l'épisode est fini (STOP ou 50 lignes)
        if action == 17 or self.current_step >= 49:
            terminated = True
            reward = self.interpreter.evaluer_agent(self.code)
        else:
            reward = 0
            self.current_step += 1

        # Préparer l'observation pour la ligne suivante
        obs = np.array([
            *self.scenarios[0],
            self.current_step,
            self.depth,
            self.last_cond,
            self.is_not
        ], dtype=np.int32)

        return obs, reward, terminated, truncated, {}


    def action_masks(self):
        mask = np.ones(18, dtype=np.bool_)
        
        # Empêcher de Retirer si case vide
        for i in range(4):
            if self.scenarios[0][i] == 0:
                mask[i + 4] = False
        
        # Empêcher FIN_SI si aucun bloc SI n'est ouvert
        if self.depth == 0:
            mask[16] = False
                
        return mask