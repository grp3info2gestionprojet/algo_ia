from __future__ import annotations
import json, sqlite3, secrets
from functools import wraps
from pathlib import Path
from flask import Flask, g, render_template, request, redirect, url_for, session, jsonify, flash

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


def generate_teacher_preview(problem):
    # placeholder help: first applicable rule
    idx = None
    for i, r in enumerate(problem['rules']['rules']):
        if eval_condition(problem['init'], r['condition']):
            idx = i
            break
    if idx is None:
        return {'message': 'Aucune règle applicable.', 'pseudocode': 'Algorithme algo_principal()\n1: // rien'}
    sim = simulate_rule(problem, idx)
    code = ['Algorithme algo_principal()']
    line = 1
    rule = problem['rules']['rules'][idx]
    cond_var = rule['condition'][0]
    code.append(f"{line}: si (non est_vide({color_name(cond_var).lower()})) alors"); line += 1
    for v in VARS:
        delta = parse_update_delta(rule['updates'].get(v,v), v)
        if delta < 0:
            for _ in range(abs(delta)):
                code.append(f"{line}:     retirer(→{color_name(v).lower()})"); line += 1
        elif delta > 0:
            for _ in range(delta):
                code.append(f"{line}:     poser(→{color_name(v).lower()})"); line += 1
    code.append(f"{line}: finsi")
    return {'message': f"Règle recommandée: {rule['name']}", 'pseudocode': '\n'.join(code), 'simulation': sim}


def blocks_to_code(blocks):
    lines = ['Algorithme algo_principal()']
    line_no = 1
    for block in blocks:
        indent = '    ' * max(0, int(block.get('indent', 0)))
        kind = block.get('type')
        color = block.get('color', 'b')
        label = color_name(color).lower()
        if kind == 'if_not_empty':
            lines.append(f"{line_no}: {indent}si non est_vide({label}) alors")
        elif kind == 'if_empty':
            lines.append(f"{line_no}: {indent}si est_vide({label}) alors")
        elif kind == 'retirer':
            lines.append(f"{line_no}: {indent}retirer(→{label})")
        elif kind == 'poser':
            lines.append(f"{line_no}: {indent}poser(→{label})")
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
    submissions = db.execute('''
        SELECT s.*, u.username FROM submissions s JOIN users u ON u.id=s.student_id WHERE exercise_id=? ORDER BY created_at DESC
    ''', (exercise_id,)).fetchall()
    return render_template('teacher_session.html', exercise=ex, submissions=submissions)

# ---------------- Student ----------------
@app.route('/student/dashboard')
@login_required('student')
def student_dashboard():
    db = get_db()
    exercises = db.execute('SELECT * FROM exercises WHERE is_published=1 ORDER BY created_at DESC').fetchall()
    return render_template('student_dashboard.html', exercises=exercises)

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
    problem = json.loads(ex['problem_json'])
    return jsonify({'ok': True, **generate_teacher_preview(problem)})

@app.post('/api/student/submit/<int:exercise_id>')
@login_required('student')
def student_submit(exercise_id):
    data = request.get_json(force=True)
    blocks = data.get('blocks', [])
    generated_code = blocks_to_code(blocks)
    ex, _ = get_exercise(exercise_id)
    if not ex:
        return jsonify({'ok': False}), 404
    problem = json.loads(ex['problem_json'])
    help_preview = generate_teacher_preview(problem)
    feedback = {
        'message': 'Soumission enregistrée. Comparaison basique disponible.',
        'expected_hint': help_preview['message'],
        'expected_pseudocode': help_preview['pseudocode'],
        'student_code': generated_code
    }
    db = get_db()
    db.execute('INSERT INTO submissions(exercise_id,student_id,blocks_json,generated_code,feedback_json) VALUES(?,?,?,?,?)', (
        exercise_id, session['user_id'], json.dumps(blocks, ensure_ascii=False), generated_code, json.dumps(feedback, ensure_ascii=False)
    ))
    db.commit()
    return jsonify({'ok': True, 'feedback': feedback})

# Jinja helper
app.jinja_env.globals.update(color_name=color_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
