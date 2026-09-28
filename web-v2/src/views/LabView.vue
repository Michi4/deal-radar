<template>
  <div>
    <h2>Lab <small>describe a driver or enrichment · AI builds, tests &amp; hot-loads it</small></h2>
    <div class="panel">
      <h3>AI Lab — chat-built plugins</h3>
      <small>Tip: coding agents read <b>docs/DRIVER_AUTHORING.md</b> (interfaces, categories, pagination contract) — just describe what you want.</small>
      <div><small>{{ statusLine }}</small></div>
      <div class="row">
        <select v-model="kind" class="inp kindsel" aria-label="plugin kind">
          <option value="enricher">enricher</option><option value="driver">driver</option>
        </select>
        <input v-model="text" class="inp grow" placeholder="e.g. flag listings with missing charger as incomplete" aria-label="build instruction" @keyup.enter="build" />
        <button class="btn btn-primary" :disabled="busy || !text.trim()" @click="build">Build</button>
      </div>
      <div v-if="job">
        <div class="stages">
          <span v-for="s in stages" :key="s" class="chip" :class="{ active: doneStages.includes(s) }">{{ s.replace('_', ' ') }}</span>
        </div>
        <div v-for="(l, i) in job.log || []" :key="i"><small>{{ l.stage }} — {{ l.msg }}</small></div>
        <div v-if="showResult" class="mt">
          <div v-if="job && job.status === 'done'">Built, checked, hot-loaded: <b>{{ resId }}</b></div>
          <div v-else class="err">failed: {{ resErr }}</div>
          <div class="row mt">
            <input v-model="followup" class="inp grow" placeholder="step in: fix, change, extend…" aria-label="follow-up instruction" @keyup.enter="sendFollow" />
            <button class="btn btn-primary" @click="sendFollow">send follow-up</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { api } from '@/api';
import { useUi } from '@/stores/ui';

const ui = useUi();
const kind = ref('enricher');
const text = ref('');
const followup = ref('');
const busy = ref(false);
const statusLine = ref('');
const job = ref<{ id?: string; status?: string; stage?: string; log?: { stage: string; msg: string }[]; result?: { id?: string; error?: string } } | null>(null);
const showResult = ref(false);
const resId = ref('');
const resErr = ref('');
const stages = ['prompting', 'waiting_model', 'validating', 'saving', 'contract_check', 'done'];
const doneStages = ref<string[]>([]);
let stop = false;

async function loadStatus() {
  try {
    const st = await api<{ enabled: boolean; enrichers: string[] }>('/lab/status');
    statusLine.value = `${st?.enabled ? 'enabled' : 'disabled (LAB_ENABLED=0)'} · enrichers: ${(st?.enrichers || []).join(', ')}`;
  } catch { statusLine.value = ''; }
}
async function build() {
  if (!text.value.trim()) { ui.toast('describe what to build first'); return; }
  busy.value = true;
  job.value = null; showResult.value = false;
  const r = await api<{ id: string }>('/lab/build', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: kind.value, instruction: text.value })
  });
  if (r?.id) await follow(r.id);
  else busy.value = false;
}
async function follow(jid: string) {
  stop = false;
  for (;;) {
    const r = await api<{ status: string; stage?: string; log?: { stage: string; msg: string }[]; result?: { id?: string; error?: string } }>(`/lab/build/${encodeURIComponent(jid)}`, {}, 1);
    if (!r) { busy.value = false; return; }
    job.value = r;
    doneStages.value = (r.log || []).map((l: { stage: string }) => l.stage);
    if (r.status !== 'running') {
      showResult.value = true;
      resId.value = r.result?.id || '';
      resErr.value = r.result?.error || r.status;
      busy.value = false;
      return;
    }
    await new Promise((x) => setTimeout(x, 3000));
    if (stop) return;
  }
}
async function sendFollow() {
  if (!job.value || !followup.value.trim()) { ui.toast('write a follow-up first'); return; }
  const jid = job.value.id || '';
  const r = await api<{ id: string }>('/lab/follow', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jid, followup: followup.value })
  });
  if (r?.id) { busy.value = true; showResult.value = false; await follow(r.id); }
}
onMounted(loadStatus);
onUnmounted(() => { stop = true; });
</script>

<style scoped>
h2 small { opacity: 0.6; font-weight: 400; }
h3 { margin: 0 0 0.375rem; }
.row { display: flex; gap: 0.5rem; margin-top: 0.625rem; }
.grow { flex: 1; } .kindsel { max-width: 9rem; }
.stages { display: flex; gap: 0.375rem; flex-wrap: wrap; margin: 0.625rem 0; }
.chip { background: var(--bg2); border: 1px solid var(--line); border-radius: 99px; padding: 2px 10px; font-size: var(--fs-xs); }
.chip.active { background: var(--acc-soft); border-color: var(--acc); }
.mt { margin-top: 0.625rem; }
.err { color: #dc2626; }
small { color: var(--mut); }
</style>
