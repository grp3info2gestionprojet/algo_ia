# Masked PPO (RL) sur système de jetons HTML + Flask

## Idée RL
- **État** = vecteur [r, v, b, j, ...]
- **Actions** = index de règle (0..N-1)
- **Masque d'actions** = une règle est sélectionnable uniquement si sa `condition` est vraie.
- **Transition** = appliquer `updates` de la règle choisie.
- **Reward**:
  - +1 si `target` atteint OU si `goal_condition` vraie
  - -0.01 par pas (encourage à réussir vite)

## Lancer
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Ouvre: http://localhost:8000

## Champs JSON
- init: dict
- max_steps: int
- rules.vars: liste des variables
- rules.rules: liste des règles {name, condition, updates}
- optionnel: target (dict) ou goal_condition (string Python)

## API
- POST /api/train : entraîne MaskablePPO
- POST /api/run   : exécute la policy entraînée
- POST /api/one_step : debug (une itération)
- POST /api/pseudocode : pseudo-code est_vide/non est_vide