import { chromium } from 'playwright';

// Proves keyword + NL searches run truly in parallel and both complete.
const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
let fail = 0;
const check = (name, ok) => { console.log((ok ? 'PASS' : 'FAIL') + ' ' + name); if (!ok) fail++; };
const errs = [];
page.on('pageerror', e => errs.push(String(e).slice(0, 100)));

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
await page.click('details summary');
try { await page.waitForSelector('#limitN:visible', { timeout: 5000 }); }
catch (e) { await page.click('details summary'); await page.waitForSelector('#limitN:visible', { timeout: 5000 }); }
await page.selectOption('#limitN', '50');
await page.fill('#deepN', '5');

// start keyword search (don't await completion)
await page.fill('#q', 'ThinkPad');
await page.click('#searchbtn');
await page.waitForTimeout(1500);
// start NL search while the first is running
await page.fill('#nl', 'iphone with usb-c charging');
await page.click('#askbtn');
await page.waitForTimeout(3000);
const active = await page.evaluate(() => ACTIVEJOBS.size);
check(`two searches active at once (n=${active})`, active >= 2);

// both must complete with results (whichever finishes last drives the view)
await page.waitForFunction(() => ACTIVEJOBS.size === 0, null, { timeout: 540000 });
const done = await page.evaluate(() => ({ cards: document.querySelectorAll('#results .card').length, followed: FOLLOWED }));
check(`both finished, view shows results (cards=${done.cards})`, done.cards > 0 && !!done.followed);
check('no JS errors', errs.length === 0);
if (errs.length) console.log(errs);
await browser.close();
process.exit(fail ? 1 : 0);
