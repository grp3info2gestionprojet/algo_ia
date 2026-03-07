const palette = document.getElementById('palette');
const workspace = document.getElementById('workspace');
const feedbackText = document.getElementById('feedbackText');
let blocks = [];

function colorSelect(selected='b'){
  return `<select class="color-select">\
    <option value="b" ${selected==='b'?'selected':''}>Bleue</option>\
    <option value="j" ${selected==='j'?'selected':''}>Jaune</option>\
    <option value="r" ${selected==='r'?'selected':''}>Rouge</option>\
    <option value="v" ${selected==='v'?'selected':''}>Verte</option>\
  </select>`;
}

function typeLabel(type){
  if(type==='if_not_empty') return 'si non est_vide';
  if(type==='if_empty') return 'si est_vide';
  if(type==='retirer') return 'retirer';
  if(type==='poser') return 'poser';
  return 'finsi';
}

function renderBlocks(){
  workspace.innerHTML = '';
  blocks.forEach((block, index) => {
    const row = document.createElement('div');
    row.className = 'workspace-item';
    const blockDiv = document.createElement('div');
    blockDiv.className = 'workspace-block';
    blockDiv.style.marginLeft = `${block.indent * 28}px`;
    blockDiv.innerHTML = `
      <div>
        <span>${typeLabel(block.type)}</span>
        ${block.type !== 'finsi' ? colorSelect(block.color || 'b') : ''}
        ${block.type === 'if_not_empty' || block.type === 'if_empty' ? '<span> alors</span>' : ''}
      </div>
      <div class="workspace-controls">
        <button class="tiny-btn" data-act="left">←</button>
        <button class="tiny-btn" data-act="right">→</button>
        <button class="tiny-btn" data-act="up">↑</button>
        <button class="tiny-btn" data-act="down">↓</button>
        <button class="tiny-btn" data-act="delete">✕</button>
      </div>
    `;
    const select = blockDiv.querySelector('.color-select');
    if(select){
      select.value = block.color || 'b';
      select.addEventListener('change', e => {
        blocks[index].color = e.target.value;
      });
    }
    blockDiv.querySelectorAll('[data-act]').forEach(btn => {
      btn.addEventListener('click', () => actOnBlock(index, btn.dataset.act));
    });
    row.appendChild(blockDiv);
    workspace.appendChild(row);
  });
}

function actOnBlock(index, act){
  const block = blocks[index];
  if(act==='left') block.indent = Math.max(0, block.indent - 1);
  if(act==='right') block.indent += 1;
  if(act==='delete') blocks.splice(index, 1);
  if(act==='up' && index > 0) [blocks[index-1], blocks[index]] = [blocks[index], blocks[index-1]];
  if(act==='down' && index < blocks.length - 1) [blocks[index+1], blocks[index]] = [blocks[index], blocks[index+1]];
  renderBlocks();
}

function addBlock(type){
  blocks.push({ type, color: 'b', indent: 0 });
  renderBlocks();
}

palette.querySelectorAll('[draggable="true"]').forEach(el => {
  el.addEventListener('dragstart', e => {
    e.dataTransfer.setData('text/plain', el.dataset.type);
  });
});
workspace.addEventListener('dragover', e => e.preventDefault());
workspace.addEventListener('drop', e => {
  e.preventDefault();
  const type = e.dataTransfer.getData('text/plain');
  if(type) addBlock(type);
});

async function askHelp(){
  const res = await fetch(`/api/student/help/${window.STUDENT_EXERCISE.exerciseId}`, { method: 'POST' });
  const data = await res.json();
  feedbackText.textContent = JSON.stringify(data, null, 2);
}

async function submitSolution(){
  const res = await fetch(`/api/student/submit/${window.STUDENT_EXERCISE.exerciseId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ blocks })
  });
  const data = await res.json();
  feedbackText.textContent = JSON.stringify(data, null, 2);
}

document.getElementById('helpBtn').addEventListener('click', askHelp);
document.getElementById('submitBtn').addEventListener('click', submitSolution);
renderBlocks();
