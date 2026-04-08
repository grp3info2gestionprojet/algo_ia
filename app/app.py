from __future__ import annotations
import json, sqlite3, secrets, sys
from functools import wraps
from pathlib import Path
from flask import Flask, g, render_template, request, redirect, url_for, session, jsonify, flash

# Ajout du dossier src au path pour les imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src' / 'Recommendation'))
from Recommandation import SystemeRecommandation, ALL_ACTIONS

# ── Moteur IA (Module_IA) ──
# Structure : algo_ia/src/Module_IA/engine/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src' / 'Module_IA'))
try:
    from engine.core import parse_problem as _parse_problem
    from engine.pseudocode import generate_pseudocode as _generate_pseudocode
    _ENGINE_AVAILABLE = True
except ImportError:
    _ENGINE_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'platform.db'

app = Flask(__name__)
app.secret_key = 'change-me-in-production'

# ---------------- DB ----------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('teacher','student'))
    );
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        init_b INTEGER NOT NULL,
        init_j INTEGER NOT NULL,
        init_r INTEGER NOT NULL,
        init_v INTEGER NOT NULL,
        goal_condition TEXT NOT NULL,
        max_steps INTEGER NOT NULL DEFAULT 30,
        problem_json TEXT NOT NULL,
        is_published INTEGER NOT NULL DEFAULT 0,
        session_code TEXT,
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS exercise_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        cond_color TEXT NOT NULL,
        cond_operator TEXT NOT NULL,
        cond_value INTEGER NOT NULL,
        delta_b INTEGER NOT NULL DEFAULT 0,
        delta_j INTEGER NOT NULL DEFAULT 0,
        delta_r INTEGER NOT NULL DEFAULT 0,
        delta_v INTEGER NOT NULL DEFAULT 0,
        position INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        blocks_json TEXT NOT NULL,
        generated_code TEXT NOT NULL,
        feedback_json TEXT,
        is_correct INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (exercise_id) REFERENCES exercises(id),
        FOREIGN KEY (student_id) REFERENCES users(id)
    );
    ''')
    # seed users
    cur = db.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        db.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", ('teacher','teacher','teacher'))
        db.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)", ('student','student','student'))
        db.commit()
    db.close()

    # Migration : ajouter is_correct si la colonne n'existe pas encore
    db = sqlite3.connect(DB_PATH)
    try:
        db.execute('ALTER TABLE submissions ADD COLUMN is_correct INTEGER NOT NULL DEFAULT 0')
        db.commit()
    except sqlite3.OperationalError:
        pass  # colonne déjà présente
    db.close()

init_db()

# ---------------- Auth ----------------
def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                return redirect(url_for('index'))
            return fn(*args, **kwargs)
        return wrapper
    return deco

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    return redirect(url_for('student_dashboard'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=? AND password=?', (username,password)).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        flash('Identifiants invalides', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- Helpers ----------------
COLOR_LABELS = {'b': 'Bleue', 'j': 'Jaune', 'r': 'Rouge', 'v': 'Verte'}
VARS = ['b','j','r','v']

# ---- Conversion blocs JS ↔ code_ids (AlgorithmeInterpreter) ----
_COLOR_MAP  = {'b': 0, 'j': 1, 'r': 2, 'v': 3}
_COLOR_NAMES = {0: 'bleue', 1: 'jaune', 2: 'rouge', 3: 'verte'}

def blocks_to_code_ids(blocks):
    """Convertit les blocs plats du frontend en liste de code_ids."""
    code_ids = []
    for b in blocks:
        c = _COLOR_MAP.get(b.get('color'), 0)
        t = b.get('type', '')
        if t == 'poser':                                  code_ids.append(c)
        elif t == 'retirer':                              code_ids.append(c + 4)
        elif t in ('if_empty', 'if_empty_else'):          code_ids.append(c + 8)
        elif t in ('if_not_empty', 'if_not_empty_else'):  code_ids.append(c + 12)
        elif t == 'sinon':                                code_ids.append(18)
        elif t == 'finsi':                                code_ids.append(16)
    code_ids.append(17)  # STOP
    return code_ids

def tronquer_code_partiel(code_ids):
    """
    Retire le STOP final et tous les FIN_SI qui le précèdent immédiatement,
    afin que le système de recommandation reçoive uniquement les instructions
    réellement saisies par l'étudiant, sans la fermeture automatique.

    Exemple : [12, 0, 16, 17] → [12, 0]
              [8, 0, 18, 4, 16, 17] → [8, 0, 18, 4]
    """
    ids = list(code_ids)
    # Retirer le STOP final
    if ids and ids[-1] == 17:
        ids.pop()
    # Retirer les FIN_SI qui terminent la séquence
    while ids and ids[-1] == 16:
        ids.pop()
    return ids


def code_ids_to_pseudocode(code_ids):
    """Convertit une liste de code_ids en pseudocode lisible numéroté."""
    lines = []
    depth = 0
    line_no = 1
    for action_id in code_ids:
        action = ALL_ACTIONS.get(action_id, '')
        if not action or action == 'STOP':
            break
        indent = '    ' * depth
        if action == 'FIN_SI':
            depth = max(0, depth - 1)
            indent = '    ' * depth
            lines.append(f"{line_no}: {indent}finsi"); line_no += 1
        elif action == 'SINON':
            depth = max(0, depth - 1)
            indent = '    ' * depth
            lines.append(f"{line_no}: {indent}sinon"); line_no += 1
            depth += 1
        elif action.startswith('SI NON Est_vide('):
            lines.append(f"{line_no}: {indent}si non est_vide({_COLOR_NAMES[action_id % 4]}) alors"); line_no += 1
            depth += 1
        elif action.startswith('SI Est_vide('):
            lines.append(f"{line_no}: {indent}si est_vide({_COLOR_NAMES[action_id % 4]}) alors"); line_no += 1
            depth += 1
        elif action.startswith('Ajouter('):
            lines.append(f"{line_no}: {indent}poser(→{_COLOR_NAMES[action_id % 4]})"); line_no += 1
        elif action.startswith('Retirer('):
            lines.append(f"{line_no}: {indent}retirer(→{_COLOR_NAMES[action_id % 4]})"); line_no += 1
    return '\n'.join(lines) if lines else '(algorithme vide)'

def recommandation_to_message(resultat):
    """Traduit le dict de SystemeRecommandation.recommander() en HTML lisible."""
    if resultat.get('code_correct'):
        return '✅ Votre algorithme est correct !'
    rec = resultat.get('recommandation')
    if rec is None:
        return 'Aucune recommandation disponible pour le moment.'
    labels = {'AJOUTER': '➕ Ajouter', 'SUPPRIMER': '🗑️ Supprimer', 'REMPLACER': '🔄 Remplacer'}
    label = labels.get(rec['type'], rec['type'])
    if rec['type'] == 'AJOUTER':
        return f"💡 <b>Prochaine action :</b> {label} <code>{rec['action_nom']}</code>"
    elif rec['type'] == 'SUPPRIMER':
        return (f"💡 <b>Prochaine action :</b> {label} la ligne {rec['position']} "
                f"(<code>{rec['action_nom']}</code>)")
    else:
        return (f"💡 <b>Prochaine action :</b> {label} la ligne {rec['position']} : "
                f"<code>{rec['action_remplacee']}</code> → <code>{rec['action_nom']}</code>")


def color_name(code):
    return COLOR_LABELS.get(code, code)


def exercise_to_json(ex_row, rules):
    problem = {
        'init': {
            'b': ex_row['init_b'],
            'j': ex_row['init_j'],
            'r': ex_row['init_r'],
            'v': ex_row['init_v'],
        },
        'max_steps': ex_row['max_steps'],
        'goal_condition': ex_row['goal_condition'],
        'rules': {
            'vars': VARS,
            'rules': []
        }
    }
    for r in rules:
        updates = {}
        for c in VARS:
            delta = int(r[f'delta_{c}'])
            if delta == 0:
                updates[c] = c
            elif delta > 0:
                updates[c] = f'{c}+{delta}'
            else:
                updates[c] = f'{c}{delta}'
        problem['rules']['rules'].append({
            'name': r['name'],
            'condition': f"{r['cond_color']}{r['cond_operator']}{r['cond_value']}",
            'updates': updates
        })
    return problem


def get_exercise(exercise_id: int):
    db = get_db()
    ex = db.execute('SELECT * FROM exercises WHERE id=?', (exercise_id,)).fetchone()
    rules = db.execute('SELECT * FROM exercise_rules WHERE exercise_id=? ORDER BY position,id', (exercise_id,)).fetchall()
    return ex, rules


def eval_condition(state, cond):
    cond = cond.replace(' ','')
    for op in ['>=','<=','==','>','<']:
        if op in cond:
            var, val = cond.split(op)
            x = int(state.get(var, 0)); n = int(val)
            return {'>=': x>=n, '<=': x<=n, '==': x==n, '>': x>n, '<': x<n}[op]
    return False


def parse_update_delta(expr, var):
    expr = str(expr).replace(' ','')
    if expr == var:
        return 0
    if expr.startswith(var + '+'):
        return int(expr.split('+',1)[1])
    if expr.startswith(var + '-'):
        return -int(expr.split('-',1)[1])
    return 0


def simulate_rule(problem, idx):
    state0 = dict(problem['init'])
    rule = problem['rules']['rules'][idx]
    cond_ok = eval_condition(state0, rule['condition']) if rule.get('condition') else True
    state1 = dict(state0)
    warnings = []
    if cond_ok:
        for v in VARS:
            delta = parse_update_delta(rule['updates'].get(v, v), v)
            if state1[v] + delta < 0:
                warnings.append(f"Retrait impossible sur {color_name(v)}")
                continue
            state1[v] += delta
    return {
        'rule_index': idx,
        'rule_name': rule['name'],
        'cond_ok': cond_ok,
        'state0': state0,
        'state1': state1,
        'warnings': warnings
    }


def pseudocode_to_code_ids(pseudocode: str) -> list:
    """
    Convertit le pseudo-code textuel produit par Module_IA en liste de code_ids
    compatibles avec AlgorithmeInterpreter / SystemeRecommandation.

    Mapping :
      poser(→bleue/jaune/rouge/verte)        →  0– 3
      retirer(→bleue/jaune/rouge/verte)      →  4– 7
      si (est_vide(couleur)) alors           →  8–11
      si (non est_vide(couleur)) alors       → 12–15
      finsi                                  → 16
      sinon                                  → 18
      STOP ajouté automatiquement            → 17
    Les lignes non reconnues sont ignorées.
    """
    COLOR_IDX = {'bleue': 0, 'jaune': 1, 'rouge': 2, 'verte': 3}
    code_ids = []

    for raw_line in pseudocode.splitlines():
        # Retirer le numéro de ligne éventuel ("12: …")
        line = raw_line.strip()
        if ':' in line:
            line = line.split(':', 1)[1].strip()
        lc = line.lower().replace(' ', '')

        if not lc or lc.startswith('algorithme') or lc.startswith('//'):
            continue

        if lc in ('finsi', 'fin_si'):
            code_ids.append(16)
            continue

        if lc in ('sinon'):
            code_ids.append(18)
            continue

        matched = False
        for color, idx in COLOR_IDX.items():
            if f'poser(→{color})' in lc or f'poser(->{color})' in lc:
                code_ids.append(idx)        # 0–3
                matched = True; break
        if matched: continue

        for color, idx in COLOR_IDX.items():
            if f'retirer(→{color})' in lc or f'retirer(->{color})' in lc:
                code_ids.append(idx + 4)    # 4–7
                matched = True; break
        if matched: continue

        for color, idx in COLOR_IDX.items():
            if f'nonest_vide({color})' in lc or (f'est_vide({color})' in lc and 'non' in lc):
                code_ids.append(idx + 12)   # 12–15
                matched = True; break
        if matched: continue

        for color, idx in COLOR_IDX.items():
            if f'est_vide({color})' in lc and 'non' not in lc:
                code_ids.append(idx + 8)    # 8–11
                break

    code_ids.append(17)  # STOP
    return code_ids


def generate_teacher_preview(problem):
    """
    Génère le pseudo-code de référence via le moteur Module_IA et le convertit
    en code_ids pour le système de recommandation.
    Retourne : { 'pseudocode': str, 'code_ids': list[int] }
    """
    if _ENGINE_AVAILABLE:
        try:
            prob = _parse_problem(problem)
            pseudocode = _generate_pseudocode(prob)
            code_ids = pseudocode_to_code_ids(pseudocode)
            return {'pseudocode': pseudocode, 'code_ids': code_ids}
        except Exception as e:
            return {'pseudocode': f'Erreur de génération : {e}', 'code_ids': [17]}

    # ── Fallback sans moteur IA ──
    idx = None
    for i, r in enumerate(problem['rules']['rules']):
        if eval_condition(problem['init'], r['condition']):
            idx = i
            break
    if idx is None:
        return {'pseudocode': 'Algorithme algo_principal()\n1: // aucune règle applicable', 'code_ids': [17]}
    code = ['Algorithme algo_principal()']
    line = 1
    rule = problem['rules']['rules'][idx]
    cond_var = rule['condition'][0]
    code.append(f"{line}: si (non est_vide({color_name(cond_var).lower()})) alors"); line += 1
    for v in VARS:
        delta = parse_update_delta(rule['updates'].get(v, v), v)
        if delta < 0:
            for _ in range(abs(delta)):
                code.append(f"{line}:     retirer(→{color_name(v).lower()})"); line += 1
        elif delta > 0:
            for _ in range(delta):
                code.append(f"{line}:     poser(→{color_name(v).lower()})"); line += 1
    code.append(f"{line}: finsi")
    pseudocode = '\n'.join(code)
    return {'pseudocode': pseudocode, 'code_ids': pseudocode_to_code_ids(pseudocode)}


def blocks_to_code(blocks):
    lines = ['Algorithme algo_principal()']
    line_no = 1
    for block in blocks:
        indent = '    ' * max(0, int(block.get('indent', 0)))
        kind = block.get('type')
        color = block.get('color') or 'b'
        label = color_name(color).lower() if color else ''
        if kind in ('if_not_empty', 'if_not_empty_else'):
            lines.append(f"{line_no}: {indent}si non est_vide({label}) alors")
        elif kind in ('if_empty', 'if_empty_else'):
            lines.append(f"{line_no}: {indent}si est_vide({label}) alors")
        elif kind == 'retirer':
            lines.append(f"{line_no}: {indent}retirer(→{label})")
        elif kind == 'poser':
            lines.append(f"{line_no}: {indent}poser(→{label})")
        elif kind == 'sinon':
            lines.append(f"{line_no}: {indent}sinon")
        elif kind == 'finsi':
            lines.append(f"{line_no}: {indent}finsi")
        line_no += 1
    return '\n'.join(lines)

# ---------------- Teacher ----------------
@app.route('/teacher/dashboard')
@login_required('teacher')
def teacher_dashboard():
    db = get_db()
    exercises = db.execute('SELECT * FROM exercises ORDER BY created_at DESC').fetchall()
    return render_template('teacher_dashboard.html', exercises=exercises)

@app.route('/teacher/exercise/new')
@login_required('teacher')
def teacher_new_exercise():
    return render_template('teacher_exercise_form.html')

@app.post('/api/teacher/exercise/preview')
@login_required('teacher')
def teacher_preview_json():
    data = request.get_json(force=True)
    problem = data['problem']
    preview = generate_teacher_preview(problem)
    return jsonify({'problem_json': problem, 'preview': preview})

@app.post('/api/teacher/exercise/save')
@login_required('teacher')
def teacher_save_exercise():
    data = request.get_json(force=True)
    payload = data['problem']
    title = data.get('title','Exercice')
    description = data.get('description','')
    publish = bool(data.get('publish', False))
    db = get_db()

    # Génération du pseudo-code et des code_ids de référence,
    # stockés dans problem_json pour le système de recommandation
    preview = generate_teacher_preview(payload)
    payload['pseudocode_reference'] = preview['pseudocode']
    payload['code_ids_correct']     = preview['code_ids']

    cur = db.execute('''
        INSERT INTO exercises(title,description,init_b,init_j,init_r,init_v,goal_condition,max_steps,problem_json,is_published,session_code,created_by)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        title, description,
        payload['init']['b'], payload['init']['j'], payload['init']['r'], payload['init']['v'],
        payload['goal_condition'], payload['max_steps'], json.dumps(payload, ensure_ascii=False),
        1 if publish else 0,
        secrets.token_hex(3).upper() if publish else None,
        session['user_id']
    ))
    exercise_id = cur.lastrowid
    for pos, r in enumerate(payload['rules']['rules']):
        cond = r['condition']
        cond_color = cond[0]
        m = None
        for op in ['>=','<=','==','>','<']:
            if op in cond:
                _, n = cond.split(op)
                m = (op, int(n))
                break
        if m is None:
            m = ('>=', 1)
        deltas = {c: parse_update_delta(r['updates'].get(c, c), c) for c in VARS}
        db.execute('''
            INSERT INTO exercise_rules(exercise_id,name,cond_color,cond_operator,cond_value,delta_b,delta_j,delta_r,delta_v,position)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        ''', (exercise_id, r['name'], cond_color, m[0], m[1], deltas['b'], deltas['j'], deltas['r'], deltas['v'], pos))
    db.commit()
    ex = db.execute('SELECT * FROM exercises WHERE id=?', (exercise_id,)).fetchone()
    return jsonify({'ok': True, 'exercise_id': exercise_id, 'session_code': ex['session_code']})

