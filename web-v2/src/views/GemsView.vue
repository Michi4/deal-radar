<template>
  <div>
    <h2>Gems <small>best measured value across everything seen</small></h2>
    <div class="panel">
      <div class="row">
        <button class="btn btn-primary" @click="hunt" :disabled="hunting" title="One click, three broad unlimited searches">start value hunt (3 searches)</button>
        <button class="btn" @click="summarize" :disabled="busy" title="AI summary + ranking over it all">AI summary of it all</button>
        <label class="ck"><input type="checkbox" v-model="favOnly" @change="load" /> favorites only</label>
      </div>
      <small v-if="meta">{{ meta }}</small>
      <div v-if="advice" class="panel advise">
        <div class="eyebrow">AI summary {{ advice.fallback ? '(rule-based — AI unreachable)' : '' }}</div>
        <p>{{ advice.summary }}</p>
        <div v-if="(advice.honest_flags || []).length" class="flags">flags: {{ (advice.honest_flags || []).join(' · ') }}</div>
        <ol>
          <li v-for="p in advice.picks || []" :key="p.url">
            <b>#{{ p.rank }}</b> {{ p.verdict }}
            <div><small>plus: {{ (p.pros || []).join(' · ') }}</small></div>
            <div><small>minus: {{ (p.cons || []).join(' · ') }}</small></div>
            <div><a :href="p.url" target="_blank" rel="noopener">open listing</a></div>
          </li>
        </ol>
      </div>
      <div class="row">
        <button v-for="s in sections" :key="s.key" class="btn btn-sm" :class="sec === s.key ? 'btn-primary' : ''" @click="sec = s.key">{{ s.title }} ({{ s.rows.length }})</button>
      </div>
      <div class="row">
        <span><small>sort by:</small></span>
        <button v-for="c in cols" :key="c.key" class="btn btn-sm" :class="sortKey === c.key ? 'btn-primary' : ''" @click="setSort(c.key)" :title="'sort by ' + c.label">{{ c.label }}{{ sortKey === c.key ? (sortDir > 0 ? ' ↓' : ' ↑') : '' }}</button>
      </div>
      <div class="rgrid">
        <div v-for="r in sorted" :key="r.url" class="card res">
          <div class="thumbwrap" v-if="r.image">
            <img class="thumb" loading="lazy" :src="safeUrl(r.image || '')" @error="imgGone" alt="" />
          </div>
          <div class="body">
            <span class="best-badge" v-if="r.kind && r.kind !== 'offer'">{{ r.kind }}</span>
            <h4 :title="r.title"><a :href="r.url" target="_blank" rel="noopener">{{ r.title || '(no title)' }}</a></h4>
            <div>
              <span class="price">{{ r.price ?? '?' }} {{ r.currency || '' }}</span>
              <span class="badge">{{ r.cpu || '?' }}</span>
            </div>
            <div class="lane">{{ r.source || '' }} · {{ r.multi || '?' }} MT{{ r.single ? ` / ${r.single} ST` : '' }}</div>
            <div class="lane">perf/€ <b>{{ r.ppe ?? '—' }}</b> · perf/W <b>{{ r.ppw ?? '—' }}</b></div>
            <div class="row">
              <a :href="r.url" target="_blank" rel="noopener"><button class="btn btn-sm btn-primary">open listing</button></a>
              <button class="btn btn-sm iconbtn" @click="fav(r)" :aria-label="r.fav ? 'saved' : 'save favorite'" :title="r.fav ? 'saved favorite' : 'save favorite'">
                <Star :size="15" :fill="r.fav ? 'currentColor' : 'none'" />
              </button>
            </div>
          </div>
        </div>
      </div>
      <small v-if="!sorted.length">nothing rated yet — run a search or the value hunt first.</small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Star } from 'lucide-vue-next';
import { api, safeUrl } from '@/api';
import { useUi } from '@/stores/ui';

