import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const browser = await chromium.launch();
const page = await browser.newPage();
let fail = 0;
const check = (name, ok) => { console.log((ok ? 'PASS' : 'FAIL') + ' ' + name); if (!ok) fail++; };
const errs = [];
page.on('pageerror', e => errs.push(String(e).slice(0, 100)));

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
check('index loads', await page.locator('#q').count() === 1);
check('sources listed', (await page.locator('#sources input').count()) >= 2);

await page.fill('#q', 'ThinkPad');
await page.click('#searchbtn');
await page.waitForFunction(() => document.querySelectorAll('#results .card').length > 0, null, { timeout: 300000 });
const n = await page.locator('#results .card').count();
check(`keyword search renders cards (n=${n})`, n > 0);

// drawer + version history
await page.click('#results .card');
await page.waitForSelector('#drawer.open', { timeout: 15000 });
await page.waitForFunction(() => document.querySelector('#vhist').textContent.length > 5, null, { timeout: 15000 });
check('drawer + version history', true);
await page.click('#drawer .scrim');

await page.goto(BASE + '/admin', { waitUntil: 'networkidle' });
await page.waitForFunction(() => document.querySelectorAll('#drivers td').length > 0, null, { timeout: 30000 });
check('admin shows drivers', true);

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
// tabs: history, store, lab, watches
await page.getByRole('button', { name: 'Searches' }).click();
await page.waitForFunction(() => document.querySelector('#results').textContent.length > 20, null, { timeout: 30000 });
check('searches dashboard renders', true);
await page.getByRole('button', { name: 'Store' }).click();
await page.waitForFunction(() => document.querySelector('#results').textContent.includes('Willhaben'), null, { timeout: 30000 });
check('store lists drivers', true);
await page.getByRole('button', { name: 'Lab' }).click();
await page.waitForFunction(() => document.querySelector('#results').textContent.includes('AI Lab'), null, { timeout: 30000 });
check('lab tab renders', true);

const m = await (await fetch(BASE + '/metrics.json')).json();
check('metrics.json has drivers', Object.keys(m.drivers || {}).length >= 2);
check('no JS errors', errs.length === 0);
if (errs.length) console.log(errs);

await browser.close();
process.exit(fail ? 1 : 0);