@app.route('/teacher/session/<int:exercise_id>')
@login_required('teacher')
def teacher_session(exercise_id):
    ex, _ = get_exercise(exercise_id)
    if not ex:
        return redirect(url_for('teacher_dashboard'))
    db = get_db()
    rows = db.execute('''
        SELECT s.*, u.username FROM submissions s JOIN users u ON u.id=s.student_id WHERE exercise_id=? ORDER BY created_at DESC
    ''', (exercise_id,)).fetchall()
    submissions = []
    for row in rows:
        s = dict(row)
        try:
            s['feedback'] = json.loads(s['feedback_json']) if s['feedback_json'] else {}
        except Exception:
            s['feedback'] = {}
        submissions.append(s)
    problem = json.loads(ex['problem_json'])
    pseudocode = problem.get('pseudocode_reference', '')
    return render_template('teacher_session.html',exercise=ex,submissions=submissions,pseudocode=pseudocode)

@app.route('/api/teacher/exercise/<int:exercise_id>', methods=['DELETE'])
@login_required('teacher')
def teacher_delete_exercise(exercise_id):
    db = get_db()
    ex = db.execute('SELECT id FROM exercises WHERE id=?', (exercise_id,)).fetchone()
    if not ex:
        return jsonify({'ok': False, 'error': 'Exercice introuvable'}), 404
    db.execute('DELETE FROM submissions WHERE exercise_id=?', (exercise_id,))
    db.execute('DELETE FROM exercise_rules WHERE exercise_id=?', (exercise_id,))
    db.execute('DELETE FROM exercises WHERE id=?', (exercise_id,))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/teacher/submission/<int:submission_id>', methods=['DELETE'])
