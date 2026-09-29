import { defineStore } from 'pinia';
import { api } from '@/api';
import type { JobState, Scored, SearchResult } from '@/types';
import { useUi } from './ui';

export interface Filters {
  min: string; max: string; black: string; req: string;
  minMatch: number; warnT: number; blockT: number;
  wMatch: number; wValue: number; wRisk: number; wComp: number;
  maxpages: string; limitN: string; deepN: string;
  catSel: string; catKa: string; catVi: string; catAuto: boolean;
  locQ: string; locR: string;
  fOcr: boolean; fBench: boolean; fVision: boolean; fDet: boolean;
  fPick: boolean; fShip: boolean;
}
export const defaultFilters = (): Filters => ({
  min: '', max: '', black: '', req: '', minMatch: 12, warnT: 35, blockT: 100,
  wMatch: 35, wValue: 35, wRisk: 20, wComp: 10,
  maxpages: '', limitN: '', deepN: '150',
  catSel: '', catKa: '', catVi: '', catAuto: true, locQ: '', locR: '',
  fOcr: true, fBench: true, fVision: true, fDet: true, fPick: false, fShip: false
});

const ABORTS = new Map<string, number>();

export const useSearch = defineStore('search', {
  state: () => ({
    results: [] as Scored[],
    hidden: [] as Scored[],
    sid: null as string | null,
    searched: false,
    jobs: new Map<string, JobState>(),
    followed: null as string | null,
    running: false,
    lastDurationS: 0,
    filters: defaultFilters(),
    sources: new Set<string>(),
    hideKind: { want: true, parts: true, acc: true } as Record<string, boolean>,
    hideLanes: new Set<string>(),
    showHidden: false,
    sort: 'score' as string,
    sortDir: 1,
    perPage: 20 as number,
    page: 0,
    maxRisk: 100 as number,
    minScore: 0 as number,
    maxDist: null as number | null,
    compare: new Set<string>(),
    favs: new Set<string>(),
    visibleIds: [] as string[],
    statusHtml: '' as string,
    appliedNl: null as null | { keywords: string; models?: string[]; blacklist?: string[]; required?: string[]; category?: string; subs?: string[] }
  }),
  actions: {
    liveSources(): string[] {
      return [...this.sources];
    },
    async loadFavs() {
      try {
        const f = await api<{ listing_id: string }[]>('/favorites', {}, 1);
        this.favs = new Set((f || []).map((x) => x.listing_id));
      } catch { /* offline: keep empty */ }
    },
    async toggleFav(id: string) {
      const ui = useUi();
      try {
        if (this.favs.has(id)) {
          await api(`/favorites/${encodeURIComponent(id)}`, { method: 'DELETE' });
          this.favs.delete(id);
        } else {
          await api(`/favorites/${encodeURIComponent(id)}`, { method: 'POST' });
          this.favs.add(id);
        }
        this.favs = new Set(this.favs);
      } catch (e) { ui.toastErr(e); }
    },
    toggleCompare(id: string) {
      if (this.compare.has(id)) this.compare.delete(id);
      else this.compare.add(id);
      this.compare = new Set(this.compare);
    },
    async jobOp(sid: string, op: 'stop' | 'pause' | 'resume') {
      const ui = useUi();
      if (op === 'stop') ABORTS.set(sid, Date.now());
      try {
        await api(`/searches/${encodeURIComponent(sid)}/${op}`, { method: 'POST' });
        ui.toast(op === 'stop' ? 'stopping…' : op === 'pause' ? 'paused' : 'resumed');
      } catch (e) { ui.toastErr(e); }
    },
    leave(sid: string) {
      this.jobs.delete(sid);
      ABORTS.delete(sid);
      for (const [k, t] of ABORTS) if (Date.now() - t > 600000) ABORTS.delete(k);
      if (this.followed === sid) this.followed = null;
      if (!this.jobs.size) this.running = false;
      this.jobs = new Map(this.jobs);
    },
    async poll(sid: string, label: string): Promise<SearchResult | null> {
      const t0 = Date.now();
      this.running = true;
      this.followed = sid;
      this.jobs.set(sid, { done: 0, total: '?', detail: 'starting', label });
      this.jobs = new Map(this.jobs);
      let dark = 0;
      for (;;) {
        if (ABORTS.has(sid)) { this.leave(sid); return null; }
        let r: SearchResult;
        try {
          r = await api<SearchResult>(`/searches/${encodeURIComponent(sid)}`);
        } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          if (/login required|auth session/i.test(msg)) { this.leave(sid); return null; }
          dark++;
          if (dark > 40) { this.leave(sid); return null; }
          await new Promise((x) => setTimeout(x, /429/.test(msg) ? 10000 : 3000));
          continue;
        }
        dark = 0;
        if (r.status === 'running') {
          const prev = this.jobs.get(sid);
          this.jobs.set(sid, {
            done: r.done || 0, total: r.total || '?', detail: r.detail || '',
            control: r.control || 'run', label: prev?.label || sid
          });
          this.jobs = new Map(this.jobs);
          if (sid !== this.followed) { await new Promise((x) => setTimeout(x, 3000)); continue; }
          const part = r.partial;
          if (part && part.n_results) {
            this.results = part.results || [];
            this.hidden = [];
            this.sid = sid;
          }
          await new Promise((x) => setTimeout(x, 3000));
          continue;
        }
        this.running = false;
        const mine = sid === this.followed;
        this.leave(sid);
        if (!mine) return null;
        this.searched = true;
        this.hidden = r.filtered || [];
        this.lastDurationS = Math.round((Date.now() - t0) / 1000);
        return r;
      }
    }
  }
});
