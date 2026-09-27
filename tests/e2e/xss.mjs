import { chromium } from 'playwright';

// Stored-XSS regression: malicious listing fields must render inert.
const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const browser = await chromium.launch();
const page = await browser.newPage();
let fail = 0;
const check = (name, ok) => { console.log((ok ? 'PASS' : 'FAIL') + ' ' + name); if (!ok) fail++; };
const errs = [];
page.on('pageerror', e => errs.push(String(e).slice(0, 120)));

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
const evil = {
  listing: {
    id: 'x1"><img src=x onerror=window.__xss=1>',
    title: '<img src=x onerror=window.__xss=1>ThinkPad',
    price: 100, currency: 'EUR', source: '<b>evil</b>',
    location: '"><svg onload=window.__xss=1>',
    url: 'javascript:window.__xss=1',
    images: ['javascript:window.__xss=1', 'https://example.com/a.jpg'],
    description: '<script>window.__xss=1</script>nice laptop',
  },
  lane: 'top', final_score: 0.9, why: ['<img src=x onerror=window.__xss=1>'],
  risk: { score: 0.1, severity: 'low', reasons: ['<svg onload=window.__xss=1>'], counter_evidence: [] },
  deal_dna: {}, enrichments: [{ field: '<b>f</b>', value: '<i>v</i>', confidence: 0.5, status: '<u>s</u>' }],
};
await page.evaluate((ev) => {
  window.__xss = 0;
  LAST = [ev]; SEARCHED = true; SID = 't'; PAGE = 0; PERPAGE = 20;
  render();
  openD(ev.listing.id);
}, evil);
await page.waitForTimeout(800);
const fired = await page.evaluate(() => window.__xss);
check('no script executes from evil fields', fired === 0);
const body = await page.evaluate(() => document.getElementById('results').innerHTML + document.getElementById('sheet').innerHTML);
check('title escaped', body.includes('&lt;img') && !body.includes('<img src=x onerror'));
check('javascript: url neutralized', !body.includes('javascript:window'));
check('no page errors', errs.length === 0);
if (errs.length) console.log(errs);
await browser.close();
process.exit(fail ? 1 : 0);