@login_required('teacher')
def teacher_delete_submission(submission_id):
    db = get_db()
    row = db.execute('SELECT id FROM submissions WHERE id=?', (submission_id,)).fetchone()
    if not row:
        return jsonify({'ok': False, 'error': 'Soumission introuvable'}), 404
    db.execute('DELETE FROM submissions WHERE id=?', (submission_id,))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/teacher/submissions/exercise/<int:exercise_id>', methods=['DELETE'])
@login_required('teacher')
def teacher_delete_all_submissions(exercise_id):
    db = get_db()
    
    try:
        db.execute('DELETE FROM submissions WHERE exercise_id=?', (exercise_id,))
        db.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# ---------------- Student ----------------
@app.route('/student/dashboard')
@login_required('student')
def student_dashboard():
    db = get_db()
    exercises = db.execute('SELECT * FROM exercises WHERE is_published=1 ORDER BY created_at DESC').fetchall()
    # Exercices validés par cet étudiant (au moins une soumission correcte)
    rows = db.execute(
        'SELECT DISTINCT exercise_id FROM submissions WHERE student_id=? AND is_correct=1',
        (session['user_id'],)
    ).fetchall()
    validated_ids = {r['exercise_id'] for r in rows}
    return render_template('student_dashboard.html', exercises=exercises, validated_ids=validated_ids)

