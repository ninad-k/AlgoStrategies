/* ═══════════════════════════════════════════════════════════
   Rey Capital — US Stock Scanner  |  Frontend Logic
   ═══════════════════════════════════════════════════════════ */

const API = '';   // same-origin

// ── State ──────────────────────────────────────────────────
const state = {
  category:   'multibagger',
  page:        1,
  pageSize:    25,
  minScore:    50,
  sector:      '',
  capFilter:   '',
  sortBy:      null,
  totalPages:  1,
  total:       0,
  pollTimer:   null,
  scheduleTimer: null,
  sessionId:   null,
};

// Category → score column mapping
const SCORE_COL = {
  multibagger:  'multibagger_score',
  investment:   'investment_score',
  swing_medium: 'swing_medium_score',
  swing_short:  'swing_short_score',
};

const CAT_LABEL = {
  multibagger:  '🚀 Multibagger Score',
  investment:   '💼 Investment Score',
  swing_medium: '📈 Swing 2-3W Score',
  swing_short:  '⚡ Swing 2-3D Score',
};

const SCORE_CLASS = {
  multibagger:  'score-gold',
  investment:   'score-green',
  swing_medium: 'score-blue',
  swing_short:  'score-cyan',
};

// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  bindUI();
  checkStatusOnLoad();
  loadScheduleInfo();
  // Refresh schedule badge every 5 minutes
  state.scheduleTimer = setInterval(loadScheduleInfo, 5 * 60 * 1000);
});

function bindUI() {
  // Tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.category = btn.dataset.cat;
      state.page = 1;
      state.sortBy = null;
      updateScoreColumnHeader();
      loadResults();
    });
  });

  // Force Scan button (manual override)
  document.getElementById('btnScan').addEventListener('click', startScan);

  // Min score slider
  const slider = document.getElementById('minScore');
  const sliderVal = document.getElementById('minScoreVal');
  slider.addEventListener('input', () => {
    sliderVal.textContent = slider.value;
    state.minScore = parseInt(slider.value, 10);
    state.page = 1;
    debounce(loadResults, 400)();
  });

  // Sector filter
  document.getElementById('sectorFilter').addEventListener('change', e => {
    state.sector = e.target.value;
    state.page = 1;
    loadResults();
  });

  // Market cap filter
  document.getElementById('capFilter').addEventListener('change', e => {
    state.capFilter = e.target.value;
    state.page = 1;
    loadResults();
  });

  // Page size
  document.getElementById('pageSizeSelect').addEventListener('change', e => {
    state.pageSize = parseInt(e.target.value, 10);
    state.page = 1;
    loadResults();
  });

  // Sortable columns
  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      state.sortBy = th.dataset.col;
      state.page = 1;
      document.querySelectorAll('th.sortable').forEach(h => {
        h.classList.remove('sorted');
        const arrow = h.querySelector('.sort-arrow');
        if (arrow) arrow.textContent = '';
      });
      th.classList.add('sorted');
      let arrow = th.querySelector('.sort-arrow');
      if (!arrow) { arrow = document.createElement('span'); arrow.className = 'sort-arrow'; th.appendChild(arrow); }
      arrow.textContent = ' ↓';
      loadResults();
    });
  });

  // Modal close
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('modalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modalOverlay')) closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });
}

// ── Schedule info ────────────────────────────────────────────
async function loadScheduleInfo() {
  try {
    const res  = await fetch(`${API}/api/scanner/schedule`);
    if (!res.ok) return;
    const data = await res.json();
    updateScheduleBadge(data);
    updateDataBanner(data);
  } catch { /* server not ready */ }
}

function updateScheduleBadge(data) {
  const el = document.getElementById('scheduleText');
  if (!el) return;

  const badge = document.getElementById('scheduleBadge');

  if (data.last_session_status === 'running') {
    el.textContent = 'Scan in progress…';
    badge.className = 'schedule-badge badge-running';
    return;
  }

  if (data.already_ran_today && data.data_age_hours !== null) {
    const age = data.data_age_hours;
    const ageStr = age < 1
      ? `${Math.round(age * 60)}m ago`
      : `${age.toFixed(1)}h ago`;
    el.textContent = `Data refreshed ${ageStr} · Next: tomorrow 8:30 AM ET`;
    badge.className = 'schedule-badge badge-fresh';
  } else {
    el.textContent = `Next scan: ${data.next_scan_et}`;
    badge.className = 'schedule-badge badge-pending';
  }
}

