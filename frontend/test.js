
/* ── Config ──────────────────────────────────────── */
let API = localStorage.getItem('pb_api') || 'http://127.0.0.1:8000';
let TOPK = parseInt(localStorage.getItem('pb_topk') || '5');
let SESSION = 'sess_' + Date.now();
let docs = [];
let msgCount = 0;
let busy = false;

/* ── Init ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('api-url').value = API;
  document.getElementById('top-k').value = TOPK;
  setupUpload();
  refreshAll();
  setInterval(checkHealth, 30000);
});

/* ── Health ──────────────────────────────────────── */
async function checkHealth() {
  try {
    var r = await fetch(API + '/health', { signal: AbortSignal.timeout(5000) });
    var d = await r.json();
    var on = d && d.llm && d.llm.available === true;
    var model = (d && d.llm && d.llm.model) ? d.llm.model : 'Unknown';
    setStatus(on, model);
    return on;
  } catch(e) { setStatus(false, ''); return false; }
}

function setStatus(on, model) {
  var pill  = document.getElementById('llm-pill');
  var label = document.getElementById('llm-label');
  if (on) {
    pill.className = 'llm-pill';
    label.textContent = model || 'Online';
  } else {
    pill.className = 'llm-pill offline';
    label.textContent = 'Offline';
  }
  document.getElementById('send-btn').disabled = !on;
}

async function refreshLLM() {
  var btn = document.getElementById('llm-refresh');
  btn.classList.add('spinning'); btn.disabled = true;
  var on = await checkHealth();
  btn.classList.remove('spinning'); btn.disabled = false;
  btn.textContent = on ? '\u2713' : '\u27F3';
  toast(on ? 'LLM online \u2713' : 'LLM offline \u2014 start Ollama', on ? 'success' : 'error');
  setTimeout(function(){ btn.textContent = '\u27F3'; }, 2000);
}

/* ── Documents ───────────────────────────────────── */
async function loadDocs() {
  try {
    var r = await fetch(API + '/documents');
    var d = await r.json();
    docs = d.documents || [];
    renderDocs();
    updateStats();
  } catch(e) { docs = []; renderDocs(); }
}

function renderDocs() {
  var list  = document.getElementById('doc-list');
  var badge = document.getElementById('doc-badge');
  var row   = document.getElementById('stat-row');
  if (!docs.length) {
    list.innerHTML = '<div class="empty-docs"><span>&#x1F4ED;</span>No documents yet<br/>Upload a PDF to start</div>';
    badge.style.display = 'none'; row.style.display = 'none'; return;
  }
  badge.style.display = ''; badge.textContent = docs.length;
  row.style.display = 'flex';
  list.innerHTML = docs.map(function(doc) {
    var name   = doc.filename || 'unknown.pdf';
    var pages  = doc.page_count || '?';
    var chunks = doc.chunk_count || '?';
    var size   = fmtBytes(doc.file_size_bytes || 0);
    return '<div class="doc-card">'
      + '<div class="doc-icon">&#x1F4C4;</div>'
      + '<div style="flex:1;min-width:0">'
      + '<div class="doc-name" title="' + esc(name) + '">' + esc(name) + '</div>'
      + '<div class="doc-meta">' + pages + ' pages &middot; ' + chunks + ' chunks &middot; ' + size + '</div>'
      + '<span class="doc-badge">indexed</span>'
      + '</div>'
      + '<button class="doc-del" onclick="delDoc(\'' + esc(name) + '\')" title="Delete">&#x2715;</button>'
      + '</div>';
  }).join('');
}

function updateStats() {
  document.getElementById('s-docs').textContent   = docs.length;
  document.getElementById('s-chunks').textContent = docs.reduce(function(a,d){ return a+(d.chunk_count||0); }, 0);
  document.getElementById('s-msgs').textContent   = msgCount;
  var tb = document.getElementById('t-badge');
  if (docs.length) { tb.style.display=''; tb.textContent = docs.length + ' doc' + (docs.length>1?'s':'') + ' loaded'; }
  else tb.style.display = 'none';
}

async function delDoc(name) {
  try {
    await fetch(API + '/documents/' + encodeURIComponent(name), { method: 'DELETE' });
    toast('Deleted ' + name, 'success'); await loadDocs();
  } catch(e) { toast('Delete failed', 'error'); }
}

async function deleteAll() {
  try {
    await fetch(API + '/documents', { method: 'DELETE' });
    toast('All documents deleted', 'success'); await loadDocs();
  } catch(e) { toast('Delete failed', 'error'); }
}

