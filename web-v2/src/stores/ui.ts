import { defineStore } from 'pinia';
import { api, friendly } from '@/api';

export const useUi = defineStore('ui', {
  state: () => ({
    theme: (localStorage.getItem('drt') || 'dark') as string,
    view: (localStorage.getItem('drv') || 'grid') as string,
    toasts: [] as { id: number; text: string }[],
    mode: (localStorage.getItem('drmode') || 'nl') as string
  }),
  actions: {
    initTheme() {
      if (this.theme !== 'dark' && this.theme !== 'light') this.theme = 'dark';
      document.documentElement.classList.toggle('dark', this.theme === 'dark');
    },
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.classList.toggle('dark', this.theme === 'dark');
      localStorage.setItem('drt', this.theme);
    },
    setView(v: string) {
      this.view = v;
      localStorage.setItem('drv', v);
    },
    setMode(m: string) {
      this.mode = m;
      localStorage.setItem('drmode', m);
    },
    toast(text: string) {
      const id = Date.now() + Math.random();
      this.toasts.unshift({ id, text });
      this.toasts = this.toasts.slice(0, 3);
      setTimeout(() => { this.toasts = this.toasts.filter((t) => t.id !== id); }, 9000);
    },
    toastErr(e: unknown) {
      this.toast(friendly(e));
    }
  }
});

export async function apiOrToast<T>(path: string, opts?: RequestInit, retries?: number): Promise<T | null> {
  const ui = useUi();
  try {
    return await api<T>(path, opts, retries);
  } catch (e) {
    ui.toastErr(e);
    return null;
  }
}
