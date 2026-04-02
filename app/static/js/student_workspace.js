const palette = document.getElementById('palette');
const workspace = document.getElementById('workspace');
const feedbackText = document.getElementById('feedbackText');
let rootBlocks = [];

function colorSelect(selected = 'b') {
  return `<select class="color-select" style="margin: 0 5px; padding: 2px; border-radius: 4px; border: 1px solid #ccc; color: black; background: white;" onclick="event.stopPropagation()">
    <option value="b" ${selected === 'b' ? 'selected' : ''}>Bleue</option>
    <option value="j" ${selected === 'j' ? 'selected' : ''}>Jaune</option>
    <option value="r" ${selected === 'r' ? 'selected' : ''}>Rouge</option>
    <option value="v" ${selected === 'v' ? 'selected' : ''}>Verte</option>
  </select>`;
}

function typeLabel(type) {
  if (type === 'if_not_empty' || type === 'if_not_empty_else') return 'si non est_vide';
  if (type === 'if_empty' || type === 'if_empty_else') return 'si est_vide';
  if (type === 'retirer') return 'retirer';
  if (type === 'poser') return 'poser';
  return '';
}

function renderTree(blockList, container) {
  container.innerHTML = '';
  blockList.forEach((block, index) => {
    const blockDiv = document.createElement('div');
    blockDiv.style.marginBottom = '10px';
    blockDiv.style.fontFamily = 'monospace';
    blockDiv.style.fontSize = '16px';

    if (block.type.startsWith('if_')) {
      const isElse = block.type.endsWith('_else');
      let html = `
        <div class="block-header" style="background: linear-gradient(180deg, var(--green), var(--green-dark)); padding: 10px 14px; border-radius: 12px 12px 0 0; color: white; display: flex; align-items: center; justify-content: space-between; font-weight: bold; box-shadow: inset 0 2px 0 rgba(255,255,255,0.2);">
          <div>${typeLabel(block.type)}(${colorSelect(block.color)}) alors</div>
          <button class="tiny-btn btn-del" data-idx="${index}" style="margin-left: 10px; color: black;">✕</button>
        </div>
        <div class="block-children" style="border-left: 16px solid var(--green-dark); padding: 10px 10px 10px 20px; min-height: 40px; background: rgba(0,0,0,0.02);"></div>
      `;

      if (isElse) {
        html += `
        <div class="block-header block-else-header" style="background: linear-gradient(180deg, var(--green), var(--green-dark)); padding: 8px 14px; color: white; display: flex; align-items: center; font-weight: bold; border-top: 1px solid rgba(255,255,255,0.3);">
          <div>sinon</div>
        </div>
        <div class="block-children-else" style="border-left: 16px solid var(--green-dark); padding: 10px 10px 10px 20px; min-height: 40px; background: rgba(0,0,0,0.02);"></div>
        `;
      }

      html += `
        <div class="block-footer" style="background: linear-gradient(180deg, var(--green), var(--green-dark)); padding: 8px 14px; border-radius: 0 0 12px 12px; color: white; font-weight: bold;">
          finsi
        </div>
      `;
      blockDiv.innerHTML = html;

      const childrenContainer = blockDiv.querySelector('.block-children');

      childrenContainer.addEventListener('dragover', e => {
        e.preventDefault();
        e.stopPropagation();
        childrenContainer.style.backgroundColor = 'rgba(0,0,0,0.08)';
      });
      childrenContainer.addEventListener('dragleave', e => {
        childrenContainer.style.backgroundColor = 'rgba(0,0,0,0.02)';
      });
      childrenContainer.addEventListener('drop', e => {
        e.preventDefault();
        e.stopPropagation();
        childrenContainer.style.backgroundColor = 'rgba(0,0,0,0.02)';
        const type = e.dataTransfer.getData('text/plain');
        if (type) {
          block.children = block.children || [];
          block.children.push({ type, color: 'b', children: [] });
          renderBlocks();
        }
      });

      if (block.children) {
        renderTree(block.children, childrenContainer);
      }

      if (isElse) {
        const childrenElseContainer = blockDiv.querySelector('.block-children-else');
        childrenElseContainer.addEventListener('dragover', e => {
          e.preventDefault();
          e.stopPropagation();
          childrenElseContainer.style.backgroundColor = 'rgba(0,0,0,0.08)';
        });
        childrenElseContainer.addEventListener('dragleave', e => {
          childrenElseContainer.style.backgroundColor = 'rgba(0,0,0,0.02)';
        });
        childrenElseContainer.addEventListener('drop', e => {
          e.preventDefault();
          e.stopPropagation();
          childrenElseContainer.style.backgroundColor = 'rgba(0,0,0,0.02)';
          const type = e.dataTransfer.getData('text/plain');
          if (type) {
            block.childrenElse = block.childrenElse || [];
            block.childrenElse.push({ type, color: 'b', children: [] });
            renderBlocks();
          }
        });

        if (block.childrenElse) {
          renderTree(block.childrenElse, childrenElseContainer);
        }
      }

    } else {
      blockDiv.innerHTML = `
        <div style="background: linear-gradient(180deg, var(--green), var(--green-dark)); padding: 10px 14px; border-radius: 12px; color: white; display: flex; align-items: center; justify-content: space-between; font-weight: bold; box-shadow: inset 0 2px 0 rgba(255,255,255,0.2);">
          <div>${typeLabel(block.type)}(→${colorSelect(block.color)})</div>
          <button class="tiny-btn btn-del" data-idx="${index}" style="margin-left: 10px; color: black;">✕</button>
        </div>
      `;
    }

    const select = blockDiv.querySelector('.color-select');
    if (select) {
      select.addEventListener('change', e => {
        block.color = e.target.value;
      });
    }

    const delBtn = blockDiv.querySelector('.btn-del');
    if (delBtn) {
      delBtn.addEventListener('click', e => {
        e.stopPropagation();
        blockList.splice(index, 1);
        renderBlocks();
      });
    }

    container.appendChild(blockDiv);
  });
}

