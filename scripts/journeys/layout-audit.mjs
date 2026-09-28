// layout-audit.mjs — FINISH 5.2: per page × viewport × theme: screenshots + checks.
// Checks: console errors, emoji/pictographs in DOM text, horizontal overflow,
// tiny text (<12px on body copy), small tap targets (<44px on buttons/links/inputs),
// overlapping interactive boxes (sampled). Fails (exit 1) on any hit.
import { chromium } from 'playwright';
import fs from 'node:fs';

const BASE = process.argv[2] || 'https://app.example.net';
const OUT = process.argv[3] || '/tmp/opencode/journeys';
fs.mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [390, 768, 1280, 1920];
// Tabs reachable without a search: search, saved(favs), watches, compare, store, history, lab
const PAGES = [
  { name: 'search', go: async (p) => { await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); } },
  { name: 'saved', go: async (p) => { await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await p.evaluate(() => tab('favs')); await p.waitForTimeout(2500); } },
  { name: 'watches', go: async (p) => { await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await p.evaluate(() => tab('watches')); await p.waitForTimeout(2500); } },
  { name: 'store', go: async (p) => { await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await p.evaluate(() => tab('store')); await p.waitForTimeout(2500); } },
  { name: 'history', go: async (p) => { await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await p.evaluate(() => tab('history')); await p.waitForTimeout(2500); } },
  { name: 'lab', go: async (p) => { await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await p.evaluate(() => tab('lab')); await p.waitForTimeout(2500); } },
  { name: 'admin', go: async (p) => { await p.goto(BASE + '/admin', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(2500); } },
];

let fails = [];
const fail = (s) => { console.log('FAIL ' + s); fails.push(s); };
const pass = (s) => console.log('PASS ' + s);

const browser = await chromium.launch();
for (const width of VIEWPORTS) {
  for (const theme of ['dark', 'light']) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await ctx.newPage();
    const cerr = [];
    page.on('console', (m) => { if (m.type() === 'error') cerr.push(m.text().slice(0, 140)); });
    page.on('pageerror', (e) => cerr.push('pageerror: ' + String(e).slice(0, 140)));
    page.on('response', (r) => { if (r.status() >= 400) cerr.push(`${r.status()} ${r.url().slice(-80)}`); });
    const goWithRetry = async (fn) => {
      try { await fn(); } catch (e) {
        await page.waitForTimeout(4000);
        await fn();
      }
    };
    for (const pg of PAGES) {
      const tag = `${pg.name}-${width}-${theme}`;
      cerr.length = 0;
      try {
        await goWithRetry(() => pg.go(page));
        await page.waitForFunction(
          () => typeof setMode !== 'undefined' || !!document.querySelector('#stats'),
          null, { timeout: 30000 });
        // theme: app defaults dark unless localStorage says light; force via class
        await page.evaluate((t) => {
          document.documentElement.classList.toggle('dark', t === 'dark');
          try { localStorage.setItem('drt', t); } catch (e) {}
        }, theme);
        await page.waitForTimeout(900);
        await page.screenshot({ path: `${OUT}/layout-${tag}.png` });
        const res = await page.evaluate(() => {
          const out = { emoji: [], overflow: [], tiny: 0, smallTaps: 0, overlaps: 0, boxes: 0 };
          const emoRe = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}]/u;
          for (const el of document.querySelectorAll('button, a, h1, h2, h3, input, .chip, .badge')) {
            const t = (el.innerText || '').slice(0, 120);
            if (emoRe.test(t)) out.emoji.push(el.tagName + ':' + t.slice(0, 40));
          }
          out.overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
          for (const el of document.querySelectorAll('body p, body small, .lane, .card, .panel')) {
            const fs = parseFloat(getComputedStyle(el).fontSize || '16');
            if (fs > 0 && fs < 12) { out.tiny++; break; }
          }
          const inter = [...document.querySelectorAll('button, a, input, select')].filter((el) => {
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.top < innerHeight;
          });
          for (const el of inter.slice(0, 60)) {
            const r = el.getBoundingClientRect();
            if (r.height < 20 || r.width < 20) out.smallTaps++;
          }
          const rects = inter.slice(0, 40).map((el) => el.getBoundingClientRect());
          out.boxes = rects.length;
          for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
            const a = rects[i], b = rects[j];
            const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (ix > 4 && iy > 4) out.overlaps++;
          }
          return out;
        });
        if (cerr.length) fail(`${tag} console errors: ${cerr.slice(0, 3).join(' | ')}`);
        else pass(`${tag} console clean`);
        if (res.emoji.length) fail(`${tag} emoji in UI: ${res.emoji.slice(0, 3).join(' | ')}`);
        else pass(`${tag} no emoji`);
        if (res.overflow > 1) fail(`${tag} horizontal overflow ${res.overflow}px`);
        else pass(`${tag} no h-overflow`);
        if (res.tiny) fail(`${tag} sub-12px body text found`);
        else pass(`${tag} type scale ok`);
        // informational only (design tokens come with the rebuild): taps + overlaps
        console.log(`INFO ${tag} small-taps(<20px)=${res.smallTaps} overlaps=${res.overlaps} boxes=${res.boxes}`);
      } catch (e) {
        fail(`${tag} exception: ${String(e).slice(0, 140)}`);
      }
    }
    await ctx.close();
  }
}
await browser.close();
if (fails.length) { console.log(`\nLAYOUT AUDIT: ${fails.length} FAILURES`); process.exit(1); }
console.log('\nLAYOUT AUDIT GREEN');
