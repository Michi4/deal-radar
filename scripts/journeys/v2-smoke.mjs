// v2-smoke.mjs — Vue rebuild core loop vs BASE/v2 (default: local preview).
// Fresh profile: kw search → cards → compare table → drawer → saved badge. Exit 1 on failure.
import { chromium } from 'playwright';

const BASE = (process.argv[2] || 'http://127.0.0.1:8128/v2').replace(/\/$/, '');
const OUT = process.argv[3] || '/tmp/opencode/journeys';

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
await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForFunction(() => !!document.querySelector('.modeseg'), null, { timeout: 30000 });
await page.waitForTimeout(1500);

try {
  const kwBtn = await page.evaluate(() => {
    const b = [...document.querySelectorAll('.modeseg button')].find((x) => x.textContent.includes('Search') && !x.textContent.includes('language'));
    if (b) b.click();
    return !!b;
  });
  check('v2 kw mode', kwBtn);
  await page.fill('#q', 'ThinkPad X1');
  await page.click('#searchbtn');
  await page.waitForFunction(() => document.querySelectorAll('.rgrid .res').length > 0, null, { timeout: 240000 });
  check('v2 cards render', true);
  await page.waitForFunction(() => !!document.querySelector('.statusline'), null, { timeout: 120000 });
  const st = await page.evaluate(() => document.querySelector('.statusline').innerText.slice(0, 140));
  check('v2 status counts', /\d+ results/.test(st), st.slice(0, 80));
  await page.screenshot({ path: `${OUT}/v2-results.png` });

  // worker filtering: blacklist a ubiquitous word → list empties without re-search
  const before = await page.evaluate(() => document.querySelectorAll('.rgrid .res').length);
  await page.evaluate(() => {
    const labs = [...document.querySelectorAll('.refine .fld')];
    const inp = labs.find((l) => (l.textContent || '').includes('hide if')).querySelector('input');
    inp.focus(); inp.value = 'thinkpad';
    inp.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.waitForTimeout(1500);
  const after = await page.evaluate(() => document.querySelectorAll('.rgrid .res').length);
  check('v2 worker refilter live', before > 0 && after < before, `${before} → ${after}`);
  await page.evaluate(() => {
    const labs = [...document.querySelectorAll('.refine .fld')];
    const inp = labs.find((l) => (l.textContent || '').includes('hide if')).querySelector('input');
    inp.focus(); inp.value = '';
    inp.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.waitForTimeout(1500);

  // compare two via in-app nav
  await page.evaluate(() => {
    [...document.querySelectorAll('.rgrid .res .row .btn')].filter((b) => b.textContent.includes('compare')).slice(0, 2).forEach((b) => b.click());
  });
  await page.waitForTimeout(600);
  await page.evaluate(() => { [...document.querySelectorAll('.topnav a')].find((a) => a.getAttribute('href').endsWith('/compare')).click(); });
  await page.waitForTimeout(1000);
  check('v2 compare table', await page.evaluate(() => !!document.querySelector('table.cmp')));

  // drawer via in-app nav back
  const backDbg = await page.evaluate(() => ({
    n: document.querySelectorAll('.topnav a').length,
    hrefs: [...document.querySelectorAll('.topnav a')].map((a) => a.getAttribute('href')).join(','),
    url: location.href
  }));
  console.log('INFO backnav: ' + JSON.stringify(backDbg));
  await page.evaluate(() => { const a = document.querySelector('.topnav a[href="/v2/"]'); if (a) a.click(); });
  await page.waitForTimeout(1500);
  await page.evaluate(() => document.querySelector('.rgrid .res').click());
  await page.waitForTimeout(1200);
  check('v2 drawer opens', await page.evaluate(() => !!document.querySelector('.sheet')));
  const title = await page.evaluate(() => (document.querySelector('.sheet h2') || { innerText: '' }).innerText.slice(0, 50));
  check('v2 drawer has title', title.length > 3, title);

  // views render without errors
  for (const v of ['saved', 'watches', 'store', 'history', 'lab']) {
    await page.evaluate((vv) => { [...document.querySelectorAll('.topnav a')].find((a) => a.getAttribute('href').endsWith('/' + vv)).click(); }, v);
    await page.waitForTimeout(1200);
  }
  check('v2 views navigate', true);
  await page.screenshot({ path: `${OUT}/v2-views.png` });
} catch (e) {
  check('v2 journey exception: ' + String(e).slice(0, 160), false);
}
check('v2 no page errors', perr.length === 0, perr.slice(0, 2).join(' | '));
await browser.close();
if (fail) { console.log(`\nV2 SMOKE: ${fail} FAILURES`); process.exit(1); }
console.log('\nV2 SMOKE GREEN');
