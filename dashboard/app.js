/* Agent Rewards — Dashboard (no-build static, vanilla JS)
   Talks to the backend's /v1 API via RELATIVE URLs (served at site root).
   Bearer token kept in localStorage.
*/
(function () {
  'use strict';

  const API_BASE = '/v1';
  const KEY_STORE = 'ar_api_key';
  const MAX_EVENTS = 400;        // cap timeline events rendered
  const MAX_JSON_CHARS = 4000;   // cap pretty-printed size of a single node
  const MAX_TEXT_CHARS = 8000;   // cap raw text content display

  /* ---------------- state ---------------- */
  let apiKey = localStorage.getItem(KEY_STORE) || '';
  let currentTraceId = null;

  /* ---------------- DOM ---------------- */
  const $ = (id) => document.getElementById(id);
  const gate = $('gate'), app = $('app');
  const keyInput = $('key-input'), gateErr = $('gate-err'), gateOk = $('gate-ok');
  const statsEl = $('stats'), recentEl = $('recent'), tracesBody = $('traces-body');
  const bannerHolder = $('banner-holder');
  const viewerMeta = $('viewer-meta'), timelineEl = $('timeline');

  /* ---------------- auth / api ---------------- */
  function headers() {
    return { 'Authorization': 'Bearer ' + apiKey, 'Accept': 'application/json' };
  }

  async function api(path, opts) {
    opts = opts || {};
    const res = await fetch(API_BASE + path, Object.assign({ headers: headers() }, opts));
    if (res.status === 204) return null;
    const type = res.headers.get('content-type') || '';
    const body = type.indexOf('json') >= 0 ? await res.json().catch(() => null) : await res.text();
    if (!res.ok) {
      const msg = (body && (body.error || body.detail)) || ('HTTP ' + res.status);
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return body;
  }

  function clearBanners() { bannerHolder.innerHTML = ''; }
  function showBanner(kind, text) {
    const b = document.createElement('div');
    b.className = 'banner ' + kind;
    b.innerHTML = '<span>' + esc(text) + '</span><span class="x" onclick="this.parentNode.remove()">✕</span>';
    bannerHolder.appendChild(b);
  }
  function setGateMsg(ok, text) {
    gateOk.textContent = ok ? text : '';
    gateErr.textContent = ok ? '' : text;
  }

  /* ---------------- escape & formatting ---------------- */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function fmtBytes(n) {
    if (n == null) return '—';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(2) + ' MB';
  }
  function fmtTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d)) return esc(iso);
    return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
  function shortId(id) {
    if (!id) return '—';
    return id.length > 16 ? id.slice(0, 8) + '…' + id.slice(-6) : id;
  }
  // colorize pretty JSON: keys, strings, numbers, booleans, null
  function jsonHighlight(str) {
    return str.replace(/("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false)\b|\bnull\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
      function (m, key, colon, bool, num) {
        if (key) return '<span class="jk">' + key + '</span>' + (colon || '');
        if (bool) return '<span class="jb">' + bool + '</span>';
        if (num !== undefined) return '<span class="jn">' + num + '</span>';
        if (m === 'null') return '<span class="jl">null</span>';
        return m;
      });
  }
  function prettyJson(node) {
    try {
      const str = JSON.stringify(node, null, 2);
      return str.length > MAX_JSON_CHARS
        ? str.slice(0, MAX_JSON_CHARS) + '\n… (truncated)'  : str;
    } catch (e) { return String(node); }
  }

  /* ---------------- gate ---------------- */
  async function validateKey(k) {
    // credits is a cheap, authenticated endpoint — 401/403 => bad key
    const res = await fetch(API_BASE + '/credits', { headers: { 'Authorization': 'Bearer ' + k } });
    if (res.ok) return true;
    if (res.status === 401 || res.status === 403) return false;
    // reached server but other error (e.g. 500) — let caller surface it
    throw new Error('Server error ' + res.status);
  }

  async function connect() {
    const k = keyInput.value.trim();
    if (!k) { setGateMsg(false, 'Enter your API key.'); return; }
    $('connect-btn').disabled = true;
    $('connect-btn').textContent = 'Connecting…';
    setGateMsg(false, '');
    try {
      const ok = await validateKey(k);
      if (!ok) { setGateMsg(false, 'Invalid API key — check it and try again.'); }
      else {
        setGateMsg(true, 'Connected ✓');
        apiKey = k;
        localStorage.setItem(KEY_STORE, k);
        enterApp();
      }
    } catch (e) {
      setGateMsg(false, 'Could not reach server: ' + esc(e.message));
    } finally {
      $('connect-btn').disabled = false;
      $('connect-btn').textContent = '🔑 Connect';
    }
  }

  function disconnect() {
    apiKey = '';
    localStorage.removeItem(KEY_STORE);
    keyInput.value = '';
    gateOk.textContent = ''; gateErr.textContent = '';
    app.classList.add('hidden');
    gate.classList.remove('hidden');
  }

  function enterApp() {
    gate.classList.add('hidden');
    app.classList.remove('hidden');
    showList();
    loadAll();
  }

  /* ---------------- list: credits + traces ---------------- */
  async function loadAll() { await Promise.all([loadCredits(), loadTraces()]); }

  async function loadCredits() {
    recentEl.innerHTML = '<div class="loading">Loading…</div>';
    try {
      const c = await api('/credits');
      const cells = statsEl.querySelectorAll('.val');
      cells[0].textContent = (c.balance != null ? (+c.balance).toFixed(2) : '—');
      cells[0].className = 'val green';
      cells[1].textContent = c.traces_registered != null ? c.traces_registered : '—';
      if (Array.isArray(c.recent) && c.recent.length) {
        let html = '';
        c.recent.forEach((r, i) => {
          const amt = (r.credits != null) ? '+' + (+r.credits).toFixed(2) : '+—';
          html += '<div class="recent-row">'
            + '<span class="rid">' + esc(r.trace_id || ('#' + (i + 1))) + '</span>'
            + '<span class="when">' + fmtTime(r.created_at) + '</span>'
            + '<span class="amt">' + amt + '</span></div>';
        });
        recentEl.innerHTML = html;
      } else {
        recentEl.innerHTML = '<div class="empty">No recent registrations yet.</div>';
      }
    } catch (e) { recentEl.innerHTML = ''; showBanner('err', 'Failed to load credits: ' + e.message); }
  }

  function agentAvatar(agent) {
    const a = (agent || '?').toLowerCase();
    if (a.indexOf('claude') >= 0) return '🔷';
    if (a.indexOf('codex') >= 0) return '⬛';
    if (a.indexOf('grok') >= 0) return '🐦';
    if (a.indexOf('hermes') >= 0) return '🧠';
    if (a.indexOf('openclaw') >= 0) return '🛠';
    return (agent || '?').charAt(0).toUpperCase();
  }

  async function loadTraces() {
    tracesBody.innerHTML = '<tr><td colspan="5"><div class="loading"><span class="spin"></span>Loading traces…</div></td></tr>';
    try {
      const data = await api('/traces');
      const list = data.traces || [];
      if (!list.length) {
        tracesBody.innerHTML = '<tr><td colspan="5"><div class="empty">No traces yet. Upload happens through the MCP tool — use <code>/v1/traces</code> via the agent.</div></td></tr>';
        return;
      }
      let html = '';
      list.slice().sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')).forEach((t) => {
        const agent = t.agent || 'unknown';
        const id = String(t.trace_id);
        html += '<tr data-trace-id="' + esc(id) + '">'
          + '<td><span class="hash">' + esc(shortId(t.trace_id)) + '</span></td>'
          + '<td><span class="agentp"><span class="av">' + agentAvatar(agent) + '</span>' + esc(agent) + '</span></td>'
          + '<td><span class="cred">' + (t.credits != null ? (+t.credits).toFixed(2) : '—') + '</span></td>'
          + '<td><span class="sz">' + fmtBytes(t.size_bytes) + '</span></td>'
          + '<td><span class="when">' + fmtTime(t.created_at) + '</span></td></tr>';
      });
      tracesBody.innerHTML = html;
    } catch (e) {
      tracesBody.innerHTML = '';
      showBanner('err', 'Failed to load traces: ' + e.message);
      if (e.status === 401 || e.status === 403) disconnect();
    }
  }

  function showList() {
    $('view-list').classList.remove('hidden');
    $('view-viewer').classList.add('hidden');
  }
  function showViewer() {
    $('view-list').classList.add('hidden');
    $('view-viewer').classList.remove('hidden');
  }

  // expose functions referenced by inline onclick="" attributes in index.html
  window.showList = showList;
  window.loadCredits = loadCredits;
  window.loadTraces = loadTraces;

  /* ---------------- timeline viewer ---------------- */
  window.openTrace = function (traceId) {
    currentTraceId = traceId;
    showViewer();
    loadTrace(traceId);
  };

  async function loadTrace(traceId) {
    viewerMeta.innerHTML = '';
    timelineEl.innerHTML = '<div class="loading"><span class="spin"></span>Loading trace…</div>';
    try {
      const t = await api('/traces/' + encodeURIComponent(traceId));
      renderMeta(t);
      renderTimeline(t.content || '');
    } catch (e) {
      timelineEl.innerHTML = '<div class="empty">Failed to load trace: ' + esc(e.message) + '</div>';
    }
  }

  function renderMeta(t) {
    const chips = [
      ['Trace', shortId(t.trace_id), 'var(--accent)'],
      ['Agent', t.agent || '—', 'var(--txt)'],
      ['License', t.license || '—', 'var(--gold)'],
      ['Scope', t.scope || '—', 'var(--muted)'],
      ['Created', fmtTime(t.created_at), 'var(--muted)'],
    ];
    viewerMeta.innerHTML = chips.map(([l, v, c]) =>
      '<div class="meta-chip" style="--c:' + c + '"><b>' + esc(l) + ':</b> ' + esc(v) + '</div>').join('');
  }

  // Parse NDJSON content into an array of objects (skips blank / bad lines)
  function parseJsonl(content) {
    const out = [];
    if (!content) return out;
    const lines = String(content).split('\n');
    for (const line of lines) {
      const s = line.trim();
      if (!s) continue;
      try { out.push(JSON.parse(s)); }
      catch (e) { out.push({ _raw: s }); }
    }
    return out;
  }

  function classify(line) {
    const role = line.role || line.type || '';
    const r = String(role).toLowerCase();
    const has = (k) => line[k] !== undefined && line[k] !== null;

    if (has('reasoning') || has('thinking') || r === 'reasoning') {
      return { kind: 'reasoning', badge: 'reasoning', cls: 'role-reasoning', label: 'Reasoning' };
    }
    if ((has('name') && (has('input') || has('arguments')))
        || r === 'tool_use' || r === 'function_call' || r === 'tool_call'
        || (line.name && typeof line.arguments !== 'undefined')) {
      return { kind: 'tool', badge: 'tool', cls: 'role-tool', label: 'Tool call' };
    }
    if ((has('tool_call_id') || has('tool_use_id') || has('id') && has('output'))
        || r === 'tool_result' || r === 'function_call_output' || r === 'tool_result') {
      return { kind: 'tool_result', badge: 'tool', cls: 'role-tool', label: 'Tool result' };
    }
    if (r === 'user') return { kind: 'user', badge: 'user', cls: 'role-user', label: 'User' };
    if (r === 'system') return { kind: 'system', badge: 'system', cls: 'role-system', label: 'System' };
    if (r === 'assistant' || r === 'model' || r === 'bot') {
      return { kind: 'assistant', badge: 'assistant', cls: 'role-assistant', label: 'Assistant' };
    }
    // fallback heuristic
    if (line.content && typeof line.content === 'string' && line.isError === undefined
        && !has('name')) return { kind: 'assistant', badge: 'assistant', cls: 'role-assistant', label: 'Message' };
    return { kind: 'unknown', badge: 'unknown', cls: 'role-unknown', label: 'Event' };
  }

  function firstText(line) {
    const c = line.content;
    if (typeof c === 'string') return c;
    if (Array.isArray(c)) {
      return c.map((b) => (typeof b === 'string' ? b :
        (b.text != null ? b.text : b.content != null && typeof b.content === 'string' ? b.content : ''))).join('\n');
    }
    if (c && typeof c.text === 'string') return c.text;
    return '';
  }

  function renderTimeline(content) {
    const events = parseJsonl(content);
    const total = events.length;
    const shown = events.slice(0, MAX_EVENTS);
    let html = '';

    shown.forEach((line, idx) => {
      let jsonToShow = null;
      const c = classify(line);
      let text = firstText(line);
      let name = '';
      let time = line.timestamp || line.created_at || line.time || '';

      if (c.kind === 'tool') {
        name = line.name || line.function?.name || 'tool';
        const input = line.input !== undefined ? line.input : (line.arguments !== undefined
          ? (typeof line.arguments === 'string' ? safeParse(line.arguments) : line.arguments) : null);
        jsonToShow = input;
        if (!text) text = line.content && typeof line.content === 'string' ? line.content : '';
      } else if (c.kind === 'tool_result') {
        jsonToShow = line.output !== undefined ? line.output
          : (line.content !== undefined ? line.content : null);
        if (line.is_error === true) c.cls = 'role-reasoning', c.label = 'Tool error';
      } else if (c.kind === 'reasoning') {
        const r = line.reasoning !== undefined ? line.reasoning : line.thinking;
        text = (typeof r === 'string') ? r : (r && r.text ? r.text : '');
      } else if (c.kind === 'unknown' && line._raw !== undefined) {
        text = line._raw; // unparseable line
      }

      if (c.kind === 'user' || c.kind === 'assistant' || c.kind === 'system' || c.kind === 'message') {
        jsonToShow = extractExtras(line);
      }

      if (text && text.length > MAX_TEXT_CHARS) {
        text = text.slice(0, MAX_TEXT_CHARS) + '\n… (truncated)';
      }

      html += '<div class="tl-card" data-i="' + idx + '">'
        + '<div class="tl-head">'
        + '<span class="role-badge ' + c.cls + '">' + c.label + '</span>'
        + (name ? '<span class="tl-name">' + esc(name) + '</span>' : '')
        + '<span class="tl-kind">#' + (idx + 1) + '</span>'
        + (time ? '<span class="tl-time">' + esc(time) + '</span>' : '')
        + '</div>'
        + '<div class="tl-body">'
        + (c.kind === 'reasoning' && text ? '<div class="reasoning">' + esc(text) + '</div>' : '')
        + (c.kind !== 'reasoning' && text ? '<div class="text">' + esc(text) + '</div>' : '')
        + (c.kind === 'reasoning' && jsonToShow ? jsonBlock(jsonToShow) : '')
        + (c.kind !== 'reasoning' && jsonToShow != null ? jsonBlock(jsonToShow) : '')
        + '</div></div>';
    });

    if (html === '') {
      html = '<div class="empty">This trace has no viewable events.</div>';
    }
    timelineEl.innerHTML = html;

    let notice = '';
    if (total > shown.length) {
      notice += '<div class="notice-trunc"><b>Truncated.</b> Showing the first '
        + shown.length + ' of ' + total + ' events. ' + (total - shown.length) + ' more hidden.</div>';
    }
    if (content && content.length > 0 && total === 0) {
      notice += '<div class="notice-trunc">Content present but no parseable JSONL events were found.</div>';
    }
    if (notice) timelineEl.insertAdjacentHTML('beforeend', notice);
  }

  function safeParse(s) { try { return JSON.parse(s); } catch (e) { return s; } }

  // for assistant/user/system lines, surface extra structured fields (excluding noise)
  function extractExtras(line) {
    const ex = {};
    const skip = new Set(['role', 'type', 'content', 'timestamp', 'created_at', 'time',
      'agent', 'sessionId', 'session_id', 'cwd', 'model', 'provider', 'parent_uuid', 'uuid', 'id']);
    for (const k of Object.keys(line)) {
      if (skip.has(k)) continue;
      const v = line[k];
      if (v === null || v === undefined) continue;
      if (typeof v === 'string' && v.length > MAX_JSON_CHARS + 2000) continue;
      ex[k] = v;
    }
    return Object.keys(ex).length ? ex : null;
  }

  function jsonBlock(node) {
    if (node === null || node === undefined) return '';
    let str;
    if (typeof node === 'string') {
      // long string output => render as text block
      if (node.length > 60 && node.indexOf('\n') >= 0) return '<div class="text">' + esc(node) + '</div>';
      str = JSON.stringify(node, null, 2);
    } else {
      str = prettyJson(node);
    }
    if (str.length > MAX_JSON_CHARS) str = str.slice(0, MAX_JSON_CHARS) + '\n… (truncated)';
    return '<div class="json"><pre>' + jsonHighlight(esc(str)) + '</pre></div>';
  }

  /* download raw JSONL */
  async function downloadRaw() {
    if (!currentTraceId) return;
    const btn = $('dl-btn');
    btn.disabled = true; btn.textContent = 'Downloading…';
    try {
      const res = await fetch(API_BASE + '/traces/' + encodeURIComponent(currentTraceId) + '/download', {
        headers: headers()
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = currentTraceId + '.jsonl';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      showBanner('err', 'Download failed: ' + e.message);
      if (e.status === 401 || e.status === 403) disconnect();
    } finally {
      btn.disabled = false; btn.textContent = '⬇ Download raw JSONL';
    }
  }

  /* expand / collapse JSON blocks in the viewer */
  function setJsonVisibility(open) {
    document.querySelectorAll('#view-viewer .json').forEach((el) => {
      if (open) { el.style.display = ''; }
      else { el.style.display = 'none'; }
    });
  }

  /* ---------------- wiring ---------------- */
  $('connect-btn').addEventListener('click', connect);
  keyInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') connect(); });
  $('disconnect-btn').addEventListener('click', disconnect);
  $('refresh-btn').addEventListener('click', loadAll);
  $('dl-btn').addEventListener('click', downloadRaw);
  $('viewer-refresh').addEventListener('click', () => currentTraceId && loadTrace(currentTraceId));
  $('collapse-all').addEventListener('click', () => setJsonVisibility(false));
  $('expand-all').addEventListener('click', () => setJsonVisibility(true));
  // open trace viewer on row click (event delegation)
  tracesBody.addEventListener('click', (e) => {
    const tr = e.target.closest('tr[data-trace-id]');
    if (tr) openTrace(tr.getAttribute('data-trace-id'));
  });

  /* boot */
  if (apiKey) enterApp();
  else gate.classList.remove('hidden');
})();
