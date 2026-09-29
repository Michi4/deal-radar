// Filter/sort worker: keeps the main thread at 60fps with 10k+ results.
// In: { items, opts }. Out: { ids } — ordered visible listing ids.
export interface FilterOpts {
  hideKind: Record<string, boolean>;
  hideLanes: string[];
  maxRisk: number;
  minScore: number;
  maxDist: number | null;
  min: number | null;
  max: number | null;
  black: string[];
  req: string[];
  matchW: number; valueW: number; riskW: number; compW: number;
  sort: string;
  dir: number;
}

interface Item {
  listing: { id: string; title?: string; description?: string; price?: number | null; source?: string; distance_km?: number | null };
  risk?: { score?: number };
  final_score?: number;
  lane?: string;
  why?: unknown;
  deal_dna?: Record<string, number>;
  enrichments?: { field: string; value: number }[];
}

const benchOf = (s: Item): number => {
  const b = (s.enrichments || []).find((e) => e.field === 'cpu_benchmark' || e.field === 'gpu_benchmark');
  return b ? b.value : 0;
};
const gpuOf = (s: Item): number => {
  const b = (s.enrichments || []).find((e) => e.field === 'gpu_benchmark');
  return b ? b.value : 0;
};

self.onmessage = (e: MessageEvent<{ items: Item[]; opts: FilterOpts }>) => {
  const { items, opts } = e.data;
  const t = opts.matchW + opts.valueW + opts.riskW + opts.compW || 1;
  const out: { id: string; key: number }[] = [];
  let unknown = 0;
  for (const s of items) {
    const l = s.listing;
    const why = JSON.stringify(s.why || '');
    if (opts.hideKind.want && /buy-request/.test(why)) continue;
    if (opts.hideKind.parts && /parts\/repair/.test(why)) continue;
    if (opts.hideKind.acc && /accessory\/box/.test(why)) continue;
    if (opts.hideLanes.includes(s.lane || '')) continue;
    if (((s.risk?.score ?? 0) * 100) > opts.maxRisk) continue;
    if ((s.final_score ?? 0) * 100 < opts.minScore) continue;
    if (opts.maxDist != null && (l.distance_km == null || l.distance_km > opts.maxDist)) {
      if (l.distance_km == null) unknown++;
      continue;
    }
    if (opts.min != null && (l.price ?? 1e18) < opts.min) continue;
    if (opts.max != null && (l.price ?? -1) > opts.max) continue;
    const txt = ((l.title || '') + ' ' + (l.description || '')).toLowerCase();
    if (opts.black.some((w) => w && txt.includes(w))) continue;
    if (opts.req.length && !opts.req.every((w) => txt.includes(w))) continue;
    const d = s.deal_dna || {};
    const rk = s.risk?.score ?? 0;
    const score = (opts.matchW * (d.match ?? 0) + opts.valueW * (d.value ?? 0) - opts.riskW * rk + opts.compW * (d.completeness ?? 0)) / t;
    let key: number;
    switch (opts.sort) {
      case 'price': key = l.price ?? 1e18; break;
      case 'dist': key = l.distance_km ?? 1e18; break;
      case 'tc': key = s.deal_dna?.total_cost ?? l.price ?? 1e18; break;
      case 'ppe': key = (l.price && benchOf(s)) ? benchOf(s) / (l.price as number) : -1; break;
      case 'gpe': key = (l.price && gpuOf(s)) ? gpuOf(s) / (l.price as number) : -1; break;
      case 'mt': key = benchOf(s); break;
      default: key = score;
    }
    // default direction: score desc, price asc, dist asc
    const desc = opts.sort === 'score' || opts.sort === 'ppe' || opts.sort === 'mt' ? -1 : 1;
    out.push({ id: l.id, key: key * desc * opts.dir });
  }
  out.sort((a, b) => a.key - b.key);
  (self as unknown as { postMessage: (m: unknown) => void }).postMessage({ ids: out.map((o) => o.id), unknownHidden: unknown });
};
