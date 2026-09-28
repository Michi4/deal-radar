<template>
  <div class="searchpage">
    <div class="panel searchpanel">
      <div class="modeseg" role="tablist" aria-label="search mode">
        <button role="tab" :class="{ active: ui.mode === 'nl' }" @click="ui.setMode('nl')" title="Describe what you want in plain words — a real model resolves it to products, filters and categories">
          <Sparkles :size="15" /> Natural language search
        </button>
        <button role="tab" :class="{ active: ui.mode === 'kw' }" @click="ui.setMode('kw')" title="Classic keywords with per-field filters you control directly">
          <Keyboard :size="15" /> Search
        </button>
      </div>

      <form v-if="ui.mode === 'nl'" @submit.prevent="runNL" class="row">
        <input v-model="nlText" class="inp grow" placeholder="Describe what you want…" aria-label="natural language query" />
        <button class="btn btn-primary" type="submit" :disabled="busy">Ask</button>
      </form>
      <form v-else @submit.prevent="runKw" class="row">
        <input v-model="kwText" id="q" class="inp grow" placeholder="Keywords (e.g. ThinkPad X1)" aria-label="keywords" />
        <button class="btn btn-primary" type="submit" :disabled="busy" id="searchbtn">Search</button>
      </form>

      <div v-if="nlApplied" class="applied">
        <div class="eyebrow">AI understood</div>
        <div class="ai-kw">{{ nlApplied.keywords }}</div>
        <div class="chips">
          <span v-for="m in nlApplied.models || []" :key="m" class="chip">{{ m }}</span>
          <span v-if="nlApplied.category" class="chip">category: {{ nlApplied.category }}</span>
        </div>
        <small>Filtered automatically — adjust in advanced and re-run, or refine below without re-search.</small>
      </div>

      <details class="adv">
        <summary>advanced <span v-if="filtersActive" class="dot" title="filters active"></span></summary>
        <div class="advgrid">
          <label class="fld"><span title="Words that must NOT appear in title/description">hide if contains</span><input v-model="f.black" class="inp" placeholder="comma, separated" /></label>
          <label class="fld"><span title="Words that MUST appear">must contain</span><input v-model="f.req" class="inp" placeholder="comma, separated" /></label>
          <label class="fld"><span title="Minimum price in EUR">min €</span><input v-model="f.min" class="inp" type="number" /></label>
          <label class="fld"><span title="Maximum price in EUR">max €</span><input v-model="f.max" class="inp" type="number" /></label>
          <label class="fld"><span title="Hide listings above this scam-risk % (100 = block nothing)">max risk % (100 = block nothing)</span><input v-model.number="f.blockT" class="inp" type="number" min="0" max="100" /></label>
          <label class="fld"><span title="Only show listings scoring above this %">min score %</span><input v-model.number="scoreMin" class="inp" type="number" min="0" max="100" /></label>
          <label class="fld"><span title="Pickup possible">pickup possible</span><input v-model="f.fPick" type="checkbox" /></label>
          <label class="fld"><span title="Shipping possible">shipping possible</span><input v-model="f.fShip" type="checkbox" /></label>
          <label class="fld"><span title="Your location (text or browser)">location</span><input v-model="f.locQ" class="inp" /></label>
          <label class="fld"><span title="Search radius in km (empty = unlimited)">radius km</span><input v-model="f.locR" class="inp" type="number" /></label>
          <label class="fld"><span>category (willhaben)</span><select v-model="f.catSel" class="inp"><option value="">any</option><option v-for="c in cats.wh" :key="c.id" :value="c.id">{{ c.label }}</option></select></label>
          <label class="fld"><span>category (kleinanzeigen)</span><select v-model="f.catKa" class="inp"><option value="">any</option><option v-for="c in cats.ka" :key="c.id" :value="c.id">{{ c.label }}</option></select></label>
          <label class="fld"><span>sources</span>
            <span class="srcs">
              <label v-for="s in allSources" :key="s" class="ck" :class="{ on: srcOn(s) }"><input type="checkbox" :checked="srcOn(s)" @change="toggleSrc(s)" /> {{ s }}</label>
            </span>
          </label>
          <label class="fld"><span title="Max results per search (empty = unlimited)">results per search</span><input v-model="f.limitN" class="inp" type="number" /></label>
          <label class="fld"><span title="Max pages per source (empty = walk to exhaustion)">max pages per source</span><input v-model="f.maxpages" class="inp" type="number" /></label>
        </div>
        <div class="row">
          <button class="btn" @click="resetFilters" title="Reset every filter to defaults">reset filters</button>
        </div>
      </details>

      <div v-if="history.length" class="histrow" aria-label="recent queries">
        <span class="eyebrow">history</span>
        <button v-for="h in history" :key="h" class="chip" @click="rerunHistory(h)" :title="'re-run: ' + h">{{ h.slice(0, 30) }}</button>
      </div>
    </div>

    <div v-if="search.searched" class="toolbar" id="toolbar">
      <label title="Sort key (asc/desc per key)">sort
        <select v-model="search.sort" class="inp">
          <option value="score">Score</option><option value="price">Price</option>
          <option value="ppe">Perf/€</option><option value="mt">Multithread</option>
          <option value="dist">Distance</option><option value="tc">Total cost</option>
        </select>
      </label>
      <button class="btn iconbtn" @click="search.sortDir *= -1; refilter()" :title="search.sortDir === 1 ? 'ascending' : 'descending'" aria-label="toggle sort direction">
        <ArrowDown v-if="sortDown" :size="16" /><ArrowUp v-else :size="16" />
      </button>
      <label>per page
        <select v-model.number="search.perPage" class="inp" @change="search.page = 0">
          <option :value="20">20</option><option :value="50">50</option><option :value="100">100</option><option :value="500">500</option>
        </select>
      </label>
      <button class="btn iconbtn" @click="ui.setView('grid')" :class="{ active: ui.view === 'grid' }" aria-label="grid view" title="Grid view"><LayoutGrid :size="16" /></button>
      <button class="btn iconbtn" @click="ui.setView('list')" :class="{ active: ui.view === 'list' }" aria-label="list view" title="List view"><List :size="16" /></button>
      <span class="lane">{{ visibleIds.length }} items</span>
    </div>

    <div v-if="search.searched" class="panel refine">
      <div class="eyebrow">Filter loaded results · no re-search · everything re-adjustable</div>
      <div class="advgrid">
        <label class="fld"><span>hide if contains</span><input v-model="f.black" class="inp" @input="refilter" /></label>
        <label class="fld"><span>must contain</span><input v-model="f.req" class="inp" @input="refilter" /></label>
        <label class="fld"><span>max risk % ({{ search.maxRisk }})</span><input v-model.number="search.maxRisk" type="range" min="0" max="100" @input="refilter" /></label>
        <label class="fld"><span>min score % ({{ search.minScore }})</span><input v-model.number="search.minScore" type="range" min="0" max="100" @input="refilter" /></label>
      </div>
      <div class="row kinds">
        <button v-for="k in kindKeys" :key="k" :class="{ active: search.hideKind[k] }" @click="toggleKind(k)" :title="kindTip(k)">{{ kindLabel(k) }}</button>
        <label class="ck" :class="{ on: search.showHidden }"><input type="checkbox" v-model="search.showHidden" /> show hidden ({{ search.hidden.length }})</label>
      </div>
    </div>

    <div v-if="statusLine" class="panel statusline"><small>{{ statusLine }}</small></div>

    <Pager v-if="pages > 1" :page="search.page" :pages="pages" @go="goPage" />
    <div v-if="search.searched && !busy && !visibleIds.length" class="empty">
      No results. Try fewer filters or another query.
      <span v-if="driverNotes">{{ driverNotes }}</span>
    </div>
    <div v-if="ui.view === 'grid'" class="rgrid">
      <JobTile v-for="[id, job] in search.jobs" :key="'j' + id" :job="job"
        @open="openJob(id)" @pause="search.jobOp(id, 'pause')" @resume="search.jobOp(id, 'resume')" @stop="search.jobOp(id, 'stop')" />
      <ResultCard v-for="(s, i) in pageItems" :key="s.listing.id" :s="s" :best="i === 0 && isValueSort"
        :picked="search.compare.has(s.listing.id)" :is-fav="search.favs.has(s.listing.id)"
        @compare="search.toggleCompare(s.listing.id)" @fav="search.toggleFav(s.listing.id)" @click="openDrawer(s.listing.id)" />
    </div>
    <div v-else class="listcol">
      <JobTile v-for="[id, job] in search.jobs" :key="'j' + id" :job="job"
        @open="openJob(id)" @pause="search.jobOp(id, 'pause')" @resume="search.jobOp(id, 'resume')" @stop="search.jobOp(id, 'stop')" />
      <ResultCard v-for="(s, i) in pageItems" :key="s.listing.id" :s="s" :best="i === 0 && isValueSort"
        :picked="search.compare.has(s.listing.id)" :is-fav="search.favs.has(s.listing.id)"
        @compare="search.toggleCompare(s.listing.id)" @fav="search.toggleFav(s.listing.id)" @click="openDrawer(s.listing.id)" />
    </div>
    <Pager v-if="pages > 1" :page="search.page" :pages="pages" @go="goPage" />

    <Drawer v-if="drawerId" :id="drawerId" @close="drawerId = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ArrowDown, ArrowUp, Keyboard, LayoutGrid, List, Sparkles } from 'lucide-vue-next';