function updateDataBanner(data) {
  const banner = document.getElementById('dataBanner');
  if (!banner) return;

  // Show warning banner only if data is older than 26 hours (stale)
  if (data.data_age_hours !== null && data.data_age_hours > 26) {
    banner.style.display = 'block';
    banner.innerHTML = `
      ⚠ Data is ${data.data_age_hours.toFixed(0)} hours old.
      Next auto-scan: <strong>${data.next_scan_et}</strong>.
      <button class="btn btn-ghost btn-sm" onclick="startScan()" style="margin-left:12px">Scan Now</button>
    `;
  } else {
    banner.style.display = 'none';
  }
}

// ── Scan controls ────────────────────────────────────────────
async function startScan() {
  const btn = document.getElementById('btnScan');
  btn.disabled = true;
  btn.textContent = 'Starting…';

  try {
    const res = await fetch(`${API}/api/scanner/start`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'started') {
      showToast('Scan started — this takes 45-70 minutes', 4000);
      showProgress();
      startPolling();
    } else if (data.status === 'already_running') {
      showToast('Scan already running', 3000);
      showProgress();
      startPolling();
    } else {
      showToast(`Could not start: ${data.message}`, 4000);
      btn.disabled = false;
      btn.textContent = 'Force Scan';
    }
  } catch (err) {
    showToast('Server unreachable', 3000);
    btn.disabled = false;
    btn.textContent = 'Force Scan';
  }
}

function startPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(pollStatus, 4000);
}

async function pollStatus() {
  try {
    const res  = await fetch(`${API}/api/scanner/status`);
    const data = await res.json();
    updateProgressBar(data);

    if (data.status === 'completed') {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
      hideProgress();
      resetScanBtn();
      showToast('Scan complete! Loading results…', 3000);
      await loadSectors();
      loadResults();
      updateLastScanMeta(data.completed_at || data.started_at);
      loadScheduleInfo();  // Refresh schedule badge with new data age
    } else if (data.status === 'failed') {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
      hideProgress();
      resetScanBtn();
      showToast(`Scan failed: ${data.error || 'unknown error'}`, 5000);
      loadScheduleInfo();
    }
  } catch { /* network error — keep polling */ }
}

async function checkStatusOnLoad() {
  try {
    const res  = await fetch(`${API}/api/scanner/status`);
    const data = await res.json();

    if (data.status === 'running') {
      showProgress();
      updateProgressBar(data);
      startPolling();
      document.getElementById('btnScan').disabled = true;
      document.getElementById('btnScan').textContent = 'Scanning…';
    } else {
      resetScanBtn();
      if (data.id) {
        updateLastScanMeta(data.completed_at || data.started_at);
        await loadSectors();
        loadResults();
      }
    }
  } catch { /* server not ready */ }
}

function updateProgressBar(data) {
  const pct  = data.progress_pct || 0;
  const phase = data.phase || 'Running…';
  document.getElementById('progressFill').style.width = `${Math.max(2, pct)}%`;
  document.getElementById('progressText').textContent = `${phase}  —  ${pct}%`;
}

function showProgress() {
  document.getElementById('scanProgressWrap').classList.add('visible');
  document.getElementById('btnScan').disabled = true;
  document.getElementById('btnScan').textContent = 'Scanning…';
}

function hideProgress() {
  document.getElementById('scanProgressWrap').classList.remove('visible');
}

function resetScanBtn() {
  const btn = document.getElementById('btnScan');
  btn.disabled = false;
  btn.textContent = 'Force Scan';
}

