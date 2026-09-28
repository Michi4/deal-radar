const SVG_O='<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';const P_CHECK='<path d="M20 6 9 17l-5-5"/>';const P_X='<path d="M18 6 6 18"/><path d="m6 6 12 12"/>';function ic(p){return SVG_O+p+'</svg>'};const IC_CHECK=ic(P_CHECK),IC_X=ic(P_X);
document.documentElement.classList.toggle('dark', (localStorage.getItem('drt') || 'dark') !== 'light');
document.getElementById('themebtn').onclick = () => {
  const r = document.documentElement;
  const dark = !r.classList.contains('dark');
  r.classList.toggle('dark', dark);
  localStorage.setItem('drt', dark ? 'dark' : 'light');
};
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const TABS = ['Overview', 'Drivers', 'Secrets', 'Searches', 'Events', 'Danger'];
let activeTab = 'Overview';
function drawTabs() {
  document.getElementById('tabs').innerHTML = TABS.map(t =>
    `<button class="tab ${t === activeTab ? 'on' : ''}" data-tab="${t}">${t}</button>`).join('');
  for (const t of TABS) {
    const el = document.getElementById('tab-' + t.toLowerCase());
    if (el) el.style.display = t === activeTab ? '' : 'none';
  }
  document.querySelectorAll('#tabs .tab').forEach(b =>
    b.addEventListener('click', () => { activeTab = b.dataset.tab; drawTabs(); }));
}
drawTabs();
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const txt = await res.text();
  let data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch (e) { throw new Error('bad response'); }
  if (!res.ok) throw new Error((data && data.error) || ('server ' + res.status));
  return data;
}
async function tick() {
  try {
    const m = await api('/metrics.json');
    try {
      const dd = await api('/drivers?include_disabled=1');
      m._allDrivers = dd;
    } catch (e) { m._allDrivers = null; }
    document.getElementById('updated').textContent = 'updated ' + new Date().toLocaleTimeString();
    const drv = m.drivers || {};
    const okN = Object.values(drv).filter(d => d.ok).length;
    const running = (m.watchlist || []).length;
    document.getElementById('stats').innerHTML = [
      [m.searches ?? 0, 'searches'], [m.events ?? 0, 'live events'],
      [okN + '/' + Object.keys(drv).length, 'drivers ok'], [running, 'watches/jobs'],
    ].map(([v, l]) => `<div class="card stat"><b>${v}</b><span>${l}</span></div>`).join('');
    const allD = m._allDrivers || [];
    const healthById = {};
    for (const [k, v] of Object.entries(drv)) healthById[k] = v;
    document.getElementById('drivers').innerHTML = '<table><tr><th>driver</th><th>state</th><th>failures</th><th>last error</th><th></th></tr>' +
      allD.map(x => { const h = healthById[x.id] || {}; const dis = !!x.disabled;
        return `<tr><td>${esc(x.display_name || x.id)}${dis ? ' <small>(disabled)</small>' : ''}${x.configured === false ? ' <small>(needs setup)</small>' : ''}</td><td>${dis ? '—' : (h.ok ? IC_CHECK : IC_X)}</td>` +
        `<td>${h.consecutive_failures ?? 0}</td><td>${esc((h.last_error || '').slice(0, 100))}</td>` +
        `<td><button class="btn btn-ghost" data-drv="${esc(x.id)}">${dis ? 'enable' : 'disable'}</button></td></tr>`; }).join('') + '</table>';
    document.querySelectorAll('#drivers [data-drv]').forEach(b => b.addEventListener('click', async () => {
      const id = b.dataset.drv;
      const dis = b.textContent.trim() === 'disable';
      try {
        if (dis) await api('/marketplace/' + encodeURIComponent(id), { method: 'DELETE' });
        else await api('/marketplace/install', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
        tick();
      } catch (e) { showMsg(String(e.message || e)); }
    }));
    const m2 = m.metrics || {};
    document.getElementById('metrics').innerHTML = '<table>' +
      Object.entries(m2.counters || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('') +
      Object.entries(m2.latency_avg_ms || {}).map(([k, v]) => `<tr><td>latency ${esc(k)}</td><td>${esc(v)} ms</td></tr>`).join('') + '</table>';
    document.getElementById('searches').innerHTML = '<table><tr><th>keywords</th><th>results</th><th>sources</th><th></th></tr>' +
      (m.watchlist || []).map(s => `<tr><td>${esc(s.keywords)}</td><td>${s.results ?? '?'}</td><td>${esc((s.sources || []).join(','))}</td><td><button class="btn btn-ghost" data-act="rerun" data-id="${esc(s.id)}">re-run</button> <button class="btn btn-ghost" data-act="watchit" data-id="${esc(s.id)}">watch</button> <button class="btn btn-ghost" data-act="del" data-id="${esc(s.id)}">delete</button></td></tr>`).join('') + '</table>';
    document.querySelectorAll('#searches [data-act]').forEach(b => b.addEventListener('click', async () => {
      const id = b.dataset.id, act = b.dataset.act;
      try {
        if (act === 'del') await api('/searches/' + encodeURIComponent(id), { method: 'DELETE' });
        else if (act === 'watchit') await api('/searches/' + encodeURIComponent(id) + '/watch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        else await api('/searches/' + encodeURIComponent(id) + '/redo', { method: 'POST' });
        tick();
      } catch (e) { showMsg(String(e.message || e)); }
    }));
    document.getElementById('nsearch').textContent = (m.watchlist || []).length;
    document.getElementById('evclear').innerHTML = `<button class="btn btn-ghost" id="evclearbtn">clear events</button>`;
    const _eb = document.getElementById('evclearbtn');
    if (_eb) _eb.addEventListener('click', async () => { try { await api('/events', { method: 'DELETE' }); tick(); } catch (e) { showMsg(String(e.message || e)); } });
    document.getElementById('events').innerHTML = (m.events_tail || []).slice().reverse()
      .map(e => `<div class="ev">${esc(e.kind || '?')}: ${esc((e.title || e.listing_id || '').slice(0, 100))}</div>`).join('') || 'none yet';
    document.getElementById('nev').textContent = m.events || 0;
  } catch (e) {
    document.getElementById('updated').textContent = 'unreachable — retrying…';
  }
}
function showMsg(t) {
  document.getElementById('secmsg').innerHTML = t ? `<div class="err">${esc(t)}</div>` : '';
}
async function loadSecrets() {
  try {
    const d = await api('/settings/secrets');
    document.getElementById('secrets').innerHTML = d.secrets.map(s =>
      `<div class="secrow"><div class="meta"><b>${esc(s.label)}</b><small>${esc(s.key)} · ` +
      `<span class="dot ${s.configured ? '' : 'off'}"></span>${s.configured ? 'set' : 'not set'}</small></div>` +
      `<input class="inp secinput" id="sec-${esc(s.key)}" type="${s.secret ? 'password' : 'text'}" ` +
      `placeholder="${s.configured ? '•••••• (type to replace)' : 'empty'}" autocomplete="off" aria-label="${esc(s.label)}"/>` +
      `<button class="btn btn-primary" data-save="${esc(s.key)}">save</button>` +
      (s.configured ? `<button class="btn btn-ghost" data-clear="${esc(s.key)}">clear</button>` : '') +
      `</div>`).join('');
    document.querySelectorAll('#secrets [data-save]').forEach(b => b.addEventListener('click', async () => {
      const k = b.dataset.save;
      const inp = document.getElementById('sec-' + CSS.escape(k));
      try {
        await api('/settings/secrets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: k, value: inp.value }) });
        inp.value = '';
        showMsg('');
        loadSecrets();
        tick();
      } catch (e) { showMsg(String(e.message || e)); }
    }));
    document.querySelectorAll('#secrets [data-clear]').forEach(b => b.addEventListener('click', async () => {
      try {
        await api('/settings/secrets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: b.dataset.clear, value: '' }) });
        loadSecrets();
        tick();
      } catch (e) { showMsg(String(e.message || e)); }
    }));
  } catch (e) { showMsg(String(e.message || e)); }
}
const _rb = document.getElementById('resetarm');
if (_rb) _rb.addEventListener('click', async () => {
  if (!_rb.dataset.armed) {
    _rb.dataset.armed = '1'; _rb.textContent = 'click again to confirm WIPE';
    setTimeout(() => { if (_rb.isConnected) { delete _rb.dataset.armed; _rb.textContent = 'wipe all data…'; } }, 10000);
    return;
  }
  try {
    const r = await api('/admin/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: 'RESET' }) });
    document.getElementById('resetmsg').innerHTML = `<div class="err">wiped: ${esc(JSON.stringify(r.wiped || {}))}</div>`;
    tick();
  } catch (e) { showMsg(String(e.message || e)); }
});
setInterval(tick, 15000);
tick();
loadSecrets();