import { api } from '@/api';
import { useSearch } from '@/stores/search';
import { useUi } from '@/stores/ui';
import type { Category, Scored, SearchResult } from '@/types';
import ResultCard from '@/components/ResultCard.vue';
import JobTile from '@/components/JobTile.vue';
import Pager from '@/components/Pager.vue';
import Drawer from '@/components/Drawer.vue';

const search = useSearch();
const ui = useUi();
const route = useRoute();
const kwText = ref('');
const nlText = ref('');
const busy = ref(false);
const drawerId = ref<string | null>(null);
const allSources = ref<string[]>([]);
const cats = reactive<{ wh: Category[]; ka: Category[] }>({ wh: [], ka: [] });
const history = ref<string[]>(JSON.parse(localStorage.getItem('drh') || '[]'));
const nlApplied = ref<{ keywords: string; models?: string[]; blacklist?: string[]; required?: string[]; category?: string; subs?: string[] } | null>(null);
const statusLine = ref('');
const driverNotes = ref('');
const visibleIds = ref<string[]>([]);
const byId = ref(new Map<string, Scored>());
const scoreMin = computed({ get: () => search.minScore, set: (v: number) => { search.minScore = v; refilter(); } });
const f = search.filters;

let worker: Worker | null = null;
try {
  worker = new Worker(new URL('../workers/filter.ts', import.meta.url), { type: 'module' });
  worker.onmessage = (e: MessageEvent<{ ids: string[] }>) => { visibleIds.value = e.data.ids; };
} catch { worker = null; }