@app.route('/student/exercise/<int:exercise_id>')
@login_required('student')
def student_exercise(exercise_id):
    ex, _ = get_exercise(exercise_id)
    if not ex or not ex['is_published']:
        return redirect(url_for('student_dashboard'))
    problem = json.loads(ex['problem_json'])
    return render_template('student_exercise.html', exercise=ex, problem=problem)

@app.post('/api/student/help/<int:exercise_id>')
@login_required('student')
def student_help(exercise_id):
    ex, _ = get_exercise(exercise_id)
    if not ex:
        return jsonify({'ok': False, 'message': 'Exercice introuvable'}), 404

    blocks = (request.get_json(force=True) or {}).get('blocks', [])
    code_ids_etudiant = blocks_to_code_ids(blocks)

    # Récupération du code correct stocké dans problem_json
    problem = json.loads(ex['problem_json'])
    code_ids_correct = problem.get('code_ids_correct')
    if not code_ids_correct:
        # Fallback : ancienne aide basique si aucun code de référence n'est enregistré
        return jsonify({'ok': True, **generate_teacher_preview(problem)})

    try:
        systeme = SystemeRecommandation()
        oracle  = systeme.construire_oracle(code_ids_correct, nb_etats=50, max_valeur=5)

        # Contre-exemple (code complet avec STOP)
        contre_exemple_msg = systeme.generateur.tester_code(
            code_ids_etudiant, oracle, formater_message=True
        )

        # Recommandation (code partiel sans STOP ni FIN_SI de fermeture)
        code_partiel = tronquer_code_partiel(code_ids_etudiant)
        resultat  = systeme.recommander(code_partiel, oracle, verbose=False)
        message   = recommandation_to_message(resultat)
        pseudocode = None if resultat.get('code_correct') else code_ids_to_pseudocode(code_ids_correct)

        return jsonify({
            'ok':             True,
            'contre_exemple': contre_exemple_msg,
            'message':        message,
            'pseudocode':     pseudocode,
        })
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)}), 500

