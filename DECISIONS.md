# DECISIONS.md — choices made autonomously (per AGENTS.md, no stopping to ask)

- Frankfurt over homeserver/Mumbai for Kev+Ollama: 11GB RAM, WG-meshed, idle. Mumbai unreachable (BLOCKERS).
- Laptop keeps Kev+Ollama+VL copies (dev/fallback, vision backend for pipeline).
- Jev dropped (no key); Kev + local + OpenRouter-free cover all AI slots.
- OpenRouter free models congested evenings → local-first ordering + retry + NL disk cache.
- qwen2.5:3b for NL (0.6b/1.5b too weak); qwen2.5vl:3b for vision + note-consistency clamp.
- eBay ignored (no token); driver stays, clean error, out of defaults.
- Signal: wiring verified end-to-end, account re-link is user-side (BLOCKERS).
- Websters traefik has no Authelia → basic-auth there; homeserver uses real Authelia middlewares.
- External price/spec sources bot-walled → internal market-cohort plugin + PassMark CPU only.
- Frankfurt signal-api impostor removed, home-server compose restored byte-identical.
- Frankfurt deal-radar stopped; homeserver is the single primary (no split brain).
- Frankfurt runs Kev ONLY (Ollama stopped/disabled — co-hosting thrashed 2 vCPUs: load 6, Kev >120s).
  NL text goes to laptop Ollama (15GB RAM); OpenRouter-free is last resort. Lesson: one AI per tiny host.
- POST /searches uses result cache (watcher forces fresh); keyword search 48s cold / 0.1s warm.
