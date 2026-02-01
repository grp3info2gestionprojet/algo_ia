from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
import Environnement_Generique as EnvGen
import Algorithme_Interpreter as Interpret
import numpy as np
import os


class MultiEnonceCallback(BaseCallback):
    """Callback pour entraînement multi-énoncés"""
    
    def __init__(self, verbose=1):
        super(MultiEnonceCallback, self).__init__(verbose)
        self.episode_rewards = []
        self.current_reward = 0
        self.n_episodes = 0
        self.solutions_par_enonce = {}
    
    def _on_step(self):
        self.current_reward += self.locals['rewards'][0]
        
        if self.locals['dones'][0]:
            self.episode_rewards.append(self.current_reward)
            self.n_episodes += 1
            
            if self.n_episodes % 200 == 0:
                recent = self.episode_rewards[-200:]
                mean_r = np.mean(recent)
                max_r = np.max(recent)
                
                print(f"\n📊 Episode {self.n_episodes:6d} | "
                      f"Mean(200): {mean_r:7.1f} | "
                      f"Max(200): {max_r:7.1f}")
            
            self.current_reward = 0
        
        return True


# Définir plusieurs énoncés pour l'entraînement
ENONCES = {
    'enonce_1_imbrique': {
        'type': 'conditionnel_imbrique',
        'description': 'Si R non vide: retirer 1, puis si R vide: ajouter 1',
        'condition_principale': {'case': 0, 'type': 'non_vide'},
        'action_principale': {'case': 0, 'operation': 'retirer'},
        'condition_secondaire': {'case': 0, 'type': 'vide'},
        'action_secondaire': {'case': 0, 'operation': 'ajouter'}
    },
    'enonce_2_simple_B': {
        'type': 'conditionnel',
        'description': 'Si B non vide: retirer 1 de B',
        'condition_principale': {'case': 1, 'type': 'non_vide'},
        'action_principale': {'case': 1, 'operation': 'retirer'}
    },
    'enonce_3_simple_V': {
        'type': 'conditionnel',
        'description': 'Si V vide: ajouter 1 à V',
        'condition_principale': {'case': 2, 'type': 'vide'},
        'action_principale': {'case': 2, 'operation': 'ajouter'}
    },
    'enonce_4_imbrique_J': {
        'type': 'conditionnel_imbrique',
        'description': 'Si J non vide: ajouter 1, puis si J >= 2: retirer 1',
        'condition_principale': {'case': 3, 'type': 'non_vide'},
        'action_principale': {'case': 3, 'operation': 'ajouter'},
        'condition_secondaire': {'case': 3, 'type': 'non_vide'},
        'action_secondaire': {'case': 3, 'operation': 'retirer'}
    }
}


def test_enonce(model, enonce_name, enonce_config, interpreter):
    """Test un énoncé spécifique"""
    print(f"\n{'='*70}")
    print(f"TEST: {enonce_name}")
    print(f"Description: {enonce_config['description']}")
    print(f"{'='*70}")
    
    # Créer environnement avec cet énoncé
    env_test = EnvGen.EnvironnementGenerique(enonce_config)
    
    # Générer algorithme
    obs, _ = env_test.reset(options={'plateau': [2, 2, 2, 2]})
    terminated = False
    
    while not terminated:
        masks = env_test.action_masks()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        obs, reward, terminated, truncated, info = env_test.step(action)
    
    code = env_test.code.copy()
    print(f"\n🔍 Algorithme généré:")
    interpreter.print_algo(code)
    
    # Tester sur tous les scénarios
    successes = 0
    for idx, scenario in enumerate(env_test.scenarios):
        s_final, _, ok = interpreter.executer(code, scenario)
        expected = env_test._compute_expected_result(scenario)
        
        success = ok and s_final == expected
        if success:
            successes += 1
        
        status = "✅" if success else "❌"
        exec_status = "OK" if ok else "ERR"
        s_final_str = str(s_final) if s_final else "ERR"
        
        if not success:  # Afficher seulement les échecs
            print(f"{status} {scenario} → {s_final_str:20} (attendu: {expected}) | {exec_status}")
    
    taux = successes / len(env_test.scenarios) * 100
    print(f"\n📈 Résultat: {successes}/{len(env_test.scenarios)} ({taux:.1f}%)")
    
    return taux, code


print("="*70)
print("ENTRAÎNEMENT MULTI-ÉNONCÉS")
print("="*70)

print(f"\n📚 Nombre d'énoncés: {len(ENONCES)}")
for name, config in ENONCES.items():
    print(f"  - {name}: {config['description']}")

# STRATÉGIE 1: Curriculum Learning (du simple au complexe)
print("\n" + "="*70)
print("STRATÉGIE: Curriculum Learning")
print("="*70)

interpreter = Interpret.AlgorithmeInterpreter()

# Phase 1: Apprendre sur énoncés simples
print("\n📘 PHASE 1: Énoncés simples (conditionnels)")

enonces_simples = ['enonce_2_simple_B', 'enonce_3_simple_V']

for enonce_name in enonces_simples:
    print(f"\n🎯 Entraînement sur: {enonce_name}")
    
    env = EnvGen.EnvironnementGenerique(ENONCES[enonce_name])
    
    model_path = f"agent_{enonce_name}.zip"
    
    # FORCER LA CRÉATION DE NOUVEAUX MODÈLES (pas de chargement des anciens)
    print(f"   Création d'un nouveau modèle (anciens modèles supprimés)...")
    model = MaskablePPO(
        "MlpPolicy",
        env,
        learning_rate=1e-4,   # Paramètre standard
        n_steps=2048,         # Taille standard
        batch_size=64,        # Taille standard
        ent_coef=0.01,        # Entropie standard
        vf_coef=0.5,
        max_grad_norm=0.5,
        clip_range=0.2,
        verbose=0
    )
    
    callback = MultiEnonceCallback()
    
    print(f"   Entraînement: 10k steps...")  # Augmenté pour énoncés simples
    model.learn(total_timesteps=10000, callback=callback, reset_num_timesteps=False)
    
    model.save(model_path)
    
    # Test rapide
    taux, _ = test_enonce(model, enonce_name, ENONCES[enonce_name], interpreter)

