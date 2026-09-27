# DECISIONS.md — choices made autonomously (per AGENTS.md, no stopping to ask)

- AI host over app host/spare host for Kev+Ollama: 11GB RAM, WG-meshed, idle. spare host unreachable (BLOCKERS).
- Laptop keeps Kev+Ollama+VL copies (dev/fallback, vision backend for pipeline).
- Jev dropped (no key); Kev + local + OpenRouter-free cover all AI slots.
- OpenRouter free models congested evenings → local-first ordering + retry + NL disk cache.
- qwen2.5:3b for NL (0.6b/1.5b too weak); qwen2.5vl:3b for vision + note-consistency clamp.
- eBay ignored (no token); driver stays, clean error, out of defaults.
- Signal: wiring verified end-to-end, account re-link is user-side (BLOCKERS).
- Websters traefik has no Authelia → basic-auth there; app host uses real Authelia middlewares.
- External price/spec sources bot-walled → internal market-cohort plugin + PassMark CPU only.
- AI host signal-api impostor removed, home-server compose restored byte-identical.
- AI host deal-radar stopped; app host is the single primary (no split brain).
- AI host runs Kev ONLY (Ollama stopped/disabled — co-hosting thrashed 2 vCPUs: load 6, Kev >120s).
  NL text goes to laptop Ollama (15GB RAM); OpenRouter-free is last resort. Lesson: one AI per tiny host.
- POST /searches uses result cache (watcher forces fresh); keyword search 48s cold / 0.1s warm.
- Laya evaluated twice, NOT adopted: laya-serve on PyPI is a 0.1 stub (no server code);
  reported accuracy ~0.77 trails Kev; AI host Kev answers <2s. Revisit when laya-serve matures.
- eBay tokenless scraping REFUSED: bot-wall serves decoy cards (no prices/titles) — fake data risk.

- Proxy live test used 1 request via the homelab's own webshare pool (pricematters env, never committed); justified as de-minimis infra validation.
- Plugin/driver registry index stays PUBLIC: it lists scraper drivers, which lowers the bar for scraping at scale. Accepted because (a) every driver carries its ToS/personal-use notice, (b) drivers are polite by construction (≤1 req/s, cached), (c) the techniques are already public knowledge. Revisit if a source complains.

## 2026-09-27 (volume/pages/tracking batch)
- Unlimited = default (limit null). Caps only via UI select. enrich_top_n (150) bounds expensive
  work; flagged cap 5000. Perf stance: fetch is cheap, depth is bounded.
- Categories v1: only kleinanzeigen slugs verified live (notebooks/handys/autos/moebel-wohnen).
  willhaben /computer slug serves generic mix (subpaths 404) — deferred, needs real research.
  vinted 2050 = clothing, unmapped. Others: keyword fallback, documented in UI.
- Filter state: per-search intent restore on open + localStorage latest + reset-to-defaults.
  AI filters always overwrite advanced (visible application).
- Watches: 30min default, floor = max(60s, last search duration) with toast; new triggers
  desc/image/title/seller via orchestrator events; watch-from-tile endpoint.
- Product tracking Snoty-style: favorites re-fetched via fetch_detail (ebay/kleinanzeigen/
  willhaben only), title now versioned, snapshot time-travel in drawer. Others: no detail API.
- Lab/code-exec + SSRF + metrics-vs-SQLite still queued (unchanged).
