const palette = document.getElementById('palette');
const workspace = document.getElementById('workspace');
const feedbackText = document.getElementById('feedbackText');
let rootBlocks = [];
let draggedBlock = null; // bloc workspace en cours de déplacement

// ── Helpers affichage ─────────────────────────────────────────────────────────
function colorSelect(selected = 'b') {
  return `<select class="color-select" style="margin:0 4px;padding:2px 4px;border-radius:4px;border:1px solid #ccc;color:black;background:white;" onclick="event.stopPropagation()">
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

// ── Navigation dans l'arbre ───────────────────────────────────────────────────
function findBlock(target, list, parentCtx = null) {
  for (let i = 0; i < list.length; i++) {
    if (list[i] === target) return { list, index: i, parentCtx };
    const b = list[i];
    if (b.children) {
      const r = findBlock(target, b.children, { block: b, role: 'children' });
      if (r) return r;
    }
    if (b.childrenElse) {
      const r = findBlock(target, b.childrenElse, { block: b, role: 'childrenElse' });
      if (r) return r;
    }
  }
  return null;
}

// ── Déplacer ─────────────────────────────────────────────────────────────────
function moveUp(block) {
  const loc = findBlock(block, rootBlocks);
  if (!loc) return;
  const { list, index, parentCtx } = loc;
  if (index > 0) {
    const prev = list[index - 1];
    list.splice(index, 1);
    if (prev.type && prev.type.startsWith('if_')) {
      if (prev.type.endsWith('_else')) { prev.childrenElse = prev.childrenElse || []; prev.childrenElse.push(block); }
      else { prev.children = prev.children || []; prev.children.push(block); }
    } else { list.splice(index - 1, 0, block); }
  } else if (parentCtx) {
    const { block: parentBlock, role } = parentCtx;
    if (role === 'childrenElse') {
      list.splice(index, 1);
      parentBlock.children = parentBlock.children || [];
      parentBlock.children.push(block);
    } else {
      const parentLoc = findBlock(parentBlock, rootBlocks);
      if (parentLoc) { list.splice(index, 1); parentLoc.list.splice(parentLoc.index, 0, block); }
    }
  }
  renderBlocks();
}

function moveDown(block) {
  const loc = findBlock(block, rootBlocks);
  if (!loc) return;
  const { list, index, parentCtx } = loc;
  if (index < list.length - 1) {
    const next = list[index + 1];
    list.splice(index, 1);
    if (next.type && next.type.startsWith('if_')) {
      next.children = next.children || [];
      next.children.unshift(block);
    } else { list.splice(index + 1, 0, block); }
  } else if (parentCtx) {
    const { block: parentBlock, role } = parentCtx;
    if (role === 'children' && parentBlock.type.endsWith('_else')) {
      list.splice(index, 1);
      parentBlock.childrenElse = parentBlock.childrenElse || [];
      parentBlock.childrenElse.unshift(block);
    } else {
      const parentLoc = findBlock(parentBlock, rootBlocks);
      if (parentLoc) { list.splice(index, 1); parentLoc.list.splice(parentLoc.index + 1, 0, block); }
    }
  }
  renderBlocks();
}

function deleteBlock(block) {
  const loc = findBlock(block, rootBlocks);
  if (!loc) return;
  loc.list.splice(loc.index, 1);
  renderBlocks();
}

// ── Drop slot (zone de dépôt entre blocs) ─────────────────────────────────────
// insertBeforeBlock = null → insérer à la fin de targetList
function makeDropSlot(targetList, insertBeforeBlock) {
  const slot = document.createElement('div');
  slot.style.cssText = 'height:6px;border-radius:4px;margin:2px 0;transition:all .15s;';

  const activate = () => {
    slot.style.cssText = 'height:18px;border-radius:4px;margin:2px 0;background:rgba(70,173,60,.25);border:2px dashed #46ad3c;transition:all .15s;';
  };
  const deactivate = () => {
    slot.style.cssText = 'height:6px;border-radius:4px;margin:2px 0;transition:all .15s;';
  };

  slot.addEventListener('dragover', e => {
    e.preventDefault();
    e.stopPropagation();
    activate();
  });
  slot.addEventListener('dragleave', deactivate);

  slot.addEventListener('drop', e => {
    e.preventDefault();
    e.stopPropagation();
    deactivate();

    const type = e.dataTransfer.getData('text/plain');

    if (type === '__workspace_move__' && draggedBlock) {
      // Déplacement d'un bloc existant
      const movingBlock = draggedBlock;
      draggedBlock = null;

      // Retirer de sa position actuelle
      const loc = findBlock(movingBlock, rootBlocks);
      if (loc) loc.list.splice(loc.index, 1);

      // Insérer à la nouvelle position
      if (insertBeforeBlock === null) {
        targetList.push(movingBlock);
      } else {
        const idx = targetList.indexOf(insertBeforeBlock);
        targetList.splice(idx >= 0 ? idx : targetList.length, 0, movingBlock);
      }
      renderBlocks();

    } else if (type && type !== '__workspace_move__') {
      // Nouveau bloc depuis la palette
      const newBlock = { type, color: 'b', children: [] };
      if (insertBeforeBlock === null) {
        targetList.push(newBlock);
      } else {
        const idx = targetList.indexOf(insertBeforeBlock);
        targetList.splice(idx >= 0 ? idx : targetList.length, 0, newBlock);
      }
      renderBlocks();
    }
  });

  return slot;
}

// ── Boutons de contrôle ───────────────────────────────────────────────────────
function makeMoveButtons() {
  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:flex;flex-direction:row;gap:2px;flex-shrink:0;';
  wrap.innerHTML = `
    <button class="tiny-btn btn-up"   title="Monter"    style="padding:2px 7px;font-size:11px;line-height:1.4;cursor:pointer;">▲</button>
    <button class="tiny-btn btn-down" title="Descendre" style="padding:2px 7px;font-size:11px;line-height:1.4;cursor:pointer;">▼</button>
  `;
  return wrap;
}

// ── Rendu de l'arbre ──────────────────────────────────────────────────────────
function renderTree(blockList, container) {
  container.innerHTML = '';

  // Premier drop slot (avant le premier bloc)
  container.appendChild(makeDropSlot(blockList, blockList[0] || null));

  blockList.forEach((block) => {
    const blockDiv = document.createElement('div');
    blockDiv.style.cssText = 'margin-bottom:2px;font-family:monospace;font-size:16px;';

    if (block.type.startsWith('if_')) {
      const isElse = block.type.endsWith('_else');

      // ── Header ──
      const header = document.createElement('div');
      header.setAttribute('draggable', 'true');
      header.style.cssText = 'background:linear-gradient(180deg,var(--green),var(--green-dark));padding:10px 14px;border-radius:12px 12px 0 0;color:white;display:flex;align-items:center;justify-content:space-between;font-weight:bold;box-shadow:inset 0 2px 0 rgba(255,255,255,.2);cursor:grab;';

      const leftPart = document.createElement('div');
      leftPart.style.cssText = 'display:flex;align-items:center;';
      const label = document.createElement('span');
      label.innerHTML = `${typeLabel(block.type)}(${colorSelect(block.color)}) alors`;
      leftPart.appendChild(label);

      const delBtn = document.createElement('button');
      delBtn.className = 'tiny-btn btn-del';
      delBtn.textContent = '✕';
      delBtn.style.cssText = 'margin-left:4px;color:black;cursor:pointer;';

      const rightGroup = document.createElement('div');
      rightGroup.style.cssText = 'display:flex;align-items:center;gap:4px;';
      rightGroup.appendChild(makeMoveButtons());
      rightGroup.appendChild(delBtn);

      header.appendChild(leftPart);
      header.appendChild(rightGroup);
      blockDiv.appendChild(header);

      // ── Children (alors) ──
      const childrenDiv = document.createElement('div');
      childrenDiv.className = 'block-children';
      childrenDiv.style.cssText = 'border-left:16px solid var(--green-dark);padding:6px 10px 6px 20px;min-height:40px;background:rgba(0,0,0,.02);';
      blockDiv.appendChild(childrenDiv);

      // ── Sinon ──
      let childrenElseDiv = null;
      if (isElse) {
        const elseHeader = document.createElement('div');
        elseHeader.style.cssText = 'background:linear-gradient(180deg,var(--green),var(--green-dark));padding:8px 14px;color:white;display:flex;align-items:center;font-weight:bold;border-top:1px solid rgba(255,255,255,.3);';
        elseHeader.textContent = 'sinon';
        blockDiv.appendChild(elseHeader);

        childrenElseDiv = document.createElement('div');
        childrenElseDiv.className = 'block-children-else';
        childrenElseDiv.style.cssText = 'border-left:16px solid var(--green-dark);padding:6px 10px 6px 20px;min-height:40px;background:rgba(0,0,0,.02);';
        blockDiv.appendChild(childrenElseDiv);
      }

      // ── Footer ──
      const footer = document.createElement('div');
      footer.style.cssText = 'background:linear-gradient(180deg,var(--green),var(--green-dark));padding:8px 14px;border-radius:0 0 12px 12px;color:white;font-weight:bold;';
      footer.textContent = 'finsi';
      blockDiv.appendChild(footer);

      // ── Drop zones récursives ──
      if (!block.children) block.children = [];
      renderTree(block.children, childrenDiv);

      if (isElse) {
        if (!block.childrenElse) block.childrenElse = [];
        renderTree(block.childrenElse, childrenElseDiv);
      }

      // ── Drag depuis header ──
      header.addEventListener('dragstart', e => {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'SELECT' || e.target.tagName === 'OPTION') {
          e.preventDefault(); return;
        }
        e.stopPropagation();
        draggedBlock = block;
        e.dataTransfer.setData('text/plain', '__workspace_move__');
        setTimeout(() => { header.style.opacity = '0.45'; }, 0);
      });
      header.addEventListener('dragend', () => {
        header.style.opacity = '1';
        if (draggedBlock) { draggedBlock = null; renderBlocks(); }
      });

      // ── Events ──
      const colorSel = header.querySelector('.color-select');
      if (colorSel) colorSel.addEventListener('change', e => { block.color = e.target.value; });
      delBtn.addEventListener('click', e => { e.stopPropagation(); deleteBlock(block); });
      rightGroup.querySelector('.btn-up').addEventListener('click', e => { e.stopPropagation(); moveUp(block); });
      rightGroup.querySelector('.btn-down').addEventListener('click', e => { e.stopPropagation(); moveDown(block); });

    } else {
      // ── Bloc simple ──
      const inner = document.createElement('div');
      inner.setAttribute('draggable', 'true');
      inner.style.cssText = 'background:linear-gradient(180deg,var(--green),var(--green-dark));padding:10px 14px;border-radius:12px;color:white;display:flex;align-items:center;justify-content:space-between;font-weight:bold;box-shadow:inset 0 2px 0 rgba(255,255,255,.2);cursor:grab;';

      const leftPart = document.createElement('div');
      leftPart.style.cssText = 'display:flex;align-items:center;';
      const label = document.createElement('span');
      label.innerHTML = `${typeLabel(block.type)}(→${colorSelect(block.color)})`;
      leftPart.appendChild(label);

      const delBtn = document.createElement('button');
      delBtn.className = 'tiny-btn btn-del';
      delBtn.textContent = '✕';
      delBtn.style.cssText = 'margin-left:4px;color:black;cursor:pointer;';

      const rightGroup = document.createElement('div');
      rightGroup.style.cssText = 'display:flex;align-items:center;gap:4px;';
      rightGroup.appendChild(makeMoveButtons());
      rightGroup.appendChild(delBtn);

      inner.appendChild(leftPart);
      inner.appendChild(rightGroup);
      blockDiv.appendChild(inner);

      // ── Drag depuis inner ──
      inner.addEventListener('dragstart', e => {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'SELECT' || e.target.tagName === 'OPTION') {
          e.preventDefault(); return;
        }
        e.stopPropagation();
        draggedBlock = block;
        e.dataTransfer.setData('text/plain', '__workspace_move__');
        setTimeout(() => { inner.style.opacity = '0.45'; }, 0);
      });
      inner.addEventListener('dragend', () => {
        inner.style.opacity = '1';
        if (draggedBlock) { draggedBlock = null; renderBlocks(); }
      });

      // ── Events ──
      const colorSel = inner.querySelector('.color-select');
      if (colorSel) colorSel.addEventListener('change', e => { block.color = e.target.value; });
      delBtn.addEventListener('click', e => { e.stopPropagation(); deleteBlock(block); });
      rightGroup.querySelector('.btn-up').addEventListener('click', e => { e.stopPropagation(); moveUp(block); });
      rightGroup.querySelector('.btn-down').addEventListener('click', e => { e.stopPropagation(); moveDown(block); });
    }

    container.appendChild(blockDiv);
    // Drop slot après chaque bloc
    const nextBlock = blockList[blockList.indexOf(block) + 1] || null;
    container.appendChild(makeDropSlot(blockList, nextBlock));
  });
}

function renderBlocks() {
  renderTree(rootBlocks, workspace);
}

// ── Palette drag ──────────────────────────────────────────────────────────────
palette.querySelectorAll('[draggable="true"]').forEach(el => {
  el.addEventListener('dragstart', e => {
    draggedBlock = null; // c'est un nouveau bloc, pas un déplacement
    e.dataTransfer.setData('text/plain', el.dataset.type);
  });
});

// Le workspace principal accepte les dépôts directs (palette → workspace vide)
workspace.addEventListener('dragover', e => { e.preventDefault(); workspace.style.backgroundColor = '#eaeaea'; });
workspace.addEventListener('dragleave', () => { workspace.style.backgroundColor = '#f8f8f8'; });
workspace.addEventListener('drop', e => {
  e.preventDefault();
  workspace.style.backgroundColor = '#f8f8f8';
  const type = e.dataTransfer.getData('text/plain');
  if (type && type !== '__workspace_move__') {
    rootBlocks.push({ type, color: 'b', children: [] });
    renderBlocks();
  } else if (type === '__workspace_move__' && draggedBlock) {
    // Déposé directement sur le workspace sans slot → ajouter à la fin
    const movingBlock = draggedBlock;
    draggedBlock = null;
    const loc = findBlock(movingBlock, rootBlocks);
    if (loc) loc.list.splice(loc.index, 1);
    rootBlocks.push(movingBlock);
    renderBlocks();
  }
});

// ── Extraction à plat (pour envoi au serveur) ─────────────────────────────────
function extractFlatBlocks(blockList, indent = 0) {
  let flat = [];
  blockList.forEach(b => {
    if (b.type.startsWith('if_')) {
      flat.push({ type: b.type, color: b.color, indent });
      if (b.children) flat = flat.concat(extractFlatBlocks(b.children, indent + 1));
      if (b.type.endsWith('_else')) {
        flat.push({ type: 'sinon', color: null, indent });
        if (b.childrenElse) flat = flat.concat(extractFlatBlocks(b.childrenElse, indent + 1));
      }
      flat.push({ type: 'finsi', color: null, indent });
    } else {
      flat.push({ type: b.type, color: b.color, indent });
    }
  });
  return flat;
}

// ── Pseudo-code étudiant ──────────────────────────────────────────────────────
function codeBlock(content) {
  return `<div style="background:#282a36;color:#f8f8f2;padding:10px;border-radius:8px;margin-top:5px;font-family:monospace;white-space:pre-wrap;text-align:left;">${content}</div>`;
}
function setLoading(msg) {
  feedbackText.innerHTML = `<i style="color:#888;">${msg}</i>`;
}
function buildStudentPseudocode(blocks) {
  let lines = [], lineNo = 1;
  blocks.forEach(b => {
    const indent = '    '.repeat(b.indent);
    const cn = { b: 'bleue', j: 'jaune', r: 'rouge', v: 'verte' }[b.color] || '';
    let text = '';
    if (b.type === 'if_not_empty' || b.type === 'if_not_empty_else') text = `si non est_vide(${cn}) alors`;
    else if (b.type === 'if_empty' || b.type === 'if_empty_else') text = `si est_vide(${cn}) alors`;
    else if (b.type === 'sinon') text = 'sinon';
    else if (b.type === 'poser') text = `poser(→${cn})`;
    else if (b.type === 'retirer') text = `retirer(→${cn})`;
    else if (b.type === 'finsi') text = 'finsi';
    if (text) { lines.push(`${lineNo}: ${indent}${text}`); lineNo++; }
  });
  return lines.join('\n') || '(algorithme vide)';
}

// ── Demander de l'aide ────────────────────────────────────────────────────────
document.getElementById('helpBtn').addEventListener('click', async () => {
  const blocks = extractFlatBlocks(rootBlocks);
  setLoading('Génération de la recommandation…');
  let data;
  try {
    const res = await fetch(`/api/student/help/${window.STUDENT_EXERCISE.exerciseId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blocks })
    });
    const text = await res.text();
    try { data = JSON.parse(text); }
    catch (_) {
      feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur serveur (non-JSON).<br><pre style="font-size:11px;color:#aaa;">${text.slice(0, 500)}</pre></span>`;
      return;
    }
  } catch (err) {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur réseau : ${err.message}</span>`;
    return;
  }
  const studentCode = buildStudentPseudocode(blocks);
  if (data.ok) {
    let html = `<b>Votre code actuel :</b>${codeBlock(studentCode)}<br>`;
    if (data.contre_exemple) html += `<b>🔍 Contre-exemple :</b><br><span style="color:#ff5555;font-family:monospace;">${data.contre_exemple}</span><br><br>`;
    if (data.message) html += `<b>💡 Recommandation :</b><br>${data.message}`;
    feedbackText.innerHTML = html;
  } else {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur : ${data.message || JSON.stringify(data)}</span>`;
  }
});

// ── Envoyer la solution ───────────────────────────────────────────────────────
async function submitSolution() {
  const blocks = extractFlatBlocks(rootBlocks);
  setLoading('Vérification de votre solution…');
  let data;
  try {
    const res = await fetch(`/api/student/submit/${window.STUDENT_EXERCISE.exerciseId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blocks })
    });
    const text = await res.text();
    try { data = JSON.parse(text); }
    catch (_) {
      feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur serveur (non-JSON).<br><pre style="font-size:11px;color:#aaa;">${text.slice(0, 500)}</pre></span>`;
      return;
    }
  } catch (err) {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur réseau : ${err.message}</span>`;
    return;
  }
  if (data.ok) {
    if (data.is_correct) {
      feedbackText.innerHTML = `
        <div style="text-align:center;padding:20px;">
          <div style="font-size:48px;margin-bottom:10px;">🎉</div>
          <b style="font-size:20px;color:#50fa7b;">Bravo, votre algorithme est correct !</b>
          <br><br>
          <p style="color:#ccc;">L'exercice a été validé et envoyé à votre professeur.</p>
          <br>
          <a href="/student/dashboard"
             style="display:inline-block;padding:10px 24px;background:var(--green);color:white;border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px;">
            ← Retour aux exercices
          </a>
        </div>`;
      document.getElementById('submitBtn').disabled = true;
      document.getElementById('helpBtn').disabled = true;
    } else {
      const fb = data.feedback;
      let html = `<b>❌ Code incorrect</b><br><br>`;
      if (fb.contre_exemple) html += `<b>🔍 Contre-exemple :</b><br><span style="color:#ff5555;font-family:monospace;">${fb.contre_exemple}</span>`;
      feedbackText.innerHTML = html;
    }
  } else {
    feedbackText.innerHTML = `<span style="color:#ff5555;">Erreur : ${data.message || JSON.stringify(data)}</span>`;
  }
}

document.getElementById('submitBtn').addEventListener('click', submitSolution);

renderBlocks();