# Définir le modèle de base pour le transfer learning
base_model_path = f"agent_{enonces_simples[-1]}.zip"

# Phase 1.5: Apprendre structures imbriquées simples (préparation)
print("\n" + "="*70)
print("📘 PHASE 1.5: Préparation aux imbrications")
print("="*70)

# Créer un énoncé intermédiaire simple pour pratiquer l'imbrication
enonce_preparation = {
    'type': 'conditionnel_imbrique',
    'description': 'SI R non vide: ajouter 1, puis si R >= 2: retirer 1 (simple)',
    'condition_principale': {'case': 0, 'type': 'non_vide'},
    'action_principale': {'case': 0, 'operation': 'ajouter'},
    'condition_secondaire': {'case': 0, 'type': 'non_vide'},  # Simplifié
    'action_secondaire': {'case': 0, 'operation': 'retirer'}
}

print(f"\n🎯 Entraînement préparatoire sur structure imbriquée simple")

env_prep = EnvGen.EnvironnementGenerique(enonce_preparation)
model_prep_path = "agent_preparation_imbrique.zip"

model_prep_path = "agent_preparation_imbrique.zip"

# FORCER CRÉATION NOUVEAU MODÈLE PRÉPARATOIRE
print(f"   Création nouveau modèle préparatoire...")
model_prep = MaskablePPO(
    "MlpPolicy",
    env_prep,
    learning_rate=1e-4,   # Paramètre standard
    n_steps=2048,         # Standard
    batch_size=64,        # Standard
    ent_coef=0.01,        # Standard
    vf_coef=0.5,
    max_grad_norm=0.5,
    clip_range=0.2,
    verbose=0
)

callback_prep = MultiEnonceCallback()
print(f"   Entraînement préparatoire: 50k steps...")
model_prep.learn(total_timesteps=50000, callback=callback_prep, reset_num_timesteps=False)
model_prep.save(model_prep_path)

# Test de la préparation
taux_prep, _ = test_enonce(model_prep, "préparation_imbrique", enonce_preparation, interpreter)
print(f"   Taux préparation: {taux_prep:.1f}%")

# Phase 2: Apprendre sur énoncés imbriqués (transfer learning)
print("\n" + "="*70)
print("📕 PHASE 2: Énoncés imbriqués (avec transfer)")
print("="*70)

enonces_imbriques = ['enonce_1_imbrique', 'enonce_4_imbrique_J']

# Partir du modèle préparatoire pour faire du transfer
base_model_path = "agent_preparation_imbrique.zip"

for enonce_name in enonces_imbriques:
    print(f"\n🎯 Entraînement sur: {enonce_name}")
    
    env = EnvGen.EnvironnementGenerique(ENONCES[enonce_name])
    
    model_path = f"agent_{enonce_name}.zip"
    
    # FORCER CRÉATION NOUVEAU MODÈLE (pas de transfer learning)
    print(f"   Création nouveau modèle pour {enonce_name}...")
    model = MaskablePPO(
        "MlpPolicy",
        env,
        learning_rate=1e-4,   # Paramètre standard pour stabilité
        n_steps=2048,         # Standard
        batch_size=64,        # Standard
        ent_coef=0.01,        # Entropie standard
        vf_coef=0.5,
        max_grad_norm=0.5,
        clip_range=0.2,
        verbose=0
    )
    
    callback = MultiEnonceCallback()
    
    print(f"   Entraînement: 50k steps...")  # Augmenté pour énoncés imbriqués
    model.learn(total_timesteps=50000, callback=callback, reset_num_timesteps=False)
    
    model.save(model_path)
    
    # Test rapide
    taux, _ = test_enonce(model, enonce_name, ENONCES[enonce_name], interpreter)

# ÉVALUATION FINALE
print("\n" + "="*70)
print("📊 ÉVALUATION FINALE - Tous les énoncés")
print("="*70)

resultats = {}

for enonce_name, enonce_config in ENONCES.items():
    model_path = f"agent_{enonce_name}.zip"
    
    if os.path.exists(model_path):
        model = MaskablePPO.load(model_path)
        taux, code = test_enonce(model, enonce_name, enonce_config, interpreter)
        resultats[enonce_name] = {'taux': taux, 'code': code}
    else:
        print(f"\n⚠️  Modèle non trouvé pour {enonce_name}")

# Résumé
print("\n" + "="*70)
print("📈 RÉSUMÉ DES PERFORMANCES")
print("="*70)

for enonce_name, res in resultats.items():
    status = "✅" if res['taux'] == 100.0 else "⚠️" if res['taux'] >= 80.0 else "❌"
    print(f"{status} {enonce_name:25s}: {res['taux']:5.1f}%")

moyenne = np.mean([r['taux'] for r in resultats.values()])
print(f"\n🎯 Taux de réussite moyen: {moyenne:.1f}%")

if moyenne == 100.0:
    print("\n🎉🎉🎉 VICTOIRE TOTALE! L'agent maîtrise tous les énoncés! 🎉🎉🎉")
elif moyenne >= 80.0:
    print("\n🎊 Excellent! L'agent généralise bien!")
else:
    print("\n⚠️  Plus d'entraînement nécessaire pour certains énoncés")