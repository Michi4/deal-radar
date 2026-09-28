<template>
  <div class="pager">
    <button class="btn iconbtn" @click="$emit('go', page - 1)" :disabled="page <= 0" aria-label="previous page" title="Previous page">
      <ArrowLeft :size="16" />
    </button>
    <span class="pinfo">{{ page + 1 }}/{{ pages }}</span>
    <button class="btn iconbtn" @click="$emit('go', page + 1)" :disabled="page >= pages - 1" aria-label="next page" title="Next page">
      <ArrowRight :size="16" />
    </button>
    <input v-model.number="goto" class="inp paging" type="number" min="1" :max="pages" placeholder="page #" aria-label="go to page" title="Type a page number" @keyup.enter="jump" />
    <button class="btn" @click="jump">go</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ArrowLeft, ArrowRight } from 'lucide-vue-next';

const props = defineProps<{ page: number; pages: number }>();
const emit = defineEmits(['go']);
const goto = ref<number | null>(null);
function jump() {
  if (goto.value != null && goto.value >= 1 && goto.value <= props.pages) emit('go', goto.value - 1);
  goto.value = null;
}
</script>

<style scoped>
.pager { display: flex; gap: 0.5rem; align-items: center; justify-content: center; margin: 0.75rem 0; }
.pinfo { font-size: var(--fs-sm); }
.paging { max-width: 5rem; }
.iconbtn { min-width: var(--tap); justify-content: center; }
</style>
