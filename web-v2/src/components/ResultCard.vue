<template>
  <div class="card res" :class="{ picked }">
    <div class="thumbwrap" v-if="imgs.length">
      <img class="thumb" loading="lazy" :src="safeUrl(imgs[idx % imgs.length])" @error="imgGone" alt="" />
      <button v-if="imgs.length > 1" class="thumbnav l" @click.stop="idx = (idx - 1 + imgs.length) % imgs.length" aria-label="previous photo">
        <ChevronLeft :size="18" />
      </button>
      <button v-if="imgs.length > 1" class="thumbnav r" @click.stop="idx = (idx + 1) % imgs.length" aria-label="next photo">
        <ChevronRight :size="18" />
      </button>
    </div>
    <div v-else class="thumbwrap empty" aria-hidden="true"><ImageOff :size="22" /></div>
    <div class="body">
      <span v-if="best" class="best-badge">best value</span>
      <h4 :title="fullTitle">{{ s.listing.title || '(no title)' }}</h4>
      <div>
        <span class="price">{{ priceTxt }}</span>
        <span v-if="totalTxt" class="total" :title="`including ${shipTxt} shipping`">{{ totalTxt }} all-in</span>
        <span class="badge" :class="'risk-' + (s.risk?.severity || 'low')" :title="riskTip">{{ riskPct }}% risk</span>
      </div>
      <div class="lane" :title="laneTip">{{ laneTxt }}</div>
      <div v-if="(s.also_on || []).length" class="lane">also on: {{ alsoTxt }}</div>
      <div class="row">
        <button class="btn btn-sm" :class="picked ? 'btn-primary' : ''" @click.stop="$emit('compare')" :aria-pressed="picked" title="Side-by-side compare (unlimited items)">
          <ArrowLeftRight :size="15" />{{ picked ? 'picked' : 'compare' }}
        </button>
        <button class="btn btn-sm iconbtn" @click.stop="$emit('fav')" :aria-label="isFav ? 'remove favorite' : 'save favorite'" title="Track this product (price/text/photo history)">
          <Star :size="15" :fill="isFav ? 'currentColor' : 'none'" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { ArrowLeftRight, ChevronLeft, ChevronRight, ImageOff, Star } from 'lucide-vue-next';
import { safeUrl } from '@/api';
import type { Scored } from '@/types';

const props = defineProps<{ s: Scored; best?: boolean; picked?: boolean; isFav?: boolean }>();
defineEmits(['compare', 'fav', 'open']);
const idx = ref(0);
const imgs = computed(() => props.s.listing.images || []);
const fullTitle = computed(() => props.s.listing.title || '');
const shipCost = computed(() => {
  const v = props.s.listing.shipping_cost;
  return typeof v === 'number' && v > 0 ? v : 0;
});
const priceTxt = computed(() => `${props.s.listing.price ?? '?'} ${props.s.listing.currency || ''}`);
const totalTxt = computed(() => {
  const p = props.s.listing.price;
  if (p == null || !shipCost.value) return '';
  const t = Math.round((p + shipCost.value) * 100) / 100;
  return `${t} ${props.s.listing.currency || ''}`;
});
const shipTxt = computed(() => `${shipCost.value} ${props.s.listing.currency || ''} shipping`);
const riskPct = computed(() => Math.round((props.s.risk?.score ?? 0) * 100));
const riskTip = computed(() => `Scam/risk score with evidence — see details. ${(props.s.why || []).slice(0, 2).join('; ')}`);
// Human lane line: never raw score floats on the card (the tooltip keeps them).
const laneName: Record<string, string> = { top: 'Top match', good: 'Good', review: 'Check first', hidden: 'Hidden' };
const laneTxt = computed(() => {
  const l = props.s.listing;
  const dist = l.distance_km != null ? ` · ${Math.round(l.distance_km)} km` : '';
  return `${laneName[props.s.lane || ''] || props.s.lane || ''} · ${l.source || ''} · ${l.location || ''}${dist}`.replace(/ · $/, '');
});
const laneTip = computed(() => `score ${(props.s.final_score ?? 0).toFixed(2)} · match ${(props.s.match_score ?? 0).toFixed(2)}`);
const alsoTxt = computed(() => (props.s.also_on || []).slice(0, 3)
  .map((a) => `${a.source} ${a.price ?? '?'}€`).join(' · '));
function imgGone(e: Event) { (e.target as HTMLElement).remove(); }
</script>

<style scoped>
.res { cursor: pointer; }
.body { padding: 0.625rem; display: flex; flex-direction: column; gap: 0.375rem; }
.body h4 { margin: 0; font-size: var(--fs-sm); overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.thumbwrap { position: relative; aspect-ratio: 4/3; background: var(--bg2); }
.thumbwrap.empty { display: flex; align-items: center; justify-content: center; color: var(--mut); opacity: 0.5; }
.thumb { width: 100%; height: 100%; object-fit: cover; display: block; }
.total { font-size: var(--fs-xs); font-weight: 700; color: var(--mut); background: var(--bg2); border-radius: 99px; padding: 2px 8px; margin-left: 0.375rem; white-space: nowrap; }
.thumbnav { position: absolute; top: 40%; background: rgba(0,0,0,0.55); border: none; padding: 4px 6px; color: #fff; border-radius: 0.375rem; cursor: pointer; display: inline-flex; }
.thumbnav.l { left: 4px; } .thumbnav.r { right: 4px; }
.row { display: flex; gap: 0.375rem; margin-top: 0.375rem; }
.btn-sm { min-height: 36px; padding: 0.375rem 0.625rem; }
.best-badge { display: inline-block; background: var(--acc); color: #fff; font-size: var(--fs-xs); font-weight: 800; border-radius: 99px; padding: 2px 10px; margin-bottom: 2px; width: fit-content; }
.risk-low { background: #16a34a; color: #fff; } .risk-medium { background: #d97706; color: #fff; } .risk-high { background: #dc2626; color: #fff; }
</style>