const isValueSort = computed(() => search.sort === 'ppe');
const sortDown = computed(() => {
  const descDefault = search.sort === 'score' || search.sort === 'ppe' || search.sort === 'mt';
  return (descDefault ? -1 : 1) * search.sortDir === 1;
});
const pages = computed(() => Math.max(1, Math.ceil(visibleIds.value.length / search.perPage)));
const pageItems = computed(() => {
  const arr = visibleIds.value.map((id) => byId.value.get(id)).filter(Boolean) as Scored[];
  return arr.slice(search.page * search.perPage, search.page * search.perPage + search.perPage);
});
const kindKeys = ['want', 'parts', 'acc'];
const kindLabel = (k: string) => ({ want: 'Gesuche', parts: 'parts', acc: 'accessories' }[k] || k);
const kindTip = (k: string) => ({ want: 'Hide wanted/buy-request ads (kept, unhide anytime)', parts: 'Hide parts/repair-only listings', acc: 'Hide accessories/empty boxes/cases' }[k] || k);
const filtersActive = computed(() => !!(f.min || f.max || f.black || f.req || f.blockT < 100));
const srcOn = (s: string) => search.sources.has(s);

function toggleSrc(s: string) {
  if (search.sources.has(s)) search.sources.delete(s);
  else search.sources.add(s);
}
function toggleKind(k: string) { search.hideKind[k] = !search.hideKind[k]; refilter(); }
function resetFilters() { Object.assign(search.filters, { min: '', max: '', black: '', req: '', minMatch: 12, warnT: 35, blockT: 100 }); search.maxRisk = 100; search.minScore = 0; search.maxDist = null; refilter(); }
function pushHist(q: string) {
  history.value = [q, ...history.value.filter((x) => x !== q)].slice(0, 8);
  localStorage.setItem('drh', JSON.stringify(history.value));
}
function rerunHistory(h: string) {
  if (ui.mode === 'kw') { kwText.value = h; runKw(); }
  else { nlText.value = h; runNL(); }
}

