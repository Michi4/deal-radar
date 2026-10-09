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
      <div v-for="sec in sections" :key="sec.key">
        <h3>{{ sec.title }} ({{ sec.rows.length }})</h3>
        <div class="tscroll"><table>
          <tr><th>CPU</th><th>price</th><th>title</th><th>src</th><th>MT</th><th>pts/€</th><th>pts/W</th><th></th></tr>
          <tr v-for="r in sec.rows" :key="r.url">
            <td>{{ r.cpu || '?' }}</td><td><b>{{ r.price ?? '?' }} €</b></td>
            <td>{{ (r.title || '').slice(0, 70) }}</td><td>{{ r.source }}</td>
            <td>{{ r.multi }}</td><td>{{ r.ppe }}</td><td>{{ r.ppw || '—' }}</td>
            <td><a :href="r.url" target="_blank" rel="noopener">open</a></td>
          </tr>
        </table></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { api } from '@/api';
import { useUi } from '@/stores/ui';

const ui = useUi();
interface Row { cpu?: string; price?: number; title?: string; source?: string; url?: string; multi?: number; ppe?: number; ppw?: number }
interface Board { ppe: Row[]; efficient: Row[]; ppw: Row[]; raw: Row[]; items?: number; unrated?: number; advice?: { summary?: string; picks?: { url?: string; rank?: number; verdict?: string; pros?: string[]; cons?: string[] }[]; honest_flags?: string[]; fallback?: boolean } }
const board = ref<Board | null>(null);
const favOnly = ref(false);
const busy = ref(false);
const hunting = ref(false);
const advice = computed(() => board.value?.advice || null);
const meta = computed(() => board.value ? `${board.value.items} rated items · ${board.value.unrated} without benchmark data` : '');
const sections = computed(() => board.value ? [
  { key: 'ppe', title: 'Top perf/€', rows: board.value.ppe || [] },
  { key: 'eff', title: 'Efficient + cheap (≥700 pts/W)', rows: board.value.efficient || [] },
  { key: 'ppw', title: 'Top perf/Watt', rows: board.value.ppw || [] },
  { key: 'raw', title: 'Raw champs', rows: board.value.raw || [] }
] : []);

async function load() {
  try {
    board.value = await api<Board>(`/gems?limit=25&favs=${favOnly.value ? 1 : 0}`);
  } catch (e) { ui.toast('gems failed'); }
}
async function summarize() {
  busy.value = true;
  try {
    board.value = await api<Board>(`/gems?limit=30&favs=${favOnly.value ? 1 : 0}&advise=1`);
  } catch (e) { ui.toast('summary failed'); }
  busy.value = false;
}
async function hunt() {
  hunting.value = true;
  try {
    const r = await api<{ ids?: string[] }>('/hunt', { method: 'POST' });
    ui.toast(`value hunt started: ${(r?.ids || []).length} searches`);
  } catch (e) { ui.toast('hunt failed'); }
  hunting.value = false;
}
onMounted(load);
</script>
