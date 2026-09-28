<template>
  <div class="sheetwrap" @click.self="$emit('close')">
    <div class="sheet" role="dialog" aria-label="listing details">
      <div class="row">
        <button class="btn" @click="$emit('close')" title="Back to results"><ArrowLeft :size="15" /> back</button>
        <button class="btn" @click="toggleFav" :title="isFav ? 'Stop tracking' : 'Track this product'"><Star :size="15" :fill="isFav ? 'currentColor' : 'none'" /> {{ isFav ? 'saved' : 'save' }}</button>
        <a v-if="url" :href="url" target="_blank" rel="noopener"><button class="btn btn-primary" title="Open the original listing">open original <ExternalLink :size="15" /></button></a>
      </div>
      <div v-if="loading" class="skel">loading details…</div>
      <div v-else-if="d">
        <h2>{{ d.listing.title || '(no title)' }}</h2>
        <div><span class="price">{{ d.listing.price ?? '?' }} {{ d.listing.currency || '' }}</span>
          <span class="badge" :class="'risk-' + (d.risk?.severity || 'low')">{{ Math.round((d.risk?.score ?? 0) * 100) }}% risk</span></div>
        <div class="lane">{{ d.listing.location || '' }} · {{ d.listing.source }} · seller: {{ d.listing.seller?.name || '—' }} · pickup {{ d.listing.pickup_available ? 'yes' : '—' }} · shipping {{ d.listing.shipping_available ? 'yes' : '—' }}</div>
        <div class="thumbs">
          <img v-for="(u, i) in d.listing.images || []" :key="i" :src="safeUrl(u)" loading="lazy" @error="imgGone" alt="" />
        </div>
        <p class="desc">{{ d.listing.description || 'no description' }}</p>
        <div v-if="(d.why || []).length" class="panel"><div class="eyebrow">why this score</div><ul><li v-for="(w, i) in d.why" :key="i">{{ w }}</li></ul></div>
        <div class="panel"><div class="eyebrow">change history</div><div id="vhist"><small>{{ histNote }}</small></div></div>
      </div>
      <div v-else class="empty">details unavailable</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ArrowLeft, ExternalLink, Star } from 'lucide-vue-next';
import { api, safeUrl } from '@/api';
import { useSearch } from '@/stores/search';
import type { Scored } from '@/types';

const props = defineProps<{ id: string }>();
defineEmits(['close']);
const search = useSearch();
const d = ref<Scored | null>(null);
const loading = ref(true);
const histNote = ref('loading…');
const url = ref('');
const isFav = ref(false);

function imgGone(e: Event) { (e.target as HTMLElement).remove(); }
async function toggleFav() { await search.toggleFav(props.id); isFav.value = search.favs.has(props.id); }

onMounted(async () => {
  isFav.value = search.favs.has(props.id);
  const found = search.results.find((s) => s.listing.id === props.id)
    || search.hidden.find((s) => s.listing.id === props.id);
  if (found) {
    d.value = found;
    url.value = safeUrl(found.listing.url || '');
  }
  loading.value = false;
  try {
    const h = await api<{ history: { kind: string; old: string; new: string }[] }>(`/listings/${encodeURIComponent(props.id)}/history`);
    histNote.value = (h?.history || []).map((x) => `${x.kind}: ${String(x.old).slice(0, 60)} → ${String(x.new).slice(0, 60)}`).join('\n') || 'no changes tracked yet';
  } catch { histNote.value = 'history unavailable'; }
});
</script>

<style scoped>
.sheetwrap { position: fixed; inset: 0; z-index: 50; background: rgba(0,0,0,0.5); display: flex; justify-content: flex-end; }
.sheet { background: var(--bg); width: min(34rem, 100%); height: 100%; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.625rem; }
.row { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.thumbs { display: flex; gap: 0.375rem; overflow-x: auto; }
.thumbs img { height: 7rem; border-radius: 0.5rem; }
.desc { white-space: pre-wrap; font-size: var(--fs-sm); }
ul { margin: 0; padding-left: 1.25rem; font-size: var(--fs-sm); }
.skel, .empty { opacity: 0.6; padding: 1rem; }
.risk-low { background: #16a34a; color: #fff; } .risk-medium { background: #d97706; color: #fff; } .risk-high { background: #dc2626; color: #fff; }
</style>
