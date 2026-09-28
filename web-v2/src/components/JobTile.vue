<template>
  <div class="card jobtile">
    <div class="body">
      <h4>{{ job.label }}</h4>
      <div class="lane" :title="job.detail">{{ job.detail || 'starting' }}</div>
      <div class="pbar" role="progressbar" :aria-valuenow="pct"><i :style="{ width: pct + '%' }"></i></div>
      <div class="row">
        <button class="btn btn-sm btn-primary" @click="$emit('open')" title="Follow this search live">open</button>
        <button class="btn btn-sm iconbtn" @click="$emit('pause')" aria-label="pause search" title="Pause (resumable)">
          <Pause :size="15" />
        </button>
        <button class="btn btn-sm iconbtn" @click="$emit('resume')" aria-label="resume search" title="Resume">
          <Play :size="15" />
        </button>
        <button class="btn btn-sm iconbtn" @click="$emit('stop')" aria-label="stop search" title="Stop now">
          <Square :size="15" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Pause, Play, Square } from 'lucide-vue-next';
import type { JobState } from '@/types';

const props = defineProps<{ job: JobState }>();
defineEmits(['open', 'pause', 'resume', 'stop']);
const pct = computed(() => {
  const t = Number(props.job.total);
  if (t > 0) return Math.min(100, Math.round((100 * Number(props.job.done || 0)) / t));
  return 8;
});
</script>

<style scoped>
.jobtile .body { padding: 0.625rem; display: flex; flex-direction: column; gap: 0.375rem; }
.body h4 { margin: 0; font-size: var(--fs-sm); }
.pbar { height: 6px; background: var(--line); border-radius: 99px; overflow: hidden; }
.pbar i { display: block; height: 100%; background: var(--acc); }
.row { display: flex; gap: 0.375rem; }
.btn-sm { min-height: 36px; padding: 0.375rem 0.625rem; }
</style>
