import { createRouter, createWebHistory } from 'vue-router';

export default createRouter({
  // dev serves at /, prod preview mounts at /v2 (cutover to / later)
  history: createWebHistory(import.meta.env.DEV ? '/' : '/v2/'),
  routes: [
    { path: '/', name: 'search', component: () => import('@/views/SearchView.vue') },
    { path: '/saved', name: 'saved', component: () => import('@/views/SavedView.vue') },
    { path: '/watches', name: 'watches', component: () => import('@/views/WatchesView.vue') },
    { path: '/compare', name: 'compare', component: () => import('@/views/CompareView.vue') },
    { path: '/store', name: 'store', component: () => import('@/views/StoreView.vue') },
    { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue') },
    { path: '/lab', name: 'lab', component: () => import('@/views/LabView.vue') },
    { path: '/admin', name: 'admin', component: () => import('@/views/AdminView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') }
  ],
  scrollBehavior: () => ({ top: 0 })
});
