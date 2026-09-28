<template>
  <div>
    <h2>Searches <small>jump back in anytime · re-run or delete</small></h2>
    <div v-if="loading" class="empty">loading…</div>
    <div v-else-if="!tiles.length" class="empty">No searches yet.</div>
    <div class="rgrid">
      <div class="card tile" v-for="s in tiles" :key="s.id">
        <b>{{ s.keywords || '(query)' }}</b>
        <span v-if="s.watch" class="badge watch">watch</span>
        <span v-if="s.job" class="jobpill" :class="pillClass(s.job.status)">{{ pillText(s) }}</span>
        <br />
        <small>{{ when(s.ts) }} · {{ (s.sources || []).join('+') || 'all sources' }} · {{ s.results }} results<span v-if="s.filtered_out"> · {{ s.filtered_out }} hidden</span></small>
        <div v-if="s.job && s.job.status === 'running' && s.job.total" class="pbar"><i :style="{ width: Math.min(100, Math.round(100 * (s.job.done || 0) / s.job.total)) + '%' }"></i></div>
        <div v-if="s.job && s.job.status === 'running' && s.job.detail"><small>{{ String(s.job.detail).slice(0, 80) }}</small></div>
        <div class="thumbs">
          <img v-for="(u, i) in (s.thumbs || []).slice(0, 4)" :key="i" :src="safeUrl(u)" loading="lazy" @error="imgGone" alt="" />
        </div>
        <div class="row">
          <button class="btn btn-primary btn-sm" @click="openSearch(s.id)">open</button>
          <button v-if="s.job && s.job.status === 'interrupted'" class="btn btn-sm" @click="redo(s.id)">resume</button>
          <button v-else class="btn btn-sm" @click="redo(s.id)" title="Run the same query again">re-run</button>
          <button class="btn btn-sm" @click="del(s.id)" title="Delete this search">delete</button>
          <button class="btn btn-sm" @click="watch(s.id)" title="Re-poll automatically and notify">watch</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api, safeUrl } from '@/api';
import { useUi } from '@/stores/ui';

interface Tile { id: string; keywords?: string; ts?: number; sources?: string[]; results?: number; filtered_out?: number; watch?: boolean; thumbs?: string[]; job?: { status: string; done?: number; total?: number; detail?: string } }
const ui = useUi();
const router = useRouter();
const tiles = ref<Tile[]>([]);
const loading = ref(true);
let timer: number | null = null;

async function load() {
  const r = await api<{ searches: Tile[] }>('/searches', {}, 1);
  tiles.value = r?.searches || [];
  loading.value = false;
  if (tiles.value.some((s) => s.job && s.job.status === 'running') && timer == null) {
    timer = window.setInterval(() => { if (document.visibilityState === 'visible') load(); }, 8000);
  }
}
const when = (ts?: number) => { try { return ts ? new Date(ts * 1000).toLocaleString() : ''; } catch { return ''; } };
const pillClass = (st: string) => st === 'running' ? 'jobrun' : st === 'done' ? '' : 'joberr';
const pillText = (s: Tile) => s.job!.status === 'running' ? `running ${s.job!.done || 0}/${s.job!.total || '?'}` : s.job!.status;
function imgGone(e: Event) { (e.target as HTMLElement).remove(); }
async function openSearch(id: string) { router.push({ name: 'search', query: { open: id } }); }
async function redo(id: string) {
  const r = await api<{ id: string }>(`/searches/${encodeURIComponent(id)}/redo`, { method: 'POST' });
  if (r?.id) { ui.toast('re-running'); router.push({ name: 'search', query: { open: r.id } }); }
}
async function del(id: string) {
  await api(`/searches/${encodeURIComponent(id)}`, { method: 'DELETE' });
  load();
}
async function watch(id: string) {
  const r = await api<{ id?: string; error?: string }>(`/searches/${encodeURIComponent(id)}/watch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  ui.toast(r?.id ? 'watching every 30 min' : `watch failed: ${r?.error || '?'}`);
  load();
}
onMounted(load);
onUnmounted(() => { if (timer != null) clearInterval(timer); });
</script>

<style scoped>
h2 small { opacity: 0.6; font-weight: 400; }
.rgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr)); gap: 0.75rem; }
.tile { padding: 0.625rem; }
.badge.watch { background: #16a34a; color: #fff; }
.jobpill { display: inline-block; font-size: var(--fs-xs); font-weight: 800; border-radius: 99px; padding: 2px 10px; background: var(--acc-soft); }
.jobrun { background: var(--acc); color: #fff; } .joberr { background: #dc2626; color: #fff; }
.pbar { height: 6px; background: var(--line); border-radius: 99px; overflow: hidden; margin: 0.375rem 0; }
.pbar i { display: block; height: 100%; background: var(--acc); }
.thumbs { display: flex; gap: 4px; margin: 6px 0; }
.thumbs img { width: 56px; height: 44px; object-fit: cover; border-radius: 6px; }
.row { display: flex; gap: 0.375rem; flex-wrap: wrap; }
.btn-sm { min-height: 36px; }
.empty { text-align: center; opacity: 0.55; padding: 1.5rem; }
small { color: var(--mut); }
</style>
