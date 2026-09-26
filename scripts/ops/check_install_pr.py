from deal_radar.registry import install
from deal_radar.registry import COMMUNITY
import shutil

r = install({"id": "tplpr", "version": "0.1.0", "display_name": "TplPR",
             "source": "github:Michi4/deal-radar@lab/template-marketplace-entry:drivers/_template"})
print(r)
shutil.rmtree(str(COMMUNITY / "tplpr"), ignore_errors=True)
print("cleaned")
