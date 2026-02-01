from sb3_contrib import MaskablePPO
import Environnement_Generique as EnvGen
import Algorithme_Interpreter as Interpret
import os


def creer_enonce_personnalise():
    """Interface pour créer un énoncé personnalisé"""
    print("="*70)
    print("CRÉATEUR D'ÉNONCÉ PERSONNALISÉ")
    print("="*70)
    
    print("\n📝 Type d'énoncé:")
    print("  1. Simple (action inconditionnelle)")
    print("  2. Conditionnel (SI ... ALORS ...)")
    print("  3. Conditionnel imbriqué (SI ... ALORS ... SI ... ALORS ...)")
    
    type_choice = input("\nChoix (1-3): ").strip()
    
    type_map = {
        '1': 'simple',
        '2': 'conditionnel',
        '3': 'conditionnel_imbrique'
    }
    
    enonce_type = type_map.get(type_choice, 'conditionnel')
    
    print("\n🎨 Case concernée:")
    print("  0. Rouge (R)")
    print("  1. Bleue (B)")
    print("  2. Verte (V)")
    print("  3. Jaune (J)")
    
    case_choice = input("\nChoix (0-3): ").strip()
    case_idx = int(case_choice) if case_choice in ['0','1','2','3'] else 0
    
    enonce = {
        'type': enonce_type,
        'description': ''
    }
    
    if enonce_type != 'simple':
        print("\n🔍 Condition principale:")
        print("  1. Si case vide")
        print("  2. Si case non vide")
        
        cond_choice = input("\nChoix (1-2): ").strip()
        cond_type = 'vide' if cond_choice == '1' else 'non_vide'
        
        enonce['condition_principale'] = {
            'case': case_idx,
            'type': cond_type
        }
    
    print("\n⚙️  Action principale:")
    print("  1. Ajouter un jeton")
    print("  2. Retirer un jeton")
    
    action_choice = input("\nChoix (1-2): ").strip()
    action_op = 'ajouter' if action_choice == '1' else 'retirer'
    
    enonce['action_principale'] = {
        'case': case_idx,
        'operation': action_op
    }
    
    if enonce_type == 'conditionnel_imbrique':
        print("\n🔍 Condition secondaire (imbriquée):")
        print("  1. Si case vide")
        print("  2. Si case non vide")
        
        cond2_choice = input("\nChoix (1-2): ").strip()
        cond2_type = 'vide' if cond2_choice == '1' else 'non_vide'
        
        enonce['condition_secondaire'] = {
            'case': case_idx,
            'type': cond2_type
        }
        
        print("\n⚙️  Action secondaire:")
        print("  1. Ajouter un jeton")
        print("  2. Retirer un jeton")
        
        action2_choice = input("\nChoix (1-2): ").strip()
        action2_op = 'ajouter' if action2_choice == '1' else 'retirer'
        
        enonce['action_secondaire'] = {
            'case': case_idx,
            'operation': action2_op
        }
    
    # Générer description
    cases_names = ['R', 'B', 'V', 'J']
    case_name = cases_names[case_idx]
    
    if enonce_type == 'simple':
        enonce['description'] = f"{action_op.capitalize()} 1 à {case_name}"
    elif enonce_type == 'conditionnel':
        cond_str = "vide" if cond_type == 'vide' else "non vide"
        enonce['description'] = f"Si {case_name} {cond_str}: {action_op} 1"
    else:
        cond1_str = "vide" if cond_type == 'vide' else "non vide"
        cond2_str = "vide" if cond2_type == 'vide' else "non vide"
        enonce['description'] = f"Si {case_name} {cond1_str}: {action_op} 1, puis si {case_name} {cond2_str}: {action2_op} 1"
    
    return enonce


def tester_enonce_avec_modele_existant(enonce, model_path):
    """Teste un énoncé avec un modèle pré-entraîné"""
    print("\n" + "="*70)
    print("TEST AVEC MODÈLE PRÉ-ENTRAÎNÉ")
    print("="*70)
    
    interpreter = Interpret.AlgorithmeInterpreter()
    
    # Créer environnement
    env = EnvGen.EnvironnementGenerique(enonce)
    
    print(f"\n📚 Énoncé: {enonce['description']}")
    print(f"📊 Scénarios de test: {len(env.scenarios)}")
    
    # Charger modèle
    print(f"\n🤖 Chargement du modèle: {model_path}")
    model = MaskablePPO.load(model_path, env=env)
    
    # Générer algorithme
    obs, _ = env.reset(options={'plateau': [3, 2, 1, 0]})
    terminated = False
    
    while not terminated:
        masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
    
    code = env.code.copy()
    
    print(f"\n🔍 Algorithme généré:")
    interpreter.print_algo(code)
    
    # Tester sur tous les scénarios
    print(f"\n🧪 Tests détaillés:")
    print("─" * 70)
    
    successes = 0
    for idx, scenario in enumerate(env.scenarios):
        s_final, _, ok = interpreter.executer(code, scenario)
        expected = env._compute_expected_result(scenario)
        
        success = ok and s_final == expected
        if success:
            successes += 1
        
        status = "✅" if success else "❌"
        exec_status = "OK" if ok else "ERR"
        s_final_str = str(s_final) if s_final else "ERR"
        
        print(f"{status} [{idx+1:2d}] {scenario} → {s_final_str:20} "
              f"(attendu: {expected}) | {exec_status}")
    
    print("─" * 70)
    
    taux = successes / len(env.scenarios) * 100
    print(f"\n📈 RÉSULTAT: {successes}/{len(env.scenarios)} ({taux:.1f}%)")
    
    if taux == 100.0:
        print("\n🎉 Parfait! L'agent a généralisé à ce nouvel énoncé!")
    elif taux >= 80.0:
        print("\n👍 Bon résultat, mais quelques ajustements nécessaires")
    else:
        print("\n⚠️  L'énoncé est trop différent, entraînement spécifique requis")
    
    return taux, code