@app.post('/api/student/submit/<int:exercise_id>')
@login_required('student')
def student_submit(exercise_id):
    try:
        data   = request.get_json(force=True)
        blocks = data.get('blocks', [])
        generated_code    = blocks_to_code(blocks)
        code_ids_etudiant = blocks_to_code_ids(blocks)

        ex, _ = get_exercise(exercise_id)
        if not ex:
            return jsonify({'ok': False, 'message': 'Exercice introuvable'}), 404

        problem = json.loads(ex['problem_json'])
        code_ids_correct = problem.get('code_ids_correct')

        contre_exemple_msg = None
        expected_pseudocode = None

        if code_ids_correct:
            systeme = SystemeRecommandation()
            oracle  = systeme.construire_oracle(code_ids_correct, nb_etats=50, max_valeur=5)
            contre_exemple_msg = systeme.generateur.tester_code(
                code_ids_etudiant, oracle, formater_message=True
            )
            code_partiel = tronquer_code_partiel(code_ids_etudiant)
            resultat = systeme.recommander(code_partiel, oracle, verbose=False)
            if not resultat.get('code_correct'):
                expected_pseudocode = code_ids_to_pseudocode(code_ids_correct)
        else:
            # Fallback si pas de code de référence
            help_preview = generate_teacher_preview(problem)
            expected_pseudocode = help_preview['pseudocode']

        feedback = {
            'student_code':        generated_code,
            'contre_exemple':      contre_exemple_msg,
            'expected_pseudocode': expected_pseudocode,
        }
        is_correct = 1 if contre_exemple_msg is None else 0

        db = get_db()
        db.execute(
            'INSERT INTO submissions(exercise_id,student_id,blocks_json,generated_code,feedback_json,is_correct) VALUES(?,?,?,?,?,?)',
            (exercise_id, session['user_id'], json.dumps(blocks, ensure_ascii=False),
             generated_code, json.dumps(feedback, ensure_ascii=False), is_correct)
        )
        db.commit()
        return jsonify({'ok': True, 'feedback': feedback, 'is_correct': bool(is_correct)})

    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)}), 500

# Jinja helper
app.jinja_env.globals.update(color_name=color_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)