function updateLastScanMeta(ts) {
  if (!ts) return;
  const d = new Date(ts + (ts.endsWith('Z') ? '' : 'Z'));
  document.getElementById('lastScanMeta').textContent =
    `Last scan: ${d.toLocaleDateString()} ${d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
}

// ── Load sectors for dropdown ────────────────────────────────
async function loadSectors() {
  try {
    const res  = await fetch(`${API}/api/scanner/sectors`);
    const data = await res.json();
    const sel  = document.getElementById('sectorFilter');
    const current = sel.value;
    sel.innerHTML = '<option value="">All Sectors</option>';
    (data.sectors || []).forEach(s => {
      const opt = document.createElement('option');
      opt.value = s; opt.textContent = s;
      if (s === current) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch { /* ignore */ }
}

// ── Load & render results ────────────────────────────────────
async function loadResults() {
  const { category, page, pageSize, minScore, sector, capFilter, sortBy } = state;
  const { minCap, maxCap } = capToRange(capFilter);

  let url = `${API}/api/scanner/results/${category}?page=${page}&page_size=${pageSize}&min_score=${minScore}`;
  if (sector)  url += `&sector=${encodeURIComponent(sector)}`;
  if (sortBy)  url += `&sort_by=${sortBy}`;
  if (minCap !== null) url += `&min_market_cap=${minCap}`;
  if (maxCap !== null) url += `&max_market_cap=${maxCap}`;

  const tbody = document.getElementById('resultsBody');
  tbody.innerHTML = `<tr><td colspan="12" class="no-data">Loading…</td></tr>`;

  try {
    const res  = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.totalPages = data.total_pages || 1;
    state.total      = data.total || 0;
    state.sessionId  = data.session_id;

    document.getElementById('resultCount').textContent =
      `${data.total.toLocaleString()} stocks found`;

    renderTable(data.results, category);
    renderPagination();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="12" class="no-data">Failed to load results. Is the server running?<br/><small>${err.message}</small></td></tr>`;
  }
}

function capToRange(cap) {
  const map = {
    micro: { minCap: null,   maxCap: 300e6 },
    small: { minCap: 300e6,  maxCap: 2e9 },
    mid:   { minCap: 2e9,    maxCap: 10e9 },
    large: { minCap: 10e9,   maxCap: null },
  };
  return map[cap] || { minCap: null, maxCap: null };
}

// ── Table rendering ──────────────────────────────────────────
function renderTable(rows, category) {
  const tbody = document.getElementById('resultsBody');
  const scoreCol = SCORE_COL[category];
  const offset   = (state.page - 1) * state.pageSize;

  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="12" class="no-data">No stocks match the current filters.<br/><small>Try lowering Min Score or changing the Sector filter.</small></td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map((r, i) => {
    const rank         = offset + i + 1;
    const scoreVal     = r[scoreCol] ?? 0;
    const scoreColor   = scoreBarColor(scoreVal);
    const change       = r.price_change_pct ?? 0;
    const changeClass  = change >= 0 ? 'pos' : 'neg';
    const changeStr    = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
    const mcap         = fmtCap(r.market_cap);
    const rsi          = r.rsi ?? '—';
    const rsiClass     = rsi > 70 ? 'rsi-over' : (rsi < 30 ? 'rsi-under' : 'rsi-mid');
    const rs           = r.rs_vs_spy ?? 1;
    const rsClass      = rs >= 1.1 ? 'rs-strong' : (rs < 0.9 ? 'rs-weak' : 'rs-mid');
    const flags        = Array.isArray(r.red_flags) ? r.red_flags : [];
    const flagClass    = flags.length === 0 ? 'flag-0' : (flags.length === 1 ? 'flag-1' : 'flag-2');
    const stageClass   = `stage-${r.stage || 0}`;

    return `
      <tr data-sym="${r.symbol}" data-session="${r.session_id}">
        <td style="color:var(--text-muted)">${rank}</td>
        <td><span class="sym">${r.symbol}</span></td>
        <td><div class="co-name" title="${r.company_name || ''}">${r.company_name || '—'}</div></td>
        <td style="color:var(--text-muted);font-size:.8rem">${r.sector || '—'}</td>
        <td>$${(r.price ?? 0).toFixed(2)}</td>
        <td class="${changeClass}">${changeStr}</td>
        <td class="cap">${mcap}</td>
        <td><span class="rsi-badge ${rsiClass}">${typeof rsi === 'number' ? rsi.toFixed(1) : rsi}</span></td>
        <td><span class="rs-chip ${rsClass}">${typeof rs === 'number' ? rs.toFixed(2) : '—'}</span></td>
        <td><span class="stage-badge ${stageClass}">${r.stage ? 'S' + r.stage : '—'}</span></td>
        <td>
          <div class="score-bar-wrap">
            <div class="score-bar-track">
              <div class="score-bar-fill" style="width:${scoreVal}%;background:${scoreColor}"></div>
            </div>
            <span class="score-val" style="color:${scoreColor}">${scoreVal.toFixed(0)}</span>
          </div>
        </td>
        <td>
          <span class="flag-count ${flagClass}" title="${flags.join('\n') || 'No flags'}">${flags.length}</span>
        </td>
      </tr>`;
  }).join('');

  // Row click → modal
  tbody.querySelectorAll('tr[data-sym]').forEach(row => {
    row.addEventListener('click', () => openModal(row.dataset.sym, row.dataset.session));
  });
}