def entrainer_sur_nouvel_enonce(enonce):
    """Entraîne spécifiquement sur un nouvel énoncé"""
    print("\n" + "="*70)
    print("ENTRAÎNEMENT SPÉCIFIQUE SUR NOUVEL ÉNONCÉ")
    print("="*70)
    
    from stable_baselines3.common.callbacks import BaseCallback
    import numpy as np
    
    class QuickCallback(BaseCallback):
        def __init__(self):
            super(QuickCallback, self).__init__(verbose=0)
            self.episode_rewards = []
            self.current_reward = 0
            self.n_episodes = 0
        
        def _on_step(self):
            self.current_reward += self.locals['rewards'][0]
            
            if self.locals['dones'][0]:
                self.episode_rewards.append(self.current_reward)
                self.n_episodes += 1
                
                if self.n_episodes % 100 == 0:
                    recent = self.episode_rewards[-100:]
                    mean_r = np.mean(recent)
                    print(f"Episode {self.n_episodes:5d} | Mean(100): {mean_r:7.1f}")
                
                self.current_reward = 0
            
            return True
    
    env = EnvGen.EnvironnementGenerique(enonce)
    
    print(f"\n📚 Énoncé: {enonce['description']}")
    
    # Essayer de charger un modèle similaire pour transfer learning
    similar_model = None
    if enonce['type'] == 'conditionnel_imbrique':
        for model_name in ['agent_enonce_1_imbrique.zip', 'agent_enonce_4_imbrique_J.zip']:
            if os.path.exists(model_name):
                print(f"\n🔄 Transfer learning depuis: {model_name}")
                similar_model = model_name
                break
    elif enonce['type'] == 'conditionnel':
        for model_name in ['agent_enonce_2_simple_B.zip', 'agent_enonce_3_simple_V.zip']:
            if os.path.exists(model_name):
                print(f"\n🔄 Transfer learning depuis: {model_name}")
                similar_model = model_name
                break
    
    if similar_model:
        model = MaskablePPO.load(similar_model, env=env)
    else:
        print("\n🆕 Création d'un nouveau modèle...")
        model = MaskablePPO(
            "MlpPolicy",
            env,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            ent_coef=0.05,
            verbose=0
        )
    
    callback = QuickCallback()
    
    timesteps = 100000 if enonce['type'] == 'conditionnel_imbrique' else 50000
    print(f"\n🚀 Entraînement: {timesteps} steps...")
    
    model.learn(total_timesteps=timesteps, callback=callback, progress_bar=True)
    
    model.save("agent_nouvel_enonce")
    print("\n✅ Modèle sauvegardé: agent_nouvel_enonce.zip")
    
    # Test final
    return tester_enonce_avec_modele_existant(enonce, "agent_nouvel_enonce.zip")


# PROGRAMME PRINCIPAL
if __name__ == "__main__":
    print("="*70)
    print("🎯 TEST D'ÉNONCÉ - Menu Principal")
    print("="*70)
    
    print("\nOptions:")
    print("  1. Créer et tester un énoncé personnalisé")
    print("  2. Tester un énoncé prédéfini")
    print("  3. Entraîner sur un nouvel énoncé")
    
    choice = input("\nChoix (1-3): ").strip()
    
    if choice == '1':
        enonce = creer_enonce_personnalise()
        
        print(f"\n✓ Énoncé créé: {enonce['description']}")
        print(f"  Type: {enonce['type']}")
        
        # Chercher un modèle compatible
        models_available = [f for f in os.listdir('.') if f.startswith('agent_') and f.endswith('.zip')]
        
        if models_available:
            print(f"\n🤖 Modèles disponibles: {len(models_available)}")
            
            # Choisir le modèle le plus approprié
            if enonce['type'] == 'conditionnel_imbrique':
                preferred = [m for m in models_available if 'imbrique' in m]
            else:
                preferred = [m for m in models_available if 'simple' in m]
            
            model_path = preferred[0] if preferred else models_available[0]
            
            taux, code = tester_enonce_avec_modele_existant(enonce, model_path)
            
            if taux < 80.0:
                print("\n💡 Voulez-vous entraîner spécifiquement sur cet énoncé? (o/n)")
                if input().strip().lower() == 'o':
                    entrainer_sur_nouvel_enonce(enonce)
        else:
            print("\n⚠️  Aucun modèle trouvé. Entraînement nécessaire.")
            print("💡 Lancez d'abord train_multi_enonces.py")
    
    elif choice == '2':
        # Énoncé prédéfini pour test rapide
        enonce_test = {
            'type': 'conditionnel',
            'description': 'Si R >= 5: retirer 2',
            'condition_principale': {'case': 0, 'type': 'non_vide'},
            'action_principale': {'case': 0, 'operation': 'retirer'}
        }
        
        print(f"\n📝 Énoncé de test: {enonce_test['description']}")
        
        models_available = [f for f in os.listdir('.') if f.startswith('agent_') and f.endswith('.zip')]
        if models_available:
            tester_enonce_avec_modele_existant(enonce_test, models_available[0])
        else:
            print("\n⚠️  Aucun modèle trouvé. Lancez train_multi_enonces.py d'abord")
    
    elif choice == '3':
        enonce = creer_enonce_personnalise()
        entrainer_sur_nouvel_enonce(enonce)