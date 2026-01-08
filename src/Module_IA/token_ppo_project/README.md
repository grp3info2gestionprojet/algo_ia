# Module IA – PPO + Générateur de pseudo-code (Plateau à jetons)

Ce projet implémente un agent d’apprentissage par renforcement basé sur PPO (Proximal Policy Optimization) afin de résoudre un problème de transformation d’état appelé « problème des jetons ».

L’agent apprend à transformer un état initial de jetons en un état cible en appliquant une suite d’actions élémentaires (poser / retirer un jeton), sans que la solution ne soit programmée explicitement.

Le système comprend :
- un environnement Gym personnalisé,
- une modélisation du problème sous forme de MDP,
- un agent PPO (acteur–critique),
- une fonction de récompense guidant l’apprentissage,
- la génération automatique du pseudo-code,
- et un tableau d’évolution des états permettant la validation des résultats.


## 1) Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Entraîner PPO
```bash
python train.py --total-timesteps 200000
tensorboard --logdir runs
```

## 3) Tester / Générer du pseudo-code
```bash
python infer.py --init "1,3,5,7" --target "2,2,4,6"
# ou
python infer.py --spec specs/exemple_1.json
```

## 4) Structure
- `envs/token_board_env.py` : environnement RL
- `ppo/ppo_agent.py` : réseau Actor/Critic
- `ppo/ppo_train_loop.py` : boucle PPO
- `pseudocode/generator.py` : actions -> pseudo-code + tableau de simulation
- `train.py` : entrypoint entraînement
- `infer.py` : entrypoint test + génération pseudo-code
- `specs/*.json` : exemples d’énoncé machine