function renderBlocks() {
  renderTree(rootBlocks, workspace);
}

function extractFlatBlocks(blockList, indent = 0) {
  let flat = [];
  blockList.forEach(b => {
    if (b.type.startsWith('if_')) {
      flat.push({ type: b.type, color: b.color, indent: indent });
      if (b.children) {
        flat = flat.concat(extractFlatBlocks(b.children, indent + 1));
      }
      if (b.type.endsWith('_else')) {
        flat.push({ type: 'sinon', color: null, indent: indent });
        if (b.childrenElse) {
          flat = flat.concat(extractFlatBlocks(b.childrenElse, indent + 1));
        }
      }
      flat.push({ type: 'finsi', color: null, indent: indent });
    } else {
      flat.push({ type: b.type, color: b.color, indent: indent });
    }
  });
  return flat;
}

// ─── Draggable toolbox ────────────────────────────────────────────────────────

palette.querySelectorAll('[draggable="true"]').forEach(el => {
  el.addEventListener('dragstart', e => {
    e.dataTransfer.setData('text/plain', el.dataset.type);
  });
});

workspace.addEventListener('dragover', e => {
  e.preventDefault();
  workspace.style.backgroundColor = '#eaeaea';
});
workspace.addEventListener('dragleave', e => {
  workspace.style.backgroundColor = '#f8f8f8';
});
workspace.addEventListener('drop', e => {
  e.preventDefault();
  workspace.style.backgroundColor = '#f8f8f8';
  const type = e.dataTransfer.getData('text/plain');
  if (type) {
    rootBlocks.push({ type, color: 'b', children: [] });
    renderBlocks();
  }
});

// ─── Helpers affichage ────────────────────────────────────────────────────────

function codeBlock(content) {
  return `<div style="background:#282a36;color:#f8f8f2;padding:10px;border-radius:8px;margin-top:5px;font-family:monospace;white-space:pre-wrap;text-align:left;">${content}</div>`;
}

function setLoading(msg) {
  feedbackText.innerHTML = `<i style="color:#888;">${msg}</i>`;
}

