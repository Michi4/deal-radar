<template>
  <div>
    <h2>Store <small>drivers &amp; enrichers · one-click install</small></h2>
    <div v-if="loading" class="empty">loading store…</div>
    <div v-else>
      <h3>Drivers</h3>
      <div class="rgrid">
        <div class="card it" v-for="x in drivers" :key="x.id">
          <b>{{ x.display_name || x.id }}</b>
          <small>v{{ x.version || '?' }} · {{ x.author || '' }} · {{ x.license || '' }}</small>
          <span v-if="x.status && x.status !== 'ok'" class="badge" :class="x.status === 'blocked' ? 'risk-high' : 'risk-medium'" :title="x.status_reason">{{ x.status }}</span>
          <small v-if="x.status && x.status !== 'ok'">{{ x.status_reason }}</small>
          <br /><small>{{ (x.capabilities || []).join(', ') }}</small><br />
          <span v-if="x.installed" class="badge risk-low">installed</span>
          <span v-if="x.disabled" class="jobpill joberr">disabled</span>
          <button v-if="!x.installed || x.disabled" class="btn btn-primary btn-sm" @click="install(x.id)">install</button>
          <button v-else class="btn btn-sm" @click="uninstall(x.id, $event)" title="Click twice to confirm">uninstall</button>
          <div v-if="x.requires"><small>needs: {{ x.requires.join(', ') }}{{ x.configured ? ' (ok)' : ' (missing)' }}</small></div>
        </div>
      </div>
      <h3>Enrichers</h3>
      <div class="rgrid">
        <div class="card it" v-for="x in enrichers" :key="x.id">
          <b>{{ x.display_name || x.id }}</b> <small>v{{ x.version || '?' }}</small><br />
          <small>{{ (x.capabilities || []).join(', ') }}</small>
        </div>
      </div>
      <div class="empty">contribute via PR to marketplace/index.json</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '@/api';
import { useUi } from '@/stores/ui';

interface Item { id: string; display_name?: string; version?: string; author?: string; license?: string; capabilities?: string[]; installed?: boolean; disabled?: boolean; requires?: string[]; configured?: boolean; status?: string; status_reason?: string }
const ui = useUi();
const drivers = ref<Item[]>([]);
const enrichers = ref<Item[]>([]);
const loading = ref(true);

async function load() {
  loading.value = true;
  const r = await api<{ drivers: Item[]; enrichers: Item[] }>('/marketplace', {}, 1);
  drivers.value = r?.drivers || [];
  enrichers.value = r?.enrichers || [];
  loading.value = false;
}
async function install(id: string) {
  const r = await api<{ ok: boolean; error?: string; note?: string }>('/marketplace/install', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id })
  });
  ui.toast(r?.ok ? 'ok: installed ' + id : 'fail: ' + (r?.error || r?.note || 'failed'));
  load();
}
async function uninstall(id: string, ev: Event) {
  const el = ev.target as HTMLElement;
  if (!el.dataset.armed) {
    el.dataset.armed = '1';
    const old = el.textContent;
    el.textContent = 'sure?';
    setTimeout(() => { if (el.isConnected) { delete el.dataset.armed; el.textContent = old; } }, 8000);
    ui.toast('click again to confirm uninstall');
    return;
  }
  const r = await api<{ ok: boolean; error?: string }>(`/marketplace/${encodeURIComponent(id)}`, { method: 'DELETE' });
  ui.toast(r?.ok ? 'ok: uninstalled ' + id : 'fail: ' + (r?.error || 'failed'));
  load();
}
onMounted(load);
</script>

<style scoped>
h2 small, h3 { opacity: 0.7; }
.rgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr)); gap: 0.75rem; }
.it { padding: 0.625rem; display: flex; flex-direction: column; gap: 0.25rem; }
.badge { width: fit-content; }
.risk-low { background: #16a34a; color: #fff; } .risk-medium { background: #d97706; color: #fff; } .risk-high { background: #dc2626; color: #fff; }
.jobpill { font-size: var(--fs-xs); font-weight: 800; border-radius: 99px; padding: 2px 10px; background: var(--acc-soft); width: fit-content; }
.joberr { background: #dc2626; color: #fff; }
.btn-sm { min-height: 36px; width: fit-content; }
.empty { text-align: center; opacity: 0.55; padding: 1.5rem; }
small { color: var(--mut); }
</style>