function refilter() {
  const items = [...search.results];
  byId.value = new Map(items.map((s) => [s.listing.id, s]));
  const payload = {
    items: items.map((s) => ({
      listing: { id: s.listing.id, title: s.listing.title, description: s.listing.description, price: s.listing.price, source: s.listing.source, distance_km: s.listing.distance_km },
      risk: s.risk, final_score: s.final_score, lane: s.lane, why: s.why, deal_dna: s.deal_dna, enrichments: s.enrichments
    })),
    opts: {
      hideKind: { ...search.hideKind }, hideLanes: [...search.hideLanes],
      maxRisk: search.maxRisk, minScore: search.minScore, maxDist: search.maxDist,
      min: f.min === '' ? null : +f.min, max: f.max === '' ? null : +f.max,
      black: f.black.split(',').map((w: string) => w.trim().toLowerCase()).filter(Boolean),
      req: f.req.split(',').map((w: string) => w.trim().toLowerCase()).filter(Boolean),
      matchW: 0.35, valueW: 0.35, riskW: 0.2, compW: 0.1,
      sort: search.sort, dir: search.sortDir
    }
  };
  if (worker) worker.postMessage(payload);
  else {
    // fallback (worker unsupported): same logic simplified on main thread
    const o = payload.opts;
    const arr = items.filter((s) => {
      if (((s.risk?.score ?? 0) * 100) > o.maxRisk) return false;
      return true;
    });
    visibleIds.value = arr.map((s) => s.listing.id);
  }
  search.page = 0;
}
function goPage(p: number) {
  search.page = Math.min(Math.max(0, p), pages.value - 1);
  document.querySelector('.rgrid, .listcol')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
}
function openDrawer(id: string) { drawerId.value = id; }
async function openJob(id: string) {
  const r = await api<SearchResult>(`/searches/${encodeURIComponent(id)}`);
  if (!r) return;
  if (r.status === 'running') {
    ui.toast('following live search…');
    const done = await search.poll(id, id.slice(-6));
    if (done && done.status !== 'error' && done.status !== 'stopped') applyDone(done, 'reopened');
    return;
  }
  applyDone(r, r.status === 'stopped' ? 'stopped snapshot' : 'snapshot');
}

function fmtErrors(err?: Record<string, string>): string {
  const e = err || {};
  const ks = Object.keys(e);
  if (!ks.length) return '';
  const fmt = (k: string) => {
    const m = String(e[k] || '').slice(0, 120);
    if (/cooling down/i.test(m)) return `${k} cooling down (${m.slice(m.indexOf('retrying'))})`;
    if (/EBAY_APP_ID|EBAY_OAUTH_TOKEN/i.test(m)) return `${k} needs credentials (Admin → Secrets)`;
    if (/403|blocked/i.test(m)) return `${k} blocked by site — retry later or via proxy`;
    return `${k}: ${m}`;
  };
  return ` · source note${ks.length > 1 ? 's' : ''}: ` + ks.map(fmt).join(' · ');
}
function applyDone(r: SearchResult, label: string) {
  search.results = r.results || [];
  search.sid = r.id;
  refilter();
  const errs = fmtErrors(r.driver_errors);
  statusLine.value = `${search.results.length} results · filtered out ${r.filtered_out || 0} · median ${r.median ?? '—'}${errs}`;
  driverNotes.value = errs;
  ui.toast(`done: ${search.results.length} results (${label})`);
}

