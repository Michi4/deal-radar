import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const browser = await chromium.launch();
const page = await browser.newPage();
let fail = 0;
const check = (name, ok) => { console.log((ok ? 'PASS' : 'FAIL') + ' ' + name); if (!ok) fail++; };

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
check('index loads', await page.locator('#q').count() === 1);
check('sources listed', (await page.locator('#sources input').count()) >= 2);

await page.fill('#q', 'ThinkPad');
await page.click('#searchbtn');
await page.waitForFunction(() => document.querySelectorAll('#results .card').length > 0, null, { timeout: 90000 });
const n = await page.locator('#results .card').count();
check(`keyword search renders cards (n=${n})`, n > 0);

await page.goto(BASE + '/admin', { waitUntil: 'networkidle' });
await page.waitForFunction(() => document.querySelectorAll('#drivers td').length > 0, null, { timeout: 30000 });
check('admin shows drivers', true);

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
await page.click('text=🏪 Market');
await page.waitForFunction(() => document.querySelector('#results').textContent.length > 20, null, { timeout: 30000 });
check('market tab renders', true);

const m = await (await fetch(BASE + '/metrics.json')).json();
check('metrics.json has drivers', Object.keys(m.drivers || {}).length >= 2);

await browser.close();
process.exit(fail ? 1 : 0);

