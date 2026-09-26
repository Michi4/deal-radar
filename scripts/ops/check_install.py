from deal_radar.registry import install, load_index

idx = load_index()
print("remote drivers:", len(idx.get("drivers", [])))
r = install({"id": "tpldemo", "version": "0.1.0", "display_name": "Tpl",
             "source": "github:Michi4/deal-radar@main:drivers/_template"})
print(r)
import shutil
from deal_radar.registry import COMMUNITY
shutil.rmtree(str(COMMUNITY / "tpldemo"), ignore_errors=True)
print("cleaned")
