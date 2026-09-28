<template>
  <div>
    <h2>admin</h2>
    <div class="statgrid">
      <div class="card stat" v-for="s in stats" :key="s[1]"><b>{{ s[0] }}</b><span>{{ s[1] }}</span></div>
    </div>
    <div class="tabs">
      <button v-for="t in tabs" :key="t" :class="{ active: tab === t }" @click="tab = t">{{ t }}</button>
    </div>
    <div v-if="tab === 'Overview'" class="panel">
      <div class="eyebrow">Pipeline metrics</div>
      <table v-if="metricRows.length"><tr v-for="r in metricRows" :key="r[0]"><td>{{ r[0] }}</td><td>{{ r[1] }}</td></tr></table>
      <small v-else>no metrics yet</small>
      <div><small>auto-refreshes every 15s</small></div>
    </div>
    <div v-if="tab === 'Drivers'" class="panel">
      <div class="eyebrow">Drivers (disable/enable is live, no restart)</div>
      <table>
        <tr><th>driver</th><th>state</th><th>transport</th><th>failures</th><th>last error</th><th></th></tr>
        <tr v-for="d in drivers" :key="d.id">
          <td>{{ d.display_name || d.id }}<span v-if="d.disabled"> (disabled)</span><span v-if="d.configured === false"> (needs setup)</span></td>
          <td>{{ d.disabled ? '—' : (health[d.id]?.ok ? 'ok' : 'down') }}</td>
          <td>{{ d.transport || 'direct' }}</td>
          <td>{{ health[d.id]?.consecutive_failures ?? 0 }}</td>
          <td>{{ String(health[d.id]?.last_error || '').slice(0, 100) }}</td>
          <td><button class="btn btn-sm" @click="toggleDrv(d)">{{ d.disabled ? 'enable' : 'disable' }}</button></td>
        </tr>
      </table>
    </div>
    <div v-if="tab === 'Secrets'" class="panel">
      <div class="eyebrow">Tokens &amp; keys — values never leave this box, never shown back</div>
      <div v-for="s in secrets" :key="s.key" class="secrow">
        <div class="meta"><b>{{ s.label }}</b><small>{{ s.key }} · {{ s.configured ? 'configured' : 'not set' }}</small></div>
        <div class="row">
          <input v-model="secVals[s.key]" class="inp" :type="s.secret ? 'password' : 'text'" :placeholder="s.configured ? '(set — retype to change)' : '(empty)'" :aria-label="s.label" />
          <button class="btn btn-sm" @click="saveSec(s.key)">save</button>
        </div>
      </div>
      <small>{{ secMsg }}</small>
      <div><small>Saved to the server database and applied live (no restart). Server env stays the fallback.</small></div>
    </div>
    <div v-if="tab === 'Searches'" class="panel">
      <div class="eyebrow">Searches &amp; jobs</div>
      <div v-for="s in searches" :key="s.id" class="srow">
        <b>{{ s.keywords }}</b> <small>{{ s.results }} results · {{ s.job?.status || 'done' }}</small>
        <button class="btn btn-sm" @click="delSearch(s.id)">delete</button>
      </div>
      <small v-if="!searches.length">none</small>
    </div>
    <div v-if="tab === 'Events'" class="panel">
      <div class="eyebrow">Live events</div>
      <div v-for="(e, i) in events" :key="i" class="ev">{{ e.kind }}: {{ (e.title || '').slice(0, 100) }}</div>
      <small v-if="!events.length">no events yet</small>
    </div>
    <div v-if="tab === 'Danger'" class="panel">
      <div class="eyebrow">Danger zone</div>
      <div class="row">
        <input v-model="resetWord" class="inp" placeholder='type RESET to wipe all data' aria-label="reset confirmation" />
        <button class="btn" @click="resetAll">wipe</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue';
import { api } from '@/api';
import { useUi } from '@/stores/ui';

const ui = useUi();
const tabs = ['Overview', 'Drivers', 'Secrets', 'Searches', 'Events', 'Danger'];
const tab = ref('Overview');
const stats = ref<[string | number, string][]>([]);
const metricRows = ref<[string, string][]>([]);
const drivers = ref<{ id: string; display_name?: string; disabled?: boolean; configured?: boolean; transport?: string }[]>([]);
const health = ref<Record<string, { ok?: boolean; consecutive_failures?: number; last_error?: string }>>({});
const secrets = ref<{ key: string; label: string; secret?: boolean; configured?: boolean }[]>([]);
const secVals = reactive<Record<string, string>>({});
const secMsg = ref('');
const searches = ref<{ id: string; keywords?: string; results?: number; job?: { status: string } }[]>([]);
const events = ref<{ kind: string; title?: string }[]>([]);
const resetWord = ref('');
let timer: number | null = null;

