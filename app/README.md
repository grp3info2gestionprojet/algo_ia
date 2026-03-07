# RL Teacher/Student Platform

## Demo accounts
- teacher / teacher
- student / student

## Run
```bash
cd app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://localhost:8000

## Features
- Teacher login
- Teacher creates exercise with multiple rules
- Live JSON generation matching RL format
- Preview panel with recommended RL response (placeholder: first applicable rule)
- Publish exercise and generate session code
- Student sees published exercises
- Student solves via drag & drop blocks instead of copy/paste
- Student can ask for help and submit a solution
- SQLite database included automatically

## Notes
- The RL decision function is currently a deterministic placeholder (`generate_teacher_preview`).
- Replace it with your Masked PPO inference while keeping the same API endpoints.
