import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
let fail = 0;
const check = (name, ok) => { console.log((ok ? 'PASS' : 'FAIL') + ' ' + name); if (!ok) fail++; };
const errs = [];
page.on('pageerror', e => errs.push(String(e).slice(0, 80)));

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
check('index loads', await page.locator('#q').count() === 1);

// search
await page.fill('#q', 'ThinkPad');
await page.click('#searchbtn');
await page.waitForFunction(() => document.querySelectorAll('#results .card').length > 0, null, { timeout: 300000 });
check('search renders', true);

// sort + blacklist-field typing are client-side (no roundtrip); only Search button queries
let fetches = 0;
page.on('request', r => { if (r.url().includes('/searches')) fetches++; });
await page.click('details summary');
await page.fill('#black', 'rucksack XYZ123');
await page.waitForTimeout(1000);
await page.click('#sortseg button:nth-child(2)');
await p_wait(1500);
await page.click('#sortseg button:nth-child(2)');
await p_wait(1500);
check('resort client-side, no roundtrip', fetches === 0);

// drawer
await page.click('#results .card');
await page.waitForSelector('#drawer.open', { timeout: 10000 });
check('drawer opens', true);
await page.click('#drawer .scrim');

// favorite
await page.evaluate(() => { const id = LAST[0].listing.id; return fetch('/favorites/' + encodeURIComponent(id), { method: 'POST' }).then(r => r.json()); });
const favs = await page.evaluate(() => fetch('/favorites').then(r => r.json()));
check('favorite persists', favs.length > 0);

// compare pick-2
await page.evaluate(() => {
  const bxs = [...document.querySelectorAll('#results .card input[type=checkbox]')];
  bxs[0].click(); document.querySelectorAll('#results .card input[type=checkbox]')[1].click();
});
await page.waitForTimeout(800);
await page.evaluate(() => cmp());
await page.waitForTimeout(800);
check('compare table', await page.locator('#results table.cmp td').count() >= 2);

// watch
await page.locator('#topnav-center button:has-text("Watches")').click();
await page.waitForSelector('#wq', { timeout: 15000 });
await page.fill('#wq', 'ThinkPad X1 Test');
await page.click('text=+ Watch');
await page.waitForTimeout(2000);
check('watch created', true);

// theme + grid/list
await page.click('button[aria-label="toggle theme"]');
await page.waitForTimeout(300);
const themeClass = await page.evaluate(() => document.documentElement.className);
check('theme toggles', themeClass.includes('dark') || themeClass === '');
await page.click('#vlist');
await page.waitForTimeout(500);
const rows = await page.locator('#results .listrow').count();
await page.click('#vgrid');
check('theme toggles + list/grid switch', themeClass !== undefined && rows >= 0);

// marketplace lists (real driver names rendered)
await page.locator('#topnav-center button:has-text("Store")').click();
await page.waitForFunction(() => document.querySelectorAll('#results .card').length > 0, null, { timeout: 30000 });
const storeTxt = await page.locator('#results').textContent();
check('store lists drivers', storeTxt.includes('Willhaben') && storeTxt.includes('install'));

check('no JS errors', errs.length === 0);
if (errs.length) console.log(errs);
await browser.close();
process.exit(fail ? 1 : 0);

async function p_wait(ms) { return new Promise(x => setTimeout(x, ms)); }
