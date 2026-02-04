from __future__ import annotations
import os, uuid
from flask import Flask, request, jsonify, send_from_directory

from engine.core import parse_problem
from engine.one_step import one_step_transitions
from engine.pseudocode import generate_pseudocode
from engine.one_iter import one_iteration
from engine.rl import train_masked_ppo, rollout_policy
from engine.simulate import simulate

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(APP_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/simulate")
def api_simulate():
    payload = request.get_json(force=True, silent=False)
    prob = parse_problem(payload)
    return jsonify(simulate(prob, chooser="first"))

@app.post("/api/simulate_rl")
def api_simulate_rl():
    payload = request.get_json(force=True, silent=False)
    prob = parse_problem(payload)
    return jsonify(simulate(prob, chooser="rl"))

@app.post("/api/one_step")
def api_one_step():
    payload = request.get_json(force=True, silent=False)
    prob = parse_problem(payload)
    return jsonify({
        "init": prob["init"],
        "next_states": one_step_transitions(prob),
    })

@app.post("/api/one_iteration")
def api_one_iteration():
    payload = request.get_json(force=True, silent=False)
    prob = parse_problem(payload)
    return jsonify(one_iteration(prob))

@app.post("/api/pseudocode")
def api_pseudocode():
    payload = request.get_json(force=True, silent=False)
    prob = parse_problem(payload)
    return jsonify({"pseudocode": generate_pseudocode(prob)})

@app.post("/api/train")
def api_train():
    payload = request.get_json(force=True, silent=False)
    prob = parse_problem(payload)

    timesteps = int(payload.get("train_timesteps", 20000))
    seed = payload.get("seed", None)
    model_id = payload.get("model_id") or str(uuid.uuid4())[:8]
    model_path = os.path.join(MODELS_DIR, f"{model_id}.zip")

    info = train_masked_ppo(prob, timesteps=timesteps, model_path=model_path, seed=seed)
    info["model_id"] = model_id
    return jsonify(info)

@app.post("/api/run")
def api_run():
    payload = request.get_json(force=True, silent=False)
    prob = parse_problem(payload)

    model_id = payload.get("model_id")
    if not model_id:
        return jsonify({"error": "model_id manquant (entraîne d'abord)."}), 400

    model_path = os.path.join(MODELS_DIR, f"{model_id}.zip")
    if not os.path.exists(model_path):
        return jsonify({"error": f"Modèle introuvable: {model_id}"}), 404

    n_episodes = int(payload.get("n_episodes", 1))
    max_steps = int(payload.get("max_steps", prob["max_steps"]))
    return jsonify(rollout_policy(prob, model_path=model_path, n_episodes=n_episodes, max_steps=max_steps))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
