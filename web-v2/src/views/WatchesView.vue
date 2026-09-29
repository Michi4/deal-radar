<template>
  <div>
    <h2>Watches <small>auto re-polled · survive restarts · notify on new hits &amp; drops</small></h2>
    <div class="panel">
      <form @submit.prevent="mkWatch" class="fgrid">
        <label class="fld"><span>watch query</span><input v-model="q" class="inp" placeholder="e.g. ThinkPad X1 under €800" /></label>
        <label class="fld"><span title="Maximum price in EUR">max €</span><input v-model="maxP" class="inp" type="number" placeholder="no max" /></label>
        <label class="fld"><span title="Only notify drops of at least this %">drop % ≥</span><input v-model="dropP" class="inp" type="number" placeholder="any" /></label>
        <label class="fld"><span title="Only notify new matches below this risk %">risk ≤ %</span><input v-model="riskP" class="inp" type="number" placeholder="any" /></label>
        <label class="fld"><span title="Poll interval in minutes">re-check every (min)</span><input v-model.number="intMin" class="inp" type="number" min="1" value="30" /></label>
        <label class="fld"><span title="Location for distance-aware watches">location</span><input v-model="locQ" class="inp" placeholder="optional" /></label>
        <label class="fld"><span title="Radius in km (empty = unlimited)">radius km</span><input v-model="locR" class="inp" type="number" min="1" placeholder="any" /></label>
        <label class="fld"><span>&nbsp;</span><button type="submit" class="btn btn-primary">+ Watch</button></label>
      </form>
      <div class="row checks">
        <label class="ck" :class="{ on: nNew }"><input type="checkbox" v-model="nNew" /> new hits</label>
        <label class="ck" :class="{ on: nPrice }"><input type="checkbox" v-model="nPrice" /> price drops</label>
        <label class="ck" :class="{ on: nDesc }"><input type="checkbox" v-model="nDesc" /> desc changes</label>
        <label class="ck" :class="{ on: nImg }"><input type="checkbox" v-model="nImg" /> image changes</label>
      </div>
      <small>{{ channels }}</small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '@/api';
import { useUi } from '@/stores/ui';
import { useSearch } from '@/stores/search';

const ui = useUi();
const search = useSearch();
const q = ref('');
const maxP = ref('');
const dropP = ref('');
const riskP = ref('');
const intMin = ref(30);
const nNew = ref(true);
const nPrice = ref(true);
const nDesc = ref(false);
const nImg = ref(false);
const locQ = ref('');
const locR = ref('');
const channels = ref('');

async function mkWatch() {
  const mins = Math.max(1, intMin.value || 30);
  const notifyOn: string[] = [];
  if (nNew.value) notifyOn.push('new_top');
  if (nPrice.value) notifyOn.push('price_drop');
  if (nDesc.value) notifyOn.push('desc_change');
  if (nImg.value) notifyOn.push('image_change');
  const rules: Record<string, unknown>[] = [];
  if (nPrice.value && +dropP.value > 0) rules.push({ kind: 'price_drop', min_drop_pct: +dropP.value });
  if (nNew.value && +riskP.value > 0) rules.push({ kind: 'new_match', max_risk: +riskP.value / 100 });
  const body = {
    keywords: q.value || 'watch', sources: [...search.sources],
    hard: maxP.value ? { max_price: +maxP.value } : {},
    location: locQ.value.trim(), radius_km: locR.value === '' ? undefined : Math.max(1, +locR.value || 50),
    watch: true, poll_interval_s: mins * 60, notify_on: notifyOn, notify_rules: rules
  };
  const r = await api<{ id?: string; error?: string }>('/searches', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  ui.toast(r?.id ? 'Watch created: ' + (q.value || 'watch') : `watch failed: ${r?.error || '?'}`);
}
onMounted(async () => {
  try {
    const n = await api<{ channels: { type: string; target?: string }[] }>('/notifications/status');
    channels.value = 'alert channels: ' + (n?.channels || []).map((c: { type: string; target?: string }) => c.type + (c.target || '')).join(', ');
  } catch { /* offline */ }
  if (search.lastDurationS > 0) intMin.value = Math.max(30, Math.ceil(search.lastDurationS / 60));
});
</script>

<style scoped>
h2 small { opacity: 0.6; font-weight: 400; }
.fgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr)); gap: 0.625rem; }
.fld { display: flex; flex-direction: column; gap: 0.25rem; font-size: var(--fs-xs); font-weight: 700; text-transform: uppercase; }
.fld .inp { text-transform: none; font-weight: 400; }
.row.checks { display: flex; gap: 0.375rem; margin-top: 0.625rem; flex-wrap: wrap; }
.ck { display: inline-flex; align-items: center; gap: 0.25rem; border: 1px solid var(--line); border-radius: 99px; padding: 4px 10px; font-size: var(--fs-xs); cursor: pointer; }
.ck.on { background: var(--acc-soft); border-color: var(--acc); }
small { color: var(--mut); }
</style>
