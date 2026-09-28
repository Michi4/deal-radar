<template>
  <div>
    <h2>Saved <small>{{ items.length }} favorites</small></h2>
    <div class="panel track">
      <div class="eyebrow">Track a link from the marketplace</div>
      <div class="row">
        <input v-model="url" class="inp grow" placeholder="paste willhaben / kleinanzeigen link…" inputmode="url" aria-label="listing URL to track" @keyup.enter="track" />
        <button class="btn btn-primary" @click="track">track</button>
      </div>
      <small>Saves it to favorites and watches every change (price, text, photos).</small>
    </div>
    <div v-if="loading" class="empty">loading…</div>
    <div v-else-if="!items.length" class="empty">No favorites yet — tap the star on any result.</div>
    <div class="card fav" v-for="x in items" :key="x.listing_id">
      <b>{{ x.title || x.listing_id }}</b><br />
      <span class="price">{{ x.price ?? '?' }}</span>
      <a v-if="x.url" :href="x.url" target="_blank" rel="noopener">open</a>
      <button class="btn" @click="remove(x.listing_id)" aria-label="remove favorite"><X :size="15" /></button>
      <div v-if="x.note"><small>note: {{ x.note }}</small></div>
      <div class="hist">
        <div v-for="(h, i) in x.history || []" :key="i">{{ h.kind }}: {{ String(h.old).slice(0, 60) }} → {{ String(h.new).slice(0, 60) }}</div>
        <small v-if="!(x.history || []).length">no changes tracked yet</small>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { X } from 'lucide-vue-next';
import { api } from '@/api';
import { useUi } from '@/stores/ui';

interface Fav { listing_id: string; title?: string; price?: number | null; url?: string; note?: string; history?: { kind: string; old: string; new: string }[] }
const ui = useUi();
const items = ref<Fav[]>([]);
const url = ref('');
const loading = ref(true);

async function load() {
  loading.value = true;
  items.value = (await api<Fav[]>('/favorites', {}, 1)) || [];
  loading.value = false;
}
async function track() {
  if (!url.value.trim()) { ui.toast('paste a link first'); return; }
  const r = await api<{ ok: boolean; title?: string; error?: string }>('/favorites/by-url', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: url.value })
  });
  ui.toast(r?.ok ? `tracking: ${(r.title || '').slice(0, 60)}` : `not trackable: ${r?.error || '?'}`);
  if (r?.ok) load();
}
async function remove(id: string) {
  await api(`/favorites/${encodeURIComponent(id)}`, { method: 'DELETE' });
  load();
}
onMounted(load);
</script>

<style scoped>
h2 small { opacity: 0.6; font-weight: 400; }
.track { margin-bottom: 0.75rem; }
.row { display: flex; gap: 0.5rem; } .grow { flex: 1; }
.fav { padding: 0.625rem; margin-bottom: 0.5rem; }
.hist { margin-top: 0.375rem; font-size: var(--fs-xs); }
.empty { text-align: center; opacity: 0.55; padding: 1.5rem; }
</style>
