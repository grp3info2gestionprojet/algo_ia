const COLOR_OPTIONS = [
  { value: 'b', label: 'Bleue', className: 'blue' },
  { value: 'j', label: 'Jaune', className: 'yellow' },
  { value: 'r', label: 'Rouge', className: 'red' },
  { value: 'v', label: 'Verte', className: 'green' },
];
const OPERATORS = ['>=','<=','==','>','<'];
let rules = [];

function colorLabel(code){
  return COLOR_OPTIONS.find(c => c.value === code)?.label || code;
}
function signedText(n){ return n > 0 ? `+${n}` : `${n}`; }

function createRule(){
  return {
    name: 'retirer bleue si possible',
    condColor: 'b',
    operator: '>=',
    value: 1,
    deltas: { b: -1, j: 0, r: 0, v: 0 }
  };
}

function adjustDelta(index, color, change){
  rules[index].deltas[color] += change;
  renderRules();
}

function removeRule(index){
  rules.splice(index, 1);
  renderRules();
}

function renderRules(){
  const container = document.getElementById('rulesContainer');
  container.innerHTML = '';
  rules.forEach((rule, index) => {
    const wrap = document.createElement('div');
    wrap.className = 'rule-card';
    wrap.innerHTML = `
      <div class="rule-label">Règle ${index + 1}</div>
      <div style="margin-left:80px">
        <div class="cond-grid">
          <div class="big-word">Si</div>
          <div class="cond-panel">
            <div class="cond-fields">
              <div>
                <div class="color-name">Couleur</div>
                <select data-index="${index}" data-field="condColor">
                  ${COLOR_OPTIONS.map(c => `<option value="${c.value}" ${rule.condColor===c.value?'selected':''}>${c.label}</option>`).join('')}
                </select>
              </div>
              <div>
                <div class="color-name">Comparateur</div>
                <select data-index="${index}" data-field="operator">
                  ${OPERATORS.map(op => `<option value="${op}" ${rule.operator===op?'selected':''}>${op}</option>`).join('')}
                </select>
              </div>
              <div>
                <div class="color-name">Nombre</div>
                <input type="number" min="0" data-index="${index}" data-field="value" value="${rule.value}">
              </div>
            </div>
            <div style="margin-top:14px">
              <label>Nom de règle</label>
              <input type="text" data-index="${index}" data-field="name" value="${rule.name}">
            </div>
          </div>
        </div>
        <div class="then-grid">
          <div class="big-word">Alors</div>
          <div class="then-panel">
            <div class="rule-columns">
              ${COLOR_OPTIONS.map(c => `
                <div class="color-col">
                  <div class="color-name">${c.label}</div>
                  <div class="delta-box">${rule.deltas[c.value]===0 ? c.value : c.value + signedText(rule.deltas[c.value])}</div>
                  <div class="delta-buttons">
                    <button type="button" class="circle-btn ${c.className}" data-op="plus" data-index="${index}" data-color="${c.value}">+</button>
                    <button type="button" class="circle-btn ${c.className}" data-op="minus" data-index="${index}" data-color="${c.value}">-</button>
                  </div>
                </div>`).join('')}
            </div>
            <div class="rule-actions">
              <span class="muted">Cette règle sera convertie automatiquement en JSON.</span>
              <button type="button" class="secondary-btn danger" data-remove="${index}">Supprimer règle</button>
            </div>
          </div>
        </div>
      </div>`;
    container.appendChild(wrap);
  });

  container.querySelectorAll('select,input[data-field]').forEach(el => {
    el.addEventListener('change', e => {
      const idx = Number(e.target.dataset.index);
      const field = e.target.dataset.field;
      rules[idx][field] = field === 'value' ? Number(e.target.value) : e.target.value;
    });
  });
  container.querySelectorAll('[data-op]').forEach(btn => {
    btn.addEventListener('click', e => {
      const idx = Number(e.target.dataset.index);
      const color = e.target.dataset.color;
      const op = e.target.dataset.op;
      adjustDelta(idx, color, op === 'plus' ? 1 : -1);
    });
  });
  container.querySelectorAll('[data-remove]').forEach(btn => {
    btn.addEventListener('click', e => removeRule(Number(e.target.dataset.remove)));
  });
}

function buildProblem(){
  return {
    init: {
      b: Number(document.getElementById('init_b').value || 0),
      j: Number(document.getElementById('init_j').value || 0),
      r: Number(document.getElementById('init_r').value || 0),
      v: Number(document.getElementById('init_v').value || 0),
    },
    max_steps: Number(document.getElementById('max_steps').value || 30),
    goal_condition: document.getElementById('goal_condition').value || 'b==0',
    rules: {
      vars: ['b','j','r','v'],
      rules: rules.map(rule => ({
        name: rule.name,
        condition: `${rule.condColor}${rule.operator}${rule.value}`,
        updates: {
          b: rule.deltas.b === 0 ? 'b' : `b${rule.deltas.b>0?'+':''}${rule.deltas.b}`,
          j: rule.deltas.j === 0 ? 'j' : `j${rule.deltas.j>0?'+':''}${rule.deltas.j}`,
          r: rule.deltas.r === 0 ? 'r' : `r${rule.deltas.r>0?'+':''}${rule.deltas.r}`,
          v: rule.deltas.v === 0 ? 'v' : `v${rule.deltas.v>0?'+':''}${rule.deltas.v}`,
        }
      }))
    }
  };
}

async function preview(publish=false){
  const payload = {
    title: document.getElementById('title').value || 'Exercice',
    description: document.getElementById('description').value || '',
    problem: buildProblem(),
    publish
  };
  const endpoint = publish ? '/api/teacher/exercise/save' : '/api/teacher/exercise/preview';
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  return data;
}

document.addEventListener('DOMContentLoaded', () => {
  rules.push(createRule());
  renderRules();

  document.getElementById('addRuleBtn').addEventListener('click', () => {
    rules.push(createRule());
    renderRules();
  });

  document.getElementById('clearBtn').addEventListener('click', () => {
    document.getElementById('title').value = '';
    document.getElementById('description').value = '';
    document.getElementById('previewText').textContent = '(vide)';
    rules = [createRule()];
    renderRules();
  });

  document.getElementById('previewBtn').addEventListener('click', async () => {
    const data = await preview(false);
    document.getElementById('previewText').textContent = JSON.stringify(data.problem_json, null, 2) + '\n\n' + data.preview.message + '\n\n' + data.preview.pseudocode;
  });

  document.getElementById('publishBtn').addEventListener('click', async () => {
    const data = await preview(true);
    if (data.ok) {
      alert(`Exercice publié. Code session: ${data.session_code || 'N/A'}`);
      window.location.href = `/teacher/session/${data.exercise_id}`;
    }
  });
});