/* ── Upload ──────────────────────────────────────── */
function dbg(msg) {
  var log = document.getElementById('dbg-log');
  if (!log) return;
  log.style.display = 'block';
  var el = document.createElement('div');
  el.textContent = new Date().toLocaleTimeString() + ' > ' + msg;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

function setupUpload() {
  var inp = document.getElementById('file-input');
  if (!inp) { console.error('file-input not found'); return; }

  inp.addEventListener('change', function(e) {
    var files = Array.from(e.target.files);
    dbg('Selected: ' + files.length + ' file(s)');
    files.forEach(function(f) { uploadFile(f); });
    this.value = '';
  });

  var zone = document.getElementById('drop-zone');
  if (zone) {
    zone.addEventListener('dragover',  function(e){ e.preventDefault(); zone.classList.add('drag'); });
    zone.addEventListener('dragleave', function(){  zone.classList.remove('drag'); });
    zone.addEventListener('drop', function(e) {
      e.preventDefault(); zone.classList.remove('drag');
      var files = Array.from(e.dataTransfer.files).filter(function(f){
        return f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf';
      });
      dbg('Dropped: ' + files.length + ' file(s)');
      files.forEach(function(f){ uploadFile(f); });
    });
  }

  dbg('Ready. API: ' + API);
}

async function uploadFile(file) {
  dbg('Uploading: ' + file.name + ' (' + (file.size/1024).toFixed(0) + ' KB)');

  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
    dbg('Rejected: not a PDF'); toast('Only PDF files supported', 'error'); return;
  }
  if (file.size > 200*1024*1024) {
    dbg('Rejected: too large'); toast('Max 200 MB per file', 'error'); return;
  }

  var wrap = document.getElementById('prog-wrap');
  var fill = document.getElementById('prog-fill');
  var lbl  = document.getElementById('prog-lbl');
  if (wrap) wrap.style.display = 'block';
  if (lbl)  lbl.textContent = 'Uploading ' + file.name + '...';
  if (fill) fill.style.width = '20%';

  var fd = new FormData();
  fd.append('file', file);

  try {
    if (fill) fill.style.width = '50%';
    dbg('POST ' + API + '/upload');
    var r = await fetch(API + '/upload', { method: 'POST', body: fd });
    if (fill) fill.style.width = '85%';

    var txt = await r.text();
    dbg('HTTP ' + r.status + ' | ' + txt.slice(0, 120));

    var d = {};
    try { d = JSON.parse(txt); } catch(e) { dbg('JSON parse error'); }

    if (!r.ok) {
      var em = (d && d.detail) ? d.detail : ('Server error ' + r.status);
      dbg('FAILED: ' + em);
      toast('Upload failed: ' + em, 'error');
      if (wrap) wrap.style.display = 'none';
      return;
    }

    if (fill) fill.style.width = '100%';
    var msg = (d && d.already_exists)
      ? 'Already indexed: ' + file.name
      : 'Indexed: ' + file.name + ' (' + ((d && d.page_count) || '?') + ' pages)';
    dbg(msg);
    toast(msg, (d && d.already_exists) ? 'warn' : 'success');
    await loadDocs();

  } catch(err) {
    dbg('Network error: ' + err.message);
    toast('Cannot reach ' + API + ': ' + err.message, 'error');
  } finally {
    setTimeout(function(){
      if (wrap) wrap.style.display = 'none';
      if (fill) fill.style.width = '0';
    }, 1500);
  }
}

/* ── Chat ────────────────────────────────────────── */
async function sendMsg() {
  var input = document.getElementById('q-input');
  var q = input.value.trim();
  if (!q || busy) return;
  if (!docs.length) { toast('Upload a PDF first', 'warn'); return; }

  busy = true;
  input.value = ''; input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;
  document.getElementById('char-cnt').textContent = '0 / 2000';

  var welcome = document.getElementById('welcome');
  if (welcome) welcome.style.display = 'none';

  msgCount++; updateStats();
  appendUser(q);
  var typId = appendTyping();

  try {
    var r = await fetch(API + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, session_id: SESSION, top_k: TOPK })
    });
    removeTyping(typId);
    var d = await r.json();
    appendBot(d.answer || 'No answer.', d.sources || [], d.confidence || 0, d.processing_time_ms || 0);
  } catch(err) {
    removeTyping(typId);
    appendBot('Connection error. Is the backend running?', [], 0, 0);
  }

  busy = false;
  var on = document.getElementById('llm-pill').className.indexOf('offline') === -1;
  document.getElementById('send-btn').disabled = !on;
  scrollBottom();
}

