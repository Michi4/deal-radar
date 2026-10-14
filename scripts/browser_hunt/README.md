# browser_hunt — drive the debug browser past blocked drivers

These scripts scrape eBay / kleinanzeigen / willhaben **through a real Chrome**
(CDP at `localhost:9222`), which is how we hunt when the HTTP drivers are
bot-walled. They are a *hunting* tool, separate from the drivers in `drivers/`.

## Prerequisites

```bash
/usr/bin/google-chrome-stable \
  --user-data-dir=/tmp/opencode/hunt/ebay-profile \
  --remote-debugging-port=9222 --remote-allow-origins=* \
  --no-first-run --no-default-browser-check about:blank &
```

`--remote-allow-origins=*` is required — without it the WebSocket handshake is
rejected with 403. Kill/restart via the port (`fuser -k 9222/tcp`), never
`pkill -f`, which matches your own shell.

The eBay profile carries a logged-in session, so item pages load without the
"Ihr Browser wird geprüft" wall that hits anonymous requests.

## Usage

```bash
cd scripts/browser_hunt

# batch eBay searches (sequential, 4s polite gap)
python3 batch_ebay.py '["thinkpad mainboard","mainboard i7-11800h"]' /tmp/mb1.json

# kleinanzeigen (needs DB_PATH so the PassMark cache resolves)
DB_PATH=/tmp/opencode/hunt/dealradar.db python3 scrape_ka.py \
  '["thinkpad mainboard","mini pc"]' /tmp/ka1.json

# willhaben (scrolls to trigger lazy-load: 8 -> 33+ anchors)
python3 scrape_wh.py '["mainboard i7","ryzen mainboard"]' /tmp/wh1.json

# rank everything through deal-radar's own scoring
DB_PATH=/tmp/opencode/hunt/dealradar.db python3 combine.py
```

## Gotchas learned the hard way

- **One tab, so no parallel CDP calls.** Two concurrent `cdp.py` runs race on
  the shared page target and silently return each other's results.
- **`DB_PATH` must be set** for `cached_cpu()` — the PassMark cache lives at a
  path derived from it. Forget it and *every* offer scores 0 (the bug reads as
  "0 results", not an error).
- **kleinanzeigen**: the first `a[href*="/s-anzeige/"]` in a card is a counter
  badge ("5"), not the title — pick the longest-text anchor.
- **willhaben** writes prices as `€ 30` (euro *first*); the search card carries
  title, price and locality in one `innerText`.
- **eBay item pages show USD**, search cards show EUR incl. import VAT (~0.90).
  Rank on the card's EUR figure — that is what an AT buyer actually pays.

## Results so far

See `MISSING_FULL.md` round 16 for the ranked finds from these runs.
