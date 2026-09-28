<template>
  <div class="min-h-screen flex flex-col">
    <!-- Desktop top bar: logo left, nav centered, theme right -->
    <header class="topbar hidden md:flex">
      <router-link to="/" class="logo" aria-label="deal-radar home">
        <Compass :size="22" class="logo-ic" /><span>deal-radar</span>
      </router-link>
      <nav class="topnav" aria-label="primary">
        <router-link v-for="n in nav" :key="n.to" :to="n.to" :title="n.tip">
          <component :is="n.icon" :size="16" />{{ n.label }}
          <span v-if="n.badge" class="navbadge">{{ n.badge }}</span>
        </router-link>
      </nav>
      <div class="topright">
        <button class="iconbtn" :title="themeTip" @click="ui.toggleTheme()" aria-label="toggle night mode">
          <Moon v-if="isDark" :size="18" /><Sun v-else :size="18" />
        </button>
        <router-link to="/admin" class="adminlink">admin</router-link>
      </div>
    </header>
    <!-- Mobile top bar: logo left, night mode + admin right -->
    <header class="topbar flex md:hidden">
      <router-link to="/" class="logo" aria-label="deal-radar home">
        <Compass :size="20" class="logo-ic" /><span>dr</span>
      </router-link>
      <div class="topright">
        <button class="iconbtn" @click="ui.toggleTheme()" aria-label="toggle night mode">
          <Moon v-if="isDark" :size="18" /><Sun v-else :size="18" />
        </button>
        <router-link to="/admin" class="adminlink">admin</router-link>
      </div>
    </header>

    <main class="wrap">
      <router-view />
    </main>

    <footer class="foot">
      <a href="https://github.com/Michi4/deal-radar" target="_blank" rel="noopener">deal-radar on GitHub</a>
      <span> · finds used products, live</span>
    </footer>

    <!-- Mobile bottom nav -->
    <nav class="bottomnav md:hidden" aria-label="primary mobile">
      <router-link v-for="n in mobilenav" :key="n.to" :to="n.to" :title="n.tip">
        <component :is="n.icon" :size="20" /><span>{{ n.label }}</span>
      </router-link>
    </nav>

    <div class="toasts" aria-live="polite">
      <div v-for="t in ui.toasts" :key="t.id" class="toast">{{ t.text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import {
  Compass, Search, Star, Bell, Columns2, Store, FlaskConical, History, Moon, Sun
} from 'lucide-vue-next';
import { useUi } from '@/stores/ui';
import { useSearch } from '@/stores/search';

const ui = useUi();
const search = useSearch();
const route = useRoute();
void route;
const isDark = computed(() => ui.theme === 'dark');
const themeTip = 'Toggle night mode (saved on this device)';

const nav = computed(() => [
  { to: '/', label: 'Search', icon: Search, tip: 'Natural language or keyword search across marketplaces' },
  { to: '/saved', label: 'Saved', icon: Star, tip: 'Tracked favorites with price/change history', badge: search.favs.size || '' },
  { to: '/watches', label: 'Watches', icon: Bell, tip: 'Background re-polls with alert rules' },
  { to: '/compare', label: 'Compare', icon: Columns2, tip: 'Side-by-side spec, price and risk', badge: search.compare.size || '' },
  { to: '/store', label: 'Store', icon: Store, tip: 'Install drivers and enrichers' },
  { to: '/lab', label: 'Lab', icon: FlaskConical, tip: 'Describe a plugin, AI builds and hot-loads it' },
  { to: '/history', label: 'Searches', icon: History, tip: 'Every past search, reopenable instantly' }
]);
const mobilenav = computed(() => nav.value.slice(0, 6));
</script>

<style scoped>
.topbar { position: sticky; top: 0; z-index: 40; align-items: center; gap: 1rem; padding: 0.625rem 1rem; background: var(--bg); border-bottom: 1px solid var(--line); }
.logo { display: flex; align-items: center; gap: 0.5rem; font-weight: 800; font-size: var(--fs-lg); color: var(--acc-d); text-decoration: none; }
.dark .logo { color: var(--acc); }
.logo-ic { color: var(--acc); }
.topnav { flex: 1; display: flex; justify-content: center; gap: 0.25rem; flex-wrap: wrap; }
.topnav a { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.5rem 0.75rem; border-radius: 0.6rem; text-decoration: none; color: var(--mut); font-weight: 600; min-height: var(--tap); }
.topnav a.router-link-active { color: var(--acc-d); background: var(--acc-soft); }
.dark .topnav a.router-link-active { color: var(--acc); }
.topright { display: flex; align-items: center; gap: 0.5rem; margin-left: auto; }
.iconbtn { display: inline-flex; align-items: center; justify-content: center; min-width: var(--tap); min-height: var(--tap); border-radius: 0.7rem; border: none; background: transparent; color: inherit; cursor: pointer; }
.adminlink { color: var(--mut); text-decoration: none; font-weight: 600; padding: 0.5rem; }
.wrap { width: 100%; max-width: 80rem; margin: 0 auto; padding: 1rem 1rem 5rem; }
.foot { text-align: center; padding: 1.4rem 1rem 5rem; opacity: 0.55; font-size: var(--fs-xs); }
.foot a { color: inherit; text-decoration: none; }
.bottomnav { position: fixed; bottom: 0; left: 0; right: 0; z-index: 40; display: flex; background: var(--bg); border-top: 1px solid var(--line); padding-bottom: env(safe-area-inset-bottom); }
/* unlayered author CSS beats Tailwind layered utilities, so responsive hide needs its own query */
@media (min-width: 768px) { .bottomnav { display: none; } }
.bottomnav a { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 0.5rem 0; color: var(--mut); text-decoration: none; font-size: var(--fs-xs); min-height: var(--tap); }
.bottomnav a.router-link-active { color: var(--acc); }
.navbadge { background: var(--acc); color: #fff; border-radius: 99px; font-size: var(--fs-xs); padding: 0 6px; font-weight: 700; }
.toasts { position: fixed; right: 1rem; bottom: 5rem; z-index: 60; display: flex; flex-direction: column; gap: 0.5rem; max-width: min(90vw, 24rem); }
.toast { background: var(--card); border: 1px solid var(--line); border-radius: 0.75rem; padding: 0.625rem 0.875rem; box-shadow: 0 8px 24px rgba(0,0,0,0.18); }
</style>