async function tick() {
  try {
    const m = await api<{ searches?: number; events?: number; drivers?: Record<string, { ok?: boolean; consecutive_failures?: number; last_error?: string }>; _allDrivers?: { id: string; display_name?: string; disabled?: boolean; configured?: boolean; transport?: string }[]; watchlist?: unknown[]; metrics?: Record<string, unknown> }>('/metrics.json', {}, 1);
    if (!m) return;
    const drv = m.drivers || {};
    const okN = Object.values(drv).filter((d) => d.ok).length;
    stats.value = [
      [m.searches ?? 0, 'searches'], [m.events ?? 0, 'live events'],
      [`${okN}/${(m._allDrivers || []).length}`, 'drivers ok'],
      [(m.watchlist || []).length, 'watches/jobs']
    ];
    health.value = drv;
    drivers.value = m._allDrivers || [];
    metricRows.value = Object.entries(m.metrics || {}).map(([k, v]) => [k, String(v)]);
  } catch { /* offline */ }
}
async function loadSecrets() {
  const r = await api<{ secrets: { key: string; label: string; secret?: boolean; configured?: boolean }[] }>('/settings/secrets');
  secrets.value = r?.secrets || [];
}
async function saveSec(key: string) {
  const r = await api<{ ok: boolean; error?: string }>('/settings/secrets', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, value: secVals[key] || '' })
  });
  secMsg.value = r?.ok ? `saved ${key}` : `failed: ${r?.error || '?'}`;
  if (r?.ok) secVals[key] = '';
  loadSecrets();
}
async function loadSearches() {
  const r = await api<{ searches: { id: string; keywords?: string; results?: number; job?: { status: string } }[] }>('/searches', {}, 1);
  searches.value = r?.searches || [];
}
async function delSearch(id: string) {
  await api(`/searches/${encodeURIComponent(id)}`, { method: 'DELETE' });
  loadSearches(); tick();
}
async function toggleDrv(d: { id: string; disabled?: boolean }) {
  if (d.disabled) {
    await api('/marketplace/install', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: d.id }) });
  } else {
    await api(`/marketplace/${encodeURIComponent(d.id)}`, { method: 'DELETE' });
  }
  tick();
}
async function resetAll() {
  if (resetWord.value !== 'RESET') { ui.toast('type RESET to wipe all data'); return; }
  await api('/admin/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: 'RESET' }) });
  resetWord.value = '';
  tick(); loadSearches();
}
onMounted(async () => { await tick(); loadSecrets(); loadSearches(); timer = window.setInterval(tick, 15000); });
onUnmounted(() => { if (timer != null) clearInterval(timer); });
</script>

<style scoped>
.statgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr)); gap: 0.75rem; margin-bottom: 0.75rem; }
.stat { padding: 0.75rem; text-align: center; }
.stat b { display: block; font-size: 1.4rem; font-weight: 800; }
.stat span { font-size: var(--fs-xs); opacity: 0.6; }
.tabs { display: flex; gap: 0.25rem; margin-bottom: 0.75rem; overflow-x: auto; }
.tabs button { flex: 0 0 auto; padding: 0.45rem 0.9rem; border-radius: 0.6rem; font-size: var(--fs-sm); font-weight: 600; border: none; background: transparent; color: inherit; opacity: 0.6; cursor: pointer; min-height: var(--tap); }
.tabs button.active { background: var(--acc); color: #fff; opacity: 1; }
table { width: 100%; border-collapse: collapse; }
td, th { border: 1px solid var(--line); padding: 6px 10px; text-align: left; font-size: var(--fs-xs); }
th { text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.6; }
.secrow { display: flex; flex-direction: column; gap: 0.375rem; padding: 0.625rem 0; border-bottom: 1px dashed var(--line); }
.secrow .meta b { display: block; font-size: var(--fs-sm); }
.row { display: flex; gap: 0.5rem; }
.btn-sm { min-height: 36px; }
.srow, .ev { padding: 0.3rem 0; border-bottom: 1px dashed var(--line); font-size: var(--fs-xs); display: flex; gap: 0.5rem; align-items: center; }
small { color: var(--mut); }
</style>
