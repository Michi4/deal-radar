from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.enrich import REGISTRY

l = CanonicalListing(id="t", source="t", native_id="t", url="u",
                     title="ThinkPad mit 12 Monate Garantie",
                     description="volle Gewaehrleistung", price=100.0,
                     seller=Seller(name="s"))
for k, v in REGISTRY.items():
    if "warranty" in k or "refurb" in k:
        print(k, [(e.field, e.value, e.confidence) for e in v.enrich(l, {})])