function scoreBarColor(val) {
  if (val >= 75) return 'var(--success)';
  if (val >= 55) return 'var(--gold)';
  if (val >= 35) return 'var(--warning)';
  return 'var(--danger)';
}

function fmtCap(n) {
  if (!n || n === 0) return '—';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9)  return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6)  return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

// ── Pagination ───────────────────────────────────────────────
function renderPagination() {
  const el = document.getElementById('pagination');
  const { page, totalPages } = state;

  if (totalPages <= 1) { el.innerHTML = ''; return; }

  const pages = [];
  // Always show first, last, and pages around current
  const range = new Set([1, totalPages]);
  for (let p = Math.max(1, page - 2); p <= Math.min(totalPages, page + 2); p++) range.add(p);

  const sorted = [...range].sort((a, b) => a - b);

  let html = `<button class="page-btn" id="prevPage" ${page === 1 ? 'disabled' : ''}>‹ Prev</button>`;

  let prev = 0;
  for (const p of sorted) {
    if (p - prev > 1) html += `<span class="page-info">…</span>`;
    html += `<button class="page-btn ${p === page ? 'active' : ''}" data-page="${p}">${p}</button>`;
    prev = p;
  }

  html += `<button class="page-btn" id="nextPage" ${page === totalPages ? 'disabled' : ''}>Next ›</button>`;
  html += `<span class="page-info">${state.total.toLocaleString()} results</span>`;

  el.innerHTML = html;

  el.querySelectorAll('[data-page]').forEach(btn => {
    btn.addEventListener('click', () => { state.page = parseInt(btn.dataset.page); loadResults(); });
  });
  const prev_ = el.querySelector('#prevPage');
  const next_ = el.querySelector('#nextPage');
  if (prev_) prev_.addEventListener('click', () => { state.page--; loadResults(); });
  if (next_) next_.addEventListener('click', () => { state.page++; loadResults(); });
}

// ── Score column header ──────────────────────────────────────
function updateScoreColumnHeader() {
  const th = document.getElementById('scoreColHeader');
  const labels = {
    multibagger:  'MB Score',
    investment:   'Inv Score',
    swing_medium: 'SW Score',
    swing_short:  'SS Score',
  };
  th.textContent = labels[state.category] || 'Score';
  th.dataset.col = SCORE_COL[state.category];
}

// ── Modal ────────────────────────────────────────────────────
async function openModal(symbol, sessionId) {
  const overlay = document.getElementById('modalOverlay');
  const body    = document.getElementById('modalBody');

  document.getElementById('modalSymbol').textContent = symbol;
  document.getElementById('modalName').textContent   = 'Loading…';
  body.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted)">Loading…</div>';
  overlay.classList.add('open');

  try {
    const sid = sessionId || '';
    const res  = await fetch(`${API}/api/scanner/stock/${symbol}${sid ? `?session_id=${sid}` : ''}`);
    if (!res.ok) throw new Error('Not found');
    const d = await res.json();

    document.getElementById('modalName').textContent = d.company_name || '';
    body.innerHTML = buildModalBody(d);
  } catch (err) {
    body.innerHTML = `<div style="padding:24px;color:var(--danger)">Failed to load: ${err.message}</div>`;
  }
}

