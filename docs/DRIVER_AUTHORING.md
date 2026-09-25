# SKILL: author a deal-radar marketplace driver (for humans or AI assistants)

Goal: a new folder `drivers/<id>/driver.py` that passes `python -m deal_radar.registry check <id>`.

## Steps
1. Copy `drivers/_template/` to `drivers/<id>/`.
2. Find the site's keyword search URL (page 1). Fetch it with browser headers
   (`User-Agent: Mozilla... Chrome/126`, `Accept-Language` for the region).
3. Inspect the HTML: prefer embedded JSON (`__NEXT_DATA__`, JSON-LD, `application/ld+json`
   per card) over CSS selectors. Note title/link/price/image/location selectors.
4. Implement `search(query: SearchQuery) -> list[CanonicalListing]`:
   - missing fields → `""` / `None` / `[]`. NEVER raise on missing data.
   - 403/empty → raise RuntimeError with a clear cause (blocked? schema-change?).
   - max 1 req/s, sequential pages only.
5. Set `manifest` (id, display_name, regions, capabilities, access_mode, automation_permission).
6. Save 2+ real card HTML snippets as `tests/fixtures/<id>-*.html`, add parser asserts in `tests/test_core.py`.
7. Run `PYTHONPATH=packages python -m deal_radar.registry check <id>` — must be `{"ok": true}`.
8. Register in `apps/api/main.py load_drivers()` + `drivers/registry.json` entry
   (`github:<owner>/<repo>@<ref>:drivers/<id>` + sha256 over `*.py`).
9. Live test: `POST /searches {"keywords":"<common item>","sources":["<id>"],"limit":5}` → real listings.

## Rules
- Personal, low-volume, polite scraping only. Document the site's ToS stance in the driver docstring.
- Never invent selectors — read real HTML first. If blocked, say so in BLOCKERS.md.
