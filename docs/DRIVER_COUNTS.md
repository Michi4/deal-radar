# Driver fetch audit — site-reported vs app-fetched (query: ThinkPad, 2026-09-29, laptop egress)

| driver | site-reported total | app fetched (1 page) | ratio / note |
|---|---|---|---|
| willhaben | 29,291 rowsFound (Smartphones + iphone, __NEXT_DATA__ 2026-09-28) | walks to exhaustion (max_pages cap); 180 fetched in 2-page live test | full walk supported; laptop IP currently ConnectError-walled (BLOCKERS) |
| kleinanzeigen | n/a (no machine-readable total in markup found) | 27 (ThinkPad, 1 page) | walks via pagination hrefs to exhaustion or user cap |
| vinted | n/a ("0026 Artikel" match unreliable, not trusted) | 91 (ThinkPad, 1 page) | walks via next-page links to exhaustion or user cap |
| shpock | n/a (total: null in SSR apolloState) | 0 + loud error (2026-09-29: ?q= ignored, generic dump) | FIRST PAGE ONLY by site design; keyword-ignored dumps now raise instead of silent zero |
| ebay | n/a (no credentials) | clean error naming EBAY_APP_ID + EBAY_CERT_ID | official Browse API ready, needs user creds (BLOCKERS) |
| ricardo | n/a (403 bot-wall) | clean 403 error, no fakes | blocked; proxy/API options in Store status |

Method: one polite capped search per driver through the running app (`limit 200, max_pages 1`,
enrichment off) + one polite markup probe each for site totals. No hammering.
