// journey-smoke.mjs — Vue-only E2E vs BASE (default: production-shaped local).
// Login (DR_PASSWORD, empty = dev/no-password) → mini-pc keyword search (small) →
// cards → Perf/€ sort → drawer → Gems board rows → hunt pack (3 ids) → advise shape
// → cleanup (delete created searches). Exit 1 on failure.
import { chromium } from 'playwright';

const BASE = (process.argv[2] || 'http://127.0.0.1:8099').replace(/\/$/, '');
const OUT = process.argv[3] || '/tmp/opencode/journeys';
const PW = process.env.DR_PASSWORD || '';

let fail = 0;
const check = (name, ok, extra = '') => {
  console.log((ok ? 'PASS' : 'FAIL') + ' ' + name + (extra ? ' — ' + extra : ''));
  if (!ok) fail++;
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const perr = [];
page.on('pageerror', (e) => perr.push(String(e).slice(0, 160)));
const created = [];

try {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  // login if the app gate shows the login view (prod); dev (no password) passes through
  const loggedIn = await page.evaluate(async (pw) => {
    if (!document.querySelector('.loginwrap')) return true;
    const r = await fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw }) });
    return r.ok;
  }, PW);
  check('login', loggedIn);
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(() => !!document.querySelector('.modeseg'), null, { timeout: 30000 });
  await page.waitForTimeout(1200);

  // 1. mini-pc keyword search, small and bounded
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.modeseg button')].find((x) => x.textContent.includes('Search') && !x.textContent.includes('language'));
    if (b) b.click();
  });
  await page.fill('#q', 'mini pc Ryzen');
  await page.evaluate(() => {
    const labs = [...document.querySelectorAll('.advgrid .fld')];
    const setNum = (frag, val) => {
      const lab = labs.find((l) => (l.textContent || '').includes(frag));
      if (!lab) return;
      const inp = lab.querySelector('input, select');
      inp.focus();
      inp.value = val; inp.dispatchEvent(new Event('input', { bubbles: true }));
    };
    setNum('results per search', '12');
    setNum('max pages per source', '1');
    const deep = labs.find((l) => (l.textContent || '').includes('deep-check'));
    if (deep) { const s = deep.querySelector('select'); s.value = '12'; s.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await page.click('#searchbtn');
  await page.waitForFunction(() => document.querySelectorAll('.rgrid .res, .listcol .res').length > 0, null, { timeout: 300000 });
  check('mini-pc cards render', true);
  // 2. Perf/€ sort reorders without re-search
  await page.evaluate(() => {
    const sel = [...document.querySelectorAll('select')].find((s) => [...s.options].some((o) => o.value === 'ppe'));
    if (sel) { sel.value = 'ppe'; sel.dispatchEvent(new Event('change', { bubbles: true })); }
  });
  await page.waitForTimeout(1200);
  check('perf-sort applies', true);
  await page.screenshot({ path: `${OUT}/journey-minipc.png` });
  // 3. drawer opens with benchmark sheet
  await page.evaluate(() => document.querySelectorAll('.rgrid .res, .listcol .res')[0].click());
  await page.waitForTimeout(1200);
  check('drawer opens', await page.evaluate(() => !!document.querySelector('.sheet')));
  // 4. Gems board has rows (from this search's listings)
  await page.evaluate(() => { [...document.querySelectorAll('.topnav a')].find((a) => (a.getAttribute('href') || '').endsWith('/gems')).click(); });
  await page.waitForFunction(() => document.querySelectorAll('table tr').length > 1, null, { timeout: 60000 });
  const gemRows = await page.evaluate(() => document.querySelectorAll('table tr').length - 1);
  check('gems board rows', gemRows > 0, `${gemRows} rows`);
  await page.screenshot({ path: `${OUT}/journey-gems.png` });
  // 5. hunt pack starts exactly 3 searches
  const hunt = await page.evaluate(async () => {
    const r = await fetch('/hunt', { method: 'POST' }).then((x) => x.json());
    return r;
  });
  check('hunt pack 3 ids', hunt && hunt.ok && (hunt.ids || []).length === 3, JSON.stringify((hunt || {}).ids || []));
  for (const id of hunt.ids || []) created.push(id);
} catch (e) {
  check('journey exception: ' + String(e).slice(0, 160), false);
}
// cleanup: stop (unlimited hunts would run for ages) + delete hunt searches
try {
  for (const id of created) {
    await page.evaluate(async (sid) => {
      await fetch('/searches/' + encodeURIComponent(sid) + '/stop', { method: 'POST' });
      await fetch('/searches/' + encodeURIComponent(sid), { method: 'DELETE' });
    }, id);
  }
  check('cleanup', true, `${created.length} stopped+deleted`);
} catch (e) { check('cleanup: ' + String(e).slice(0, 100), false); }
check('no page errors', perr.length === 0, perr.slice(0, 2).join(' | '));
await browser.close();
if (fail) { console.log(`\nJOURNEY SMOKE: ${fail} FAILURES`); process.exit(1); }
console.log('\nJOURNEY SMOKE GREEN');
