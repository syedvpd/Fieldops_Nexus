import sys; sys.path.insert(0,'.')
from bx import *
r=Run("M01").start(); p=r.page("owner")
p.goto(BASE+"/app/sites/"); p.wait_for_load_state("networkidle")
heads_links=p.locator("main table thead th a, main table thead th button").count()
first=[row.locator("td").first.inner_text().strip() for row in p.locator("main table tbody tr").all()][:5]
exp=sql(f"select code from sites_site where organization_id={ALPHA} order by code limit 5").split("\n")
r.T("Site list column sorting","/app/sites/","owner","look for sortable headers / ?ordering=","sort controls (task scope: sort)",f"No sort controls (header links={heads_links}); fixed order by code (first rows {first[:3]} match DB order: {first==exp})","PARTIAL")
p.goto(BASE+"/app/sites/?ordering=-code"); first2=[row.locator("td").first.inner_text().strip() for row in p.locator("main table tbody tr").all()][:3]
r.T("Site list ?ordering= parameter","/app/sites/?ordering=-code","owner","type ?ordering=-code","(not implemented -> ignored)",f"ignored; order unchanged: {first2==first[:3]}","PARTIAL")
p.goto(BASE+"/app/sites/")
r.ok("Zone" not in p.locator("main table thead").inner_text(),"Site list shows no zone/asset-type columns beyond counts (Locations, Active assets)","/app/sites/","owner","read headers","counts only","ok")
for x in r.rows: print(x["status"],x["feature"],"|",x["actual"][:120])
r.stop()
