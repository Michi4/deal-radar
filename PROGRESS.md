# PROGRESS.md — 2026-09-27 audit + UI session (Michi4 authorship)

## Verified state
- verify.sh GREEN (ruff+mypy+pytest, coverage TOTAL 85% = gate, JS syntax, API import).
- Playwright mega.mjs 11/11 PASS (×3 runs), xss.mjs 4/4 PASS (×3), manual NL→drawer journey clean.
- Prod `4b7b150` deployed, container healthy; edge = Authelia 302 as designed.
- AUDIT_REPORT.md: 2 passes done. Fixed: stored-XSS (esc+safeUrl+delegation, strict CSP
script-src 'self', JS in web/app.js+admin.js), input bounds (422s), 404/400 error shapes,
marketplace id/hash hardening, ailab AST gate, DB indexes + batched queries + write lock +
WAL assert, headers, wider rate-limit, signal-target trim, watcher error counter,
coverage gate 85 (verify+pyproject+CI runs verify.sh), Dockerfile USER app + HEALTHCHECK +
sqlite3, compose env parity, README de-homelabbed + auth matrix.
- UI: BeBetter-style navbar (desktop pill nav + mobile bottom nav), toolbar owns sort/page/view,
de-boxed search, AI-understood panel, ptitle page headers, admin refresh, favicon, toast cap,
toolbar persists after search (SEARCHED flag), drawer enrichment formatting.
- NL fallback: EN cues (under/over/below/above, without/with-no/excluding/minus) + unit tests.
- Ops lessons: pkill -f self-match kills own shell → /tmp/opencode/killsrv.sh; one-liner
server-start+test chains lose output → step-by-step; stale :8099 squatters cause false e2e
fails → killsrv first; USER app needs chown -R app:app /data on legacy root volume (done prod).

## Next (needs human — do NOT shutdown)
1. AUTH DECISION (audit HIGH): API_KEY unset everywhere → app fully open behind Authelia only.
Options: (a) auto-generate+persist API_KEY on first boot [recommended], (b) document fork risk,
(c) per-user tokens + owner columns. Needed before "prod-ready" sign-off.
2. Queued hardening: SSRF egress allowlist (vision.py), sandboxed Lab exec, metrics/admin←SQLite,
script-src already strict; style-src unsafe-inline residual LOW.
3. Standing creds asks: EBAY_OAUTH_TOKEN, GH_TOKEN/LAB_PUBLISH, telegram/email, spare host.
4. NL 7-day cache serves stale parses after parser upgrades (texts re-tested OK).

## Older state (2026-09-26)

## Verified state
- ACCEPTANCE: all checked except 3 BLOCKED (ebay-tokenless, lab auto-PR GH_TOKEN, Signal-alive + telegram/email).
- verify.sh GREEN (ruff+mypy+86%), CI green, clean-clone green (58 passed).
- Prod: 6 drivers live, marketplace remote index, Lab builds+fires, watcher autonomy, SSE live,
  backup cron ran, jump-host deploys, total-cost DNA + sort, kind toggles, refine bar, searches dashboard.
- Brains: AI host Kev (<2s), laptop Ollama 3b + VL, OpenRouter last resort, breakers everywhere.

## Next (needs human)
1. Signal receipt confirmation (2 test messages accepted with timestamps).
2. EBAY_OAUTH_TOKEN, GH_TOKEN, telegram/email creds, spare host creds.
3. Eyes on Tailwind UI.

## Standing notes (reaffirmed)
- No push without local verify.sh GREEN. Fixture HTML: scrub third-party keys before commit.
- Test mocks: bare patch.object (correct) vs new=lambda (breaks async ctx managers).
- NL cache is prompt-versioned; server volume persists it.
- One AI per tiny host. Reset --soft stages everything (commit in chunks deliberately).
