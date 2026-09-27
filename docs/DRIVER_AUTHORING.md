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

## Categories (per-platform chooser + automatch)
- Add two class attrs so the UI offers your site in the per-platform category chooser:
  `GENERIC = {"laptops": "<native-slug>", ...}` (generic taxonomy keys: laptops, phones,
  cars, furniture, bikes, plus any you verify) and `CATEGORIES = {"<slug>": "Label", ...}`.
- Every slug must be verified live (HTTP 200 + real ads parsed) before committing —
  never invent slugs. Document verification date in a comment.
- In `search()`: if `query.cat_map.get("<your-id>")` or the generic `query.category`
  maps, browse that category URL (paginated); otherwise do the keyword search.
- Slugs from users are untrusted: validate `^[a-z0-9-]+$` before interpolating into URLs.

## Pagination contract (required for unlimited searches)
- Walk pages until exhaustion (no next-page link / zero new items), honoring
  `query.max_pages` when set and `query.limit` (stop when reached).
- Cooperative stop/pause on EVERY page (mandatory — users stop hour-long crawls):
  ```python
  from deal_radar.cancel import pause_gate, should_stop
  for page in ...:
      if should_stop(query.sid):
          break
      if await pause_gate(query.sid):
          break
  ```
- `SearchQuery` carries `.sid` (search id, may be `""` in tests) and `.cat_map` (dict).

## Enrichers (for humans or AI assistants)
Goal: a class in `enrichers/custom/<id>.py` (via Lab) or `packages/deal_radar/enrich.py`.
Contract (exact — listing is an OBJECT with attribute access, NOT a dict):
```python
from deal_radar.enrich import Enricher, register
from deal_radar.contracts import EnrichmentFact, FactStatus, Evidence
class MyEnricher(Enricher):
    id = "<id>"; version = "0.1.0"
    def supports(self, listing) -> bool: return True  # cheap field check
    def enrich(self, listing, ctx):
        title = listing.title or ""; desc = listing.description or ""
        # ... return [EnrichmentFact(field="<field>", value=<v>, confidence=0..1,
        #     status=FactStatus.EXTERNAL, sources=[Evidence(type="external", detail="<src>")])]
        # never raise (catch everything, return [] on failure)
register(MyEnricher())
```
Rules: attribute access ONLY (`listing.title/.description/.price/.images`); polite HTTP
(<=1 req/s, 15s timeout, browser UA); evidence in every fact; no API keys; no new
dependencies beyond httpx/pydantic. Validate: AST gate allows only
`deal_radar/re/math/statistics/datetime/json/httpx/pydantic/asyncio/time/urllib` imports —
anything else is rejected before it ever runs.
