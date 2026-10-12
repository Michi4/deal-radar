<template>
  <div>
    <h2>Compare <small>side-by-side spec · price · risk</small></h2>
    <div v-if="rows.length < 2" class="panel">
      <b>How comparing works</b><br />
      <small>1. Run any search.<br />2. Tick <b>compare</b> on 2+ listings (cards or list rows).<br />3. Open this tab — you get them side by side: price, source, risk, score, CPU + benchmark, RAM, storage, ports, barebone, GPU.</small>
      <br /><br />
      <router-link to="/"><button class="btn btn-primary">go search</button></router-link>
      <div v-if="rows.length === 1" class="lane">1 picked — pick more ({{ pickedTitle }})</div>
    </div>
    <div v-else class="panel scroll">
      <table class="cmp">
        <tr>
          <td v-for="s in rows" :key="s.listing.id">
            <b>{{ s.listing.title }}</b><br />{{ s.listing.price ?? '?' }} {{ s.listing.currency || '' }}<br />
            {{ s.listing.source }}<br />risk {{ Math.round((s.risk?.score ?? 0) * 100) }}%<br />
            score {{ s.final_score }}<br />cpu {{ cpuOf(s) }}<br />bench {{ benchOf(s) }}<br />ram {{ ramOf(s) }}<br />storage {{ storageOf(s) }}<br />ports {{ portsOf(s) }}<br />{{ bareboneOf(s) }}<br />gpu {{ gpuOf(s) }}
          </td>
        </tr>
      </table>
      <button class="btn" @click="search.compare.clear()">clear all</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useSearch } from '@/stores/search';
import type { Scored } from '@/types';

const search = useSearch();
const rows = computed(() => [...search.compare]
  .map((id) => search.results.find((s) => s.listing.id === id))
  .filter(Boolean) as Scored[]);
const pickedTitle = computed(() => rows.value[0]?.listing.title || '');
const cpuOf = (s: Scored) => (s.enrichments || []).find((e) => e.field === 'cpu')?.value ?? '—';
const benchOf = (s: Scored) => (s.enrichments || []).find((e) => e.field === 'cpu_benchmark' || e.field === 'gpu_benchmark')?.value ?? '—';
const ramOf = (s: Scored) => {
  const v = (s.enrichments || []).find((e) => e.field === 'ram_gb')?.value;
  return v === undefined || v === null ? '—' : `${v}GB RAM`;
};
const storageOf = (s: Scored) => {
  const gb = (s.enrichments || []).find((e) => e.field === 'storage_gb')?.value;
  if (gb === undefined || gb === null) return '—';
  const kind = (s.enrichments || []).find((e) => e.field === 'storage_kind')?.value;
  return kind ? `${gb}GB ${kind}` : `${gb}GB`;
};
const portsOf = (s: Scored) => (s.enrichments || []).find((e) => e.field === 'ports')?.value ?? '—';
const bareboneOf = (s: Scored) => ((s.enrichments || []).find((e) => e.field === 'barebone')?.value ? 'barebone (no RAM/SSD)' : 'complete');
const gpuOf = (s: Scored) => (s.enrichments || []).find((e) => e.field === 'gpu')?.value ?? '—';
</script>

<style scoped>
h2 small { opacity: 0.6; font-weight: 400; }
.scroll { overflow-x: auto; }
table.cmp td { vertical-align: top; padding: 0.5rem 1rem; border-left: 1px solid var(--line); min-width: 12rem; }
</style>