function intentBase() {
  const lim = f.limitN === '' ? null : Math.max(1, Math.min(100000, +f.limitN || 200));
  const deep = f.deepN === 'all' || f.deepN === '' ? 0 : Math.max(0, Math.min(100000, +f.deepN || 150));
  const hard: Record<string, unknown> = {};
  if (f.min !== '') hard.min_price = +f.min;
  if (f.max !== '') hard.max_price = +f.max;
  const mp = f.maxpages === '' ? undefined : Math.max(1, +f.maxpages);
  return {
    sources: [...search.sources], hard,
    required: f.req.split(',').filter(Boolean).map((w: string) => ({ fields: ['title', 'description'], op: 'contains', value: w.trim() })),
    blacklist: f.black.split(',').filter(Boolean).map((w: string) => ({ fields: ['title', 'description'], op: 'not_contains', value: w.trim() })),
    enrich_top_n: deep, limit: lim, ...(mp ? { max_pages: mp } : {}),
    category: f.catSel, location: f.locQ.trim(), radius_km: f.locR === '' ? undefined : +f.locR,
    cat_map: f.catKa ? { kleinanzeigen: f.catKa } : {},
    risk: { warning_threshold: f.warnT / 100, block_threshold: f.blockT / 100, hard_filter_enabled: f.blockT < 100 },
    ocr: f.fOcr, benchmarks: f.fBench, vision: f.fVision, details: f.fDet,
    require_pickup: f.fPick, require_shipping: f.fShip
  };
}

async function runKw() {
  if (!kwText.value.trim() || busy.value) return;
  busy.value = true;
  statusLine.value = 'Search started in background …';
  try {
    const j = await api<{ id: string }>('/searches', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keywords: kwText.value, ...intentBase() })
    });
    pushHist(kwText.value);
    const done = await search.poll(j.id, kwText.value);
    if (done && done.status !== 'error' && done.status !== 'stopped') applyDone(done, 'fresh');
    else if (done && done.status === 'stopped') { search.results = done.results || []; refilter(); statusLine.value = `stopped — ${search.results.length} partial results`; }
  } catch (e) { statusLine.value = 'search failed: ' + (e instanceof Error ? e.message : String(e)); }
  busy.value = false;
}
async function runNL() {
  if (!nlText.value.trim() || busy.value) return;
  busy.value = true;
  statusLine.value = 'AI is resolving products for: ' + nlText.value + ' …';
  try {
    const j = await api<{ id: string }>('/searches/nl', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: nlText.value, sources: [...search.sources], category: f.catSel, limit: f.limitN === '' ? null : +f.limitN })
    });
    pushHist(nlText.value);
    const done = await search.poll(j.id, 'AI: ' + nlText.value);
    if (done && done.status !== 'error' && done.status !== 'stopped') {
      const p = (done.parsed || {}) as Record<string, unknown>;
      nlApplied.value = {
        keywords: String(p.keywords || ''), models: (p.models as string[]) || [],
        blacklist: ((p.blacklist || []) as { value?: string }[]).map((b) => b.value || '').filter(Boolean),
        required: ((p.required || []) as { value?: string }[]).map((b) => b.value || '').filter(Boolean),
        category: (p.category as string) || '', subs: done.subqueries || []
      };
      applyDone(done, 'AI');
    }
  } catch (e) { statusLine.value = 'NL search failed: ' + (e instanceof Error ? e.message : String(e)); }
  busy.value = false;
}

watch(() => [search.sort, search.sortDir], refilter);