function appendUser(text) {
  var area = document.getElementById('chat-area');
  var el = document.createElement('div');
  el.className = 'msg-row user';
  el.innerHTML = '<div class="av av-u">U</div>'
    + '<div><div class="bubble bubble-u">' + esc(text) + '</div>'
    + '<div class="msg-time">' + now() + '</div></div>';
  area.appendChild(el); scrollBottom();
}

function appendTyping() {
  var area = document.getElementById('chat-area');
  var id = 'typ-' + Date.now();
  var el = document.createElement('div');
  el.id = id; el.className = 'typing-row';
  el.innerHTML = '<div class="av av-b">P</div>'
    + '<div class="typing-bubble"><div class="td"></div><div class="td"></div><div class="td"></div>'
    + '<span style="font-size:.72rem;color:var(--muted);margin-left:4px">Thinking&hellip;</span></div>';
  area.appendChild(el); scrollBottom(); return id;
}

function removeTyping(id) { var el=document.getElementById(id); if(el) el.remove(); }

function appendBot(text, sources, conf, ms) {
  var area = document.getElementById('chat-area');
  var el = document.createElement('div');
  el.className = 'msg-row';
  var inner = '<div class="bubble bubble-b"><div class="msg-content">' + esc(text) + '</div>';
  if (conf > 0) {
    var pct = Math.round(conf * 100);
    var col = pct >= 75 ? '#1d4ed8' : pct >= 50 ? '#f59e0b' : '#ef4444';
    inner += '<div class="conf-wrap"><div class="conf-lbl"><span>Relevance</span><span>' + pct + '%</span></div>'
      + '<div class="conf-track"><div class="conf-fill" style="width:' + pct + '%;background:' + col + '"></div></div></div>';
  }
  if (sources && sources.length) {
    inner += '<div class="cites">' + sources.slice(0,3).map(function(s) {
      return '<div class="cite"><div class="cite-file">&#x1F4C4; ' + esc(s.filename||'') + '</div>'
        + '<div class="cite-snip">' + esc((s.content||'').slice(0,110)) + '&hellip;</div>'
        + (s.page_number ? '<div class="cite-pg">Page ' + s.page_number + '</div>' : '') + '</div>';
    }).join('') + '</div>';
  }
  inner += '</div><div class="msg-time">' + now() + (ms ? ' &middot; &#x26A1; ' + ms + 'ms' : '') + '</div>';
  el.innerHTML = '<div class="av av-b">P</div><div style="flex:1;max-width:76%">' + inner + '</div>';
  area.appendChild(el); scrollBottom();
}

/* ── Helpers ─────────────────────────────────────── */
function scrollBottom(){ var a=document.getElementById('chat-area'); a.scrollTop=a.scrollHeight; }
function now(){ return new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}); }
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fmtBytes(b){ if(b<1024) return b+' B'; if(b<1048576) return (b/1024).toFixed(1)+' KB'; return (b/1048576).toFixed(1)+' MB'; }
function autoResize(el){ el.style.height='auto'; el.style.height=Math.min(el.scrollHeight,110)+'px'; }
function updateCount(el){ document.getElementById('char-cnt').textContent=el.value.length+' / 2000'; }
function handleKey(e){ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); sendMsg(); } }
function toast(msg,type,ms){
  var c=document.getElementById('toasts'); var el=document.createElement('div');
  el.className='toast '+(type||''); el.textContent=msg; c.appendChild(el);
  setTimeout(function(){ el.remove(); }, ms||3200);
}

/* ── Settings ────────────────────────────────────── */
function toggleSettings(){
  var b=document.getElementById('s-body'); var c=document.getElementById('s-caret');
  var open=b.classList.toggle('open'); c.textContent=open?'\u25B4':'\u25BE';
}
function saveSettings(){
  API  = document.getElementById('api-url').value.trim() || 'http://127.0.0.1:8000';
  TOPK = parseInt(document.getElementById('top-k').value) || 5;
  localStorage.setItem('pb_api', API); localStorage.setItem('pb_topk', TOPK);
  toast('Settings saved', 'success'); refreshAll();
}
function resetUrl(){
  API = 'http://127.0.0.1:8000';
  localStorage.setItem('pb_api', API);
  document.getElementById('api-url').value = API;
  toast('URL reset to ' + API, 'success'); refreshAll();
}

/* ── Modal ───────────────────────────────────────── */
function openModal()   { document.getElementById('modal').classList.add('open'); }
function closeModal()  { document.getElementById('modal').classList.remove('open'); }
function confirmDelete(){ closeModal(); deleteAll(); }

/* ── Refresh ─────────────────────────────────────── */
async function refreshAll() { await checkHealth(); await loadDocs(); }