function buildModalBody(d) {
  const flags = Array.isArray(d.red_flags) ? d.red_flags : [];
  const bd    = d.score_breakdown || {};

  // Score cards
  const cards = `
    <div class="score-cards">
      ${scoreCard('🚀 Multibagger', d.multibagger_score,  'score-gold')}
      ${scoreCard('💼 Investment',  d.investment_score,   'score-green')}
      ${scoreCard('📈 Swing 2-3W',  d.swing_medium_score, 'score-blue')}
      ${scoreCard('⚡ Swing 2-3D',  d.swing_short_score,  'score-cyan')}
    </div>`;

  // Key stats row
  const stats = `
    <div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:20px;font-size:.83rem">
      ${stat('Price',     d.price != null ? `$${d.price.toFixed(2)}` : '—')}
      ${stat('Market Cap', fmtCap(d.market_cap))}
      ${stat('RSI',        d.rsi != null  ? d.rsi.toFixed(1) : '—')}
      ${stat('RS/SPY',     d.rs_vs_spy != null ? d.rs_vs_spy.toFixed(2) : '—')}
      ${stat('Stage',      d.stage ? `Stage ${d.stage}` : '—')}
      ${stat('Vol Ratio',  d.volume_ratio != null ? `${d.volume_ratio.toFixed(1)}x` : '—')}
      ${stat('Rev Growth', d.revenue_growth != null ? `${d.revenue_growth.toFixed(1)}%` : '—')}
      ${stat('Gross Mgn',  d.gross_margin != null  ? `${d.gross_margin.toFixed(1)}%` : '—')}
      ${stat('EPS Trend',  d.eps_trend || '—')}
      ${stat('Sector',     d.sector || '—')}
    </div>`;

  // Breakdown sections
  const sections = [
    { key: 'multibagger',  label: '🚀 Multibagger Breakdown' },
    { key: 'investment',   label: '💼 Investment Breakdown' },
    { key: 'swing_medium', label: '📈 Swing 2-3 Week Breakdown' },
    { key: 'swing_short',  label: '⚡ Swing 2-3 Day Breakdown' },
  ].map(({ key, label }) => {
    const data = bd[key];
    if (!data || Object.keys(data).length === 0) return '';
    return `
      <div class="breakdown-section">
        <div class="breakdown-title">${label}</div>
        ${Object.entries(data).map(([name, info]) => breakdownRow(name, info)).join('')}
      </div>`;
  }).join('');

  // Red flags
  const flagsHtml = flags.length
    ? `<div class="breakdown-section">
         <div class="breakdown-title">⚠ Red Flags</div>
         <ul class="red-flags-list">${flags.map(f => `<li>${f}</li>`).join('')}</ul>
       </div>`
    : `<div style="color:var(--success);font-size:.83rem;margin-bottom:16px">✓ No red flags detected</div>`;

  return cards + stats + sections + flagsHtml;
}

function scoreCard(label, val, cls) {
  const v = val != null ? val.toFixed(0) : '—';
  const color = val != null ? scoreBarColor(val) : 'var(--text-muted)';
  return `
    <div class="score-card">
      <div class="score-card-label">${label}</div>
      <div class="score-card-value" style="color:${color}">${v}</div>
    </div>`;
}

function stat(label, val) {
  return `<div>
    <div style="color:var(--text-muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.4px">${label}</div>
    <div style="font-weight:600">${val}</div>
  </div>`;
}

function breakdownRow(name, info) {
  const pts    = info.pts ?? 0;
  const max    = info.max ?? 10;
  const val    = info.val ?? '';
  const pct    = max > 0 ? Math.max(0, (pts / max) * 100) : 0;
  const color  = scoreBarColor(pct);
  return `
    <div class="bd-row">
      <span class="bd-name">${name}</span>
      <span class="bd-val">${typeof val === 'boolean' ? (val ? 'Yes' : 'No') : val}</span>
      <div class="bd-bar"><div class="bd-bar-fill" style="width:${pct}%;background:${color}"></div></div>
      <span class="bd-pts" style="color:${color}">${pts > 0 ? '+' : ''}${pts}</span>
    </div>`;
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('open');
}

// ── Toast ────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg, duration = 3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), duration);
}

// ── Debounce ─────────────────────────────────────────────────
const _debounceMap = new Map();
function debounce(fn, ms) {
  return (...args) => {
    if (_debounceMap.has(fn)) clearTimeout(_debounceMap.get(fn));
    _debounceMap.set(fn, setTimeout(() => fn(...args), ms));
  };
}
