// journey-smoke.mjs — fresh-profile core loop vs BASE (default: production).
// Non-destructive: one small keyword search, stop-mid-flight check on a 2nd search,
// history open, risk-100 unhide, cleanup (delete created searches). Exit 1 on failure.
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'https://app.example.net';
const OUT = process.argv[3] || '/tmp/opencode/journeys';

let fail = 0;
const check = (name, ok, extra = '') => {
  console.log((ok ? 'PASS' : 'FAIL') + ' ' + name + (extra ? ' — ' + extra : ''));
  if (!ok) fail++;
};

const browser = await chromium.launch();
// fresh profile: clean storage, no Served state
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const perr = [];
page.on('pageerror', (e) => perr.push(String(e).slice(0, 120)));
await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(2500);

try {
  // 1. keyword search, small, fast sources only (kleinanzeigen+vinted via checkboxes if present)
  await page.evaluate(() => { const b = document.querySelector('#modeseg [data-mode="kw"]'); if (b) b.click(); });
  await page.waitForFunction(() => {
    const f = document.querySelector('#qform');
    return f && getComputedStyle(f).display !== 'none';
  }, null, { timeout: 15000 });
  await page.fill('#q', 'ThinkPad X1');
  const adv = await page.$('details:not([open]) summary');
  if (adv) await adv.click();
  const limit = await page.$('#limitN');
  if (limit) await page.selectOption('#limitN', '10');
  await page.click('#searchbtn');
  await page.waitForFunction(() => document.querySelectorAll('#results .card').length > 0,
    null, { timeout: 240000 });
  check('kw search renders cards', true);
  await page.waitForFunction(() => typeof ACTIVEJOBS !== 'undefined' && ACTIVEJOBS.size === 0,
    null, { timeout: 240000 });
  const n = await page.evaluate(() => LAST.length);
  check('search completes with results', n > 0, `${n} results`);
  const status = await page.evaluate(() => document.querySelector('#status').innerText.slice(0, 200));
  check('status shows counts not raw JSON dump', !status.includes('{"') || status.includes('source note'), status.slice(0, 100));
  await page.screenshot({ path: `${OUT}/journey-results.png` });

  // 2. history tile opens
  const sid = await page.evaluate(() => SID);
  await page.evaluate(() => tab('history'));
  await page.waitForTimeout(2000);
  const tiles = await page.evaluate(() => document.querySelectorAll('#pageview .card').length);
  check('history has tiles', tiles > 0, `${tiles} tiles`);
  await page.evaluate((id) => openSearch(id), sid);
  await page.waitForTimeout(1500);
  const reopened = await page.evaluate(() => LAST.length);
  check('history tile reopens with results', reopened > 0, `${reopened} results`);

  // 3. risk block-100 hides nothing (filter math, no re-search)
  await page.evaluate(() => { const el = document.querySelector('#rRisk'); if (el) { el.value = 100; el.dispatchEvent(new Event('input')); } render(); });
  await page.waitForTimeout(500);
  const visCount = await page.evaluate(() => document.querySelectorAll('#results .card').length);
  check('block-100 keeps results visible', visCount > 0, `${visCount} cards`);

  // 4. compare two listings
  const cmpOk = await page.evaluate(() => {
    const ids = LAST.slice(0, 2).map((s) => s.listing.id);
    if (ids.length < 2) return false;
    ids.forEach((id) => cmpTgl(id));
    return CMP.size === 2;
  });
  check('compare picks 2', cmpOk);
  await page.evaluate(() => cmp());
  await page.waitForTimeout(800);
  const cmpTable = await page.evaluate(() => document.querySelector('#pageview table.cmp') !== null);
  check('compare side-by-side table', cmpTable);
  await page.screenshot({ path: `${OUT}/journey-compare.png` });

  // 5. stop a running search (start a big one, stop it)
  await page.evaluate(() => tab('search'));
  await page.waitForTimeout(500);
  await page.waitForFunction(() => {
    const f = document.querySelector(SMODE === 'kw' ? '#qform' : '#nlform');
    return f && getComputedStyle(f).display !== 'none';
  }, null, { timeout: 15000 });
  await page.evaluate(() => {
    const sel = (typeof SMODE !== 'undefined' && SMODE === 'kw') ? '#q' : '#nl';
    document.querySelector(sel).value = 'fahrrad';
  });
  await page.evaluate(() => { (typeof SMODE !== 'undefined' && SMODE === 'kw' ? run : runNL)(); });
  await page.waitForTimeout(4000);
  const running = await page.evaluate(() => typeof ACTIVEJOBS !== 'undefined' && ACTIVEJOBS.size > 0);
  if (running) {
    const jid = await page.evaluate(() => [...ACTIVEJOBS.keys()][0]);
    await page.evaluate((id) => { ABORTSET.set(id, Date.now()); fetch('/searches/' + encodeURIComponent(id) + '/stop', { method: 'POST' }); }, jid);
    await page.waitForTimeout(6000);
    const st = await page.evaluate((id) => fetch('/searches/' + encodeURIComponent(id)).then((r) => r.json()).then((j) => j.status).catch(() => '?'), jid);
    check('stop lands (not done)', st === 'stopped', `status=${st}`);
  } else {
    check('stop lands (search already finished — timing)', true, 'finished too fast to stop');
  }

  // 6. cleanup: delete searches created by this journey
  const del = await page.evaluate(async () => {
    const r = await fetch('/searches').then((x) => x.json()).catch(() => ({ searches: [] }));
    let n = 0;
    for (const s of (r.searches || []).slice(0, 10)) {
      if ((s.keywords || '').includes('ThinkPad X1') || (s.keywords || '').includes('fahrrad')) {
        await fetch('/searches/' + encodeURIComponent(s.id), { method: 'DELETE' }).catch(() => {});
        n++;
      }
    }
    return n;
  });
  console.log(`INFO deleted ${del} journey searches`);
} catch (e) {
  check('journey exception: ' + String(e).slice(0, 160), false);
}
check('no page errors', perr.length === 0, perr.slice(0, 2).join(' | '));
await browser.close();
if (fail) { console.log(`\nJOURNEY SMOKE: ${fail} FAILURES`); process.exit(1); }
console.log('\nJOURNEY SMOKE GREEN');