const ui = useUi();
interface Row { cpu?: string; price?: number; currency?: string; title?: string; source?: string; url?: string; image?: string; multi?: number; single?: number; ppe?: number; ppw?: number; kind?: string; fav?: boolean }
interface Board { ppe: Row[]; efficient: Row[]; ppw: Row[]; raw: Row[]; items?: number; unrated?: number; advice?: { summary?: string; picks?: { url?: string; rank?: number; verdict?: string; pros?: string[]; cons?: string[] }[]; honest_flags?: string[]; fallback?: boolean } }
const board = ref<Board | null>(null);
const favOnly = ref(false);
const busy = ref(false);
const hunting = ref(false);
const sec = ref('ppe');
const sortKey = ref('ppe');
const sortDir = ref(-1);
const advice = computed(() => board.value?.advice || null);
const meta = computed(() => board.value ? `${board.value.items} rated items · ${board.value.unrated} without benchmark data` : '');
const cols = [
  { key: 'ppe', label: 'perf/€' }, { key: 'ppw', label: 'perf/W' }, { key: 'multi', label: 'MT marks' },
  { key: 'price', label: 'price' }, { key: 'cpu', label: 'CPU' }, { key: 'source', label: 'source' }
];
const sections = computed(() => board.value ? [
  { key: 'ppe', title: 'Top perf/€', rows: board.value.ppe || [] },
  { key: 'eff', title: 'Efficient + cheap', rows: board.value.efficient || [] },
  { key: 'ppw', title: 'Top perf/Watt', rows: board.value.ppw || [] },
  { key: 'raw', title: 'Raw champs', rows: board.value.raw || [] }
] : []);
const active = computed(() => sections.value.find((s) => s.key === sec.value)?.rows || []);
const sorted = computed(() => {
  const arr = [...active.value];
  const k = sortKey.value;
  const get = (r: Row): string | number => {
    if (k === 'cpu') return (r.cpu || '').toLowerCase();
    if (k === 'source') return (r.source || '').toLowerCase();
    if (k === 'price') return r.price ?? Number.MAX_SAFE_INTEGER;
    if (k === 'multi') return r.multi ?? -1;
    if (k === 'ppw') return r.ppw ?? -1;
    return r.ppe ?? -1;
  };
  arr.sort((a, b) => {
    const x = get(a), y = get(b);
    const c = typeof x === 'string' ? x.localeCompare(y as string) : (x as number) - (y as number);
    return c * sortDir.value;
  });
  return arr;
});
function setSort(k: string) {
  if (sortKey.value === k) sortDir.value *= -1;
  else { sortKey.value = k; sortDir.value = k === 'price' || k === 'cpu' || k === 'source' ? 1 : -1; }
}
function imgGone(e: Event) { (e.target as HTMLElement).remove(); }
async function fav(r: Row) {
  try {
    await api('/favorites/by-url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: r.url }) });
    r.fav = true;
  } catch (e) { ui.toast('save failed'); }
}
async function load() {
  try {
    board.value = await api<Board>(`/gems/board?limit=100&favs=${favOnly.value ? 1 : 0}`);
  } catch (e) { ui.toast('gems failed'); }
}
async function summarize() {
  busy.value = true;
  try {
    board.value = await api<Board>(`/gems/board?limit=30&favs=${favOnly.value ? 1 : 0}&advise=1`);
  } catch (e) { ui.toast('summary failed'); }
  busy.value = false;
}
async function hunt() {
  hunting.value = true;
  try {
    const r = await api<{ ids?: string[] }>('/hunt', { method: 'POST' });
    ui.toast(`value hunt started: ${(r?.ids || []).length} searches — come back, then AI summary`);
  } catch (e) { ui.toast('hunt failed'); }
  hunting.value = false;
}
onMounted(load);
</script>

<style scoped>
.rgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); gap: 0.75rem; margin-top: 0.75rem; }
.res { cursor: default; overflow: hidden; }
.thumbwrap { position: relative; aspect-ratio: 4/3; background: var(--bg2); }
.thumb { width: 100%; height: 100%; object-fit: cover; display: block; }
.body { padding: 0.625rem; display: flex; flex-direction: column; gap: 0.375rem; }
.body h4 { margin: 0; font-size: var(--fs-sm); overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.body h4 a { color: inherit; text-decoration: none; }
.body h4 a:hover { text-decoration: underline; }
.price { font-weight: 800; font-size: 1.05rem; color: var(--acc-d, #047857); }
.badge { display: inline-block; font-size: var(--fs-xs); background: var(--bg2); border-radius: 99px; padding: 2px 10px; margin-left: 0.375rem; }
.best-badge { align-self: flex-start; font-size: var(--fs-xs); font-weight: 800; background: var(--acc); color: #fff; border-radius: 99px; padding: 2px 10px; }
.lane { font-size: var(--fs-xs); opacity: 0.75; }
.lane b { opacity: 1; }
.row { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin: 0.5rem 0; }
.advise { margin: 0.75rem 0; }
.advise ol { margin: 0.5rem 0; padding-left: 1.25rem; display: flex; flex-direction: column; gap: 0.625rem; }
.flags { font-size: var(--fs-sm); color: #b91c1c; }
.tscroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
td, th { border-bottom: 1px solid var(--line); padding: 6px 10px; text-align: left; font-size: var(--fs-sm); }
</style>