function buildStudentPseudocode(blocks) {
  let lines = [];
  let lineNo = 1;
  blocks.forEach(b => {
    const indentStr = '    '.repeat(b.indent);
    const colorName = { b: 'bleue', j: 'jaune', r: 'rouge', v: 'verte' }[b.color] || '';
    let text = '';
    if (b.type === 'if_not_empty' || b.type === 'if_not_empty_else') text = `si non est_vide(${colorName}) alors`;
    else if (b.type === 'if_empty' || b.type === 'if_empty_else')  text = `si est_vide(${colorName}) alors`;
    else if (b.type === 'sinon')     text = `sinon`;
    else if (b.type === 'poser')     text = `poser(→${colorName})`;
    else if (b.type === 'retirer')   text = `retirer(→${colorName})`;
    else if (b.type === 'finsi')     text = `finsi`;
    if (text) { lines.push(`${lineNo}: ${indentStr}${text}`); lineNo++; }
  });
  return lines.join('\n') || '(algorithme vide)';
}

// ─── Demander de l'aide ───────────────────────────────────────────────────────

document.getElementById('helpBtn').addEventListener('click', async () => {
  const blocks = extractFlatBlocks(rootBlocks);
  setLoading('Génération de la recommandation…');

  let data;
  try {
    const res = await fetch(`/api/student/help/${window.STUDENT_EXERCISE.exerciseId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blocks })
    });
    const text = await res.text();
    try {
      data = JSON.parse(text);
    } catch (_) {
      feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur serveur inattendue (réponse non-JSON).<br><pre style="font-size:11px;color:#aaa;">${text.slice(0, 500)}</pre></span>`;
      return;
    }
  } catch (err) {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur réseau : ${err.message}</span>`;
    return;
  }

  const studentCode = buildStudentPseudocode(blocks);

  if (data.ok) {
    let html = `<b>Votre code actuel :</b>${codeBlock(studentCode)}<br>`;

    if (data.contre_exemple) {
      html += `<b>🔍 Contre-exemple :</b><br>
<span style="color:#ff5555;font-family:monospace;">${data.contre_exemple}</span><br><br>`;
    }

    if (data.message) {
      html += `<b>💡 Recommandation :</b><br>${data.message}`;
    }

    feedbackText.innerHTML = html;
  } else {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur : ${data.message || JSON.stringify(data)}</span>`;
  }
});

// ─── Envoyer la solution ──────────────────────────────────────────────────────

async function submitSolution() {
  const blocks = extractFlatBlocks(rootBlocks);
  setLoading('Vérification de votre solution…');

  let data;
  try {
    const res = await fetch(`/api/student/submit/${window.STUDENT_EXERCISE.exerciseId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blocks })
    });
    const text = await res.text();
    try {
      data = JSON.parse(text);
    } catch (_) {
      feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur serveur inattendue (réponse non-JSON).<br><pre style="font-size:11px;color:#aaa;">${text.slice(0, 500)}</pre></span>`;
      return;
    }
  } catch (err) {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur réseau : ${err.message}</span>`;
    return;
  }

  if (data.ok) {
    if (data.is_correct) {
      // Code correct : félicitations + bouton retour au dashboard
      feedbackText.innerHTML = `
        <div style="text-align:center; padding: 20px;">
          <div style="font-size: 48px; margin-bottom: 10px;">🎉</div>
          <b style="font-size: 20px; color: #50fa7b;">Bravo, votre algorithme est correct !</b>
          <br><br>
          <p style="color: #ccc;">L'exercice a été validé et envoyé à votre professeur.</p>
          <br>
          <a href="/student/dashboard"
             style="display:inline-block; padding: 10px 24px; background: var(--green);
                    color: white; border-radius: 8px; text-decoration: none;
                    font-weight: bold; font-size: 15px;">
            ← Retour aux exercices
          </a>
        </div>`;
      document.getElementById('submitBtn').disabled = true;
      document.getElementById('helpBtn').disabled = true;
    } else {
      // Code incorrect : afficher le contre-exemple
      const fb = data.feedback;
      let html = `<b>❌ Code incorrect</b><br><br>`;
      if (fb.contre_exemple) {
        html += `<b>🔍 Contre-exemple :</b><br>
<span style="color:#ff5555;font-family:monospace;">${fb.contre_exemple}</span>`;
      }
      feedbackText.innerHTML = html;
    }
  } else {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur : ${data.message || JSON.stringify(data)}</span>`;
  }
}

document.getElementById('submitBtn').addEventListener('click', submitSolution);

renderBlocks();