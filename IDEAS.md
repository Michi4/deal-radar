# IDEAS.md — new ideas beyond the checklist (ACCEPTANCE item 40).

- [ ] Shpock cap-workaround via price-band slicing: first SSR page yields price quartiles;
  re-query slices (e.g. PRICE_TO bands if the search URL honors them — unverified) and union
  deduped, labeled "shpock: N slices x first page" in the search tile. Needs 2-3 polite
  probes to find a working price param. (FINISH cap rule.)
- [ ] Same slicing pattern generalizes to any hard-capped driver (region/category/sort splits).
- [ ] Willhaben `treeAttributes` facets (condition 22/23/24, pickup 2536, shipping 2537,
  storage GB) are already in navigatorGroups — wire them as real search filters next
  (delivery filter "pickup possible/shipping possible" becomes server-side).
- [ ] Vinted `catalog[]` multi-select + price_from/to already in URL scheme — same treatment.
