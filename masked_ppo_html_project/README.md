# Masked PPO (RL) sur système de jetons — HTML + Flask

## Idée RL
- **État** = vecteur [b, j, r, v, ...]
- **Actions** = index de règle (0..N-1)
- **Masque d'actions** = une règle est sélectionnable uniquement si sa `condition` est vraie.
- **Transition** = appliquer `updates` de la règle choisie.
- **Reward**:
  - +1 si `target` atteint OU si `goal_condition` vraie
  - -0.01 par pas (encourage à réussir vite)

## Lancer
```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# Windows:
.venv\Scripts\activate
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


## Mise à jour (v2)
- Le pseudo-code ajoute automatiquement des tests `non est_vide(couleur)` si une règle retire des jetons (x<-x-1).
- Le masque d'actions tient compte de cette faisabilité (interdit les actions qui feraient des valeurs négatives).


## Mise à jour (v4)
- Le pseudo-code généré contient uniquement `algo_principal()` (pas d'utilitaires, pas de fonctions auxiliaires).
- Les retraits sont entourés de tests `non est_vide(couleur)` avant `retirer(→couleur)`.
- Structure `si / sinon / si / ...` (pas `sinon si`).


## Patch SafeB
Si goal_condition==b==0 et init.b==1 et qu'une règle fait b<-b-1, le pseudo-code généré devient le schéma 'retirer puis re-poser si vide'.


## Patch General SafeRemove + Conversion >=k
- Toutes les conditions x>=k (k>=1) sont converties en `non est_vide(couleur)`.
- Tout retrait `retirer(→couleur)` est généré sous la forme: si non vide(couleur) retirer ; si vide(couleur) poser.


## Patch k-correct
- x>=1 => non est_vide(couleur)
- x>=k (k>1) reste x>=k (ex b>=2)
- plus de 'poser' après retrait (corrige le cas b>=1 avec b=0)


## v6: Pseudo-code dépendant de la valeur courante
- Pour une condition x>=k :
  - affichage condition en `non est_vide(couleur)` (style demandé)
  - le corps dépend de la valeur courante x :
    - si x>=k : retirer seulement
    - si x<k : retirer puis si vide alors poser (schéma 'safe')
- /api/simulate renvoie la table d’itérations avec un champ `pseudocode` par ligne.
- /api/simulate_rl fait la même chose mais tente d’utiliser la policy Masked PPO via model_id.


## v7: Sélection 'soft' pour conditions x>=k
- Une règle avec condition x>=k peut être sélectionnée dès que x>0 (non-vide), même si x<k.
- Si x<k, l'environnement applique un 'safety wrapper' : après mise à jour, si x devient 0 alors on repose 1 jeton.
- Le pseudo-code affiché correspond à cette exécution sûre (retirer puis re-poser si vide).
