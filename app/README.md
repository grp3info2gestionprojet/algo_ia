# RL Teacher/Student Platform

## Demo accounts

* teacher / teacher
* student / student

---

## Installation

### 1°) Installation with Docker

This is the recommended way to run the project.

Run:

```bash
docker-compose up --build
```

Open http://localhost:8000

Stop:
```bash
docker-compose down
```

Notes about Docker setup:

* The application runs inside a Docker container
* The backend server is executed in a production configuration (typically Gunicorn or equivalent WSGI server depending on your setup)
* The container isolates all dependencies (Python version, libraries, system dependencies)
* This ensures reproducibility across all environments (development, testing, production)
* The application is exposed on port 8000
* SQLite database is created and managed automatically inside the container if not present 

---

### 2°) Local installation

Run:

```bash
cd app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000

---

## Features

* Teacher login
* Teacher creates exercise with multiple rules
* Live JSON generation matching RL format
* Preview panel with recommended RL response (placeholder: first applicable rule)
* Publish exercise and generate session code
* Student sees published exercises
* Student solves via drag & drop blocks instead of copy/paste
* Student can ask for help and submit a solution
* SQLite database included automatically

---

## Notes

* The RL decision function is currently a deterministic placeholder (`generate_teacher_preview`)
* Replace it with your Masked PPO inference while keeping the same API endpoints