onMounted(async () => {
  try {
    const d = await api<{ id: string }[]>('/drivers');
    allSources.value = (d || []).map((x: { id: string }) => x.id);
    if (!search.sources.size) search.sources = new Set(allSources.value.filter((s) => !['ebay'].includes(s)));
  } catch { /* offline */ }
  try {
    const wh = await api<{ categories: Category[] }>('/drivers/willhaben/categories');
    cats.wh = wh?.categories || [];
  } catch { /* offline */ }
  try {
    const ka = await api<{ categories: { label: string; id: string }[] }>('/drivers/kleinanzeigen/categories');
    cats.ka = (ka?.categories || []).map((c: { label: string; id: string }) => ({ label: c.label, id: c.id }));
  } catch { /* offline */ }
  search.loadFavs();
  const open = route.query.open;
  if (typeof open === 'string' && open) {
    const r = await api<SearchResult>(`/searches/${encodeURIComponent(open)}`);
    if (r) {
      if (r.status === 'running') {
        ui.toast('following live search…');
        const done = await search.poll(open, open.slice(-6));
        if (done && done.status !== 'error' && done.status !== 'stopped') applyDone(done, 'reopened');
      } else applyDone(r, 'snapshot');
    }
  }
});
</script>

<style scoped>
.searchpanel { display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1rem; }
.modeseg { display: flex; gap: 0.25rem; background: var(--bg2); border-radius: 0.75rem; padding: 0.25rem; width: fit-content; }
.modeseg button { display: inline-flex; align-items: center; gap: 0.375rem; border: none; background: transparent; color: var(--mut); font-weight: 700; padding: 0.5rem 0.875rem; border-radius: 0.6rem; cursor: pointer; min-height: var(--tap); }
.modeseg button.active { background: var(--acc); color: #fff; }
.row { display: flex; gap: 0.5rem; }
.grow { flex: 1; }
@media (max-width: 30rem) {
  form.row { flex-direction: column; }
  form.row .btn { width: 100%; justify-content: center; }
}
.applied { border-top: 1px solid var(--line); padding-top: 0.5rem; }
.ai-kw { font-weight: 700; }
.chips { display: flex; gap: 0.375rem; flex-wrap: wrap; margin: 0.375rem 0; }
.chip { background: var(--bg2); border: 1px solid var(--line); border-radius: 99px; padding: 2px 10px; font-size: var(--fs-xs); cursor: pointer; }
.adv summary { cursor: pointer; font-weight: 600; min-height: var(--tap); display: flex; align-items: center; gap: 0.375rem; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 99px; background: var(--acc); }
.advgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr)); gap: 0.625rem; margin: 0.625rem 0; }
.fld { display: flex; flex-direction: column; gap: 0.25rem; font-size: var(--fs-xs); font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.9; }
.fld .inp, .fld select.inp { text-transform: none; letter-spacing: normal; font-weight: 400; }
.srcs { display: flex; gap: 0.375rem; flex-wrap: wrap; }
.ck { display: inline-flex; align-items: center; gap: 0.25rem; border: 1px solid var(--line); border-radius: 99px; padding: 4px 10px; font-size: var(--fs-xs); cursor: pointer; text-transform: none; }
.ck.on { background: var(--acc-soft); border-color: var(--acc); }
.histrow { display: flex; gap: 0.375rem; align-items: center; flex-wrap: wrap; }
.toolbar { display: flex; gap: 0.5rem; align-items: end; flex-wrap: wrap; margin-bottom: 0.625rem; }
.toolbar label { display: flex; flex-direction: column; gap: 0.25rem; font-size: var(--fs-xs); font-weight: 700; text-transform: uppercase; }
.iconbtn { min-width: var(--tap); justify-content: center; }
.iconbtn.active { background: var(--acc-soft); border-color: var(--acc); }
.refine { margin-bottom: 0.625rem; }
.kinds { align-items: center; flex-wrap: wrap; }
.kinds button { border: 1px solid var(--line); background: transparent; color: var(--mut); border-radius: 99px; padding: 6px 12px; cursor: pointer; min-height: 36px; }
.kinds button.active { background: var(--acc-soft); border-color: var(--acc); color: var(--ink); }
.statusline { margin-bottom: 0.625rem; }
.rgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); gap: 0.75rem; }
.listcol { display: flex; flex-direction: column; gap: 0.5rem; }
.empty { text-align: center; opacity: 0.6; padding: 2rem; }
@media (min-width: 70rem) {
  .searchpage { display: block; }
}
</style>
