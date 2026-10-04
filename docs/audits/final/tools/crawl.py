import sys, re, json; sys.path.insert(0,'.')
from pw import *
paths=[l.split("  [")[0] for l in open("urls_html.txt").read().splitlines()]
static=[x for x in paths if "<" not in x and x.startswith("app/") and not x.endswith(("export/","read-all/","bell/","switch-organization/","process/")) and "identification/scan" not in x]
# add detail pages with real ids
ids={"sites":sql("select id from sites_site where code='HYD-1'"),"assets":sql("select id from assets_asset where asset_tag='GEN-001'"),"wo":sql("select id from workorders_workorder order by created_at desc limit 1"),"sr":sql("select id from incidents_servicerequest limit 1"),"ck":sql("select id from checklists_checklisttemplate limit 1"),"plan":sql("select id from maintenance_maintenanceplan limit 1"),"ag":sql("select id from contracts_coverageagreement limit 1"),"part":sql("select id from inventory_part limit 1"),"wh":sql("select id from inventory_warehouse limit 1"),"slap":sql("select id from sla_slaprofile limit 1"),"slat":sql("select id from sla_slatracking limit 1"),"role":sql("select id from rbac_role limit 1"),"mem":sql("select id from tenancy_membership limit 1"),"acct":sql("select id from portal_portalaccount limit 1"),"sch":sql("select id from maintenance_maintenanceschedule limit 1"),"insp":sql("select id from checklists_inspection limit 1"),"bal":sql("select id from inventory_stockbalance limit 1"),"aud":sql("select id from audit_auditlog limit 1")}
detail=[f"app/sites/{ids['sites']}/",f"app/sites/{ids['sites']}/?tab=locations",f"app/assets/{ids['assets']}/",f"app/assets/{ids['assets']}/?tab=hierarchy",f"app/assets/{ids['assets']}/?tab=meters",f"app/assets/{ids['assets']}/?tab=coverage",f"app/assets/{ids['assets']}/?tab=labels",f"app/work-orders/{ids['wo']}/",f"app/work-orders/{ids['wo']}/?tab=work",f"app/work-orders/{ids['wo']}/parts/",f"app/incidents/{ids['sr']}/",f"app/checklists/{ids['ck']}/",f"app/maintenance/plans/{ids['plan']}/",f"app/maintenance/schedules/{ids['sch']}/",f"app/contracts/agreements/{ids['ag']}/",f"app/inventory/parts/{ids['part']}/",f"app/inventory/warehouses/{ids['wh']}/",f"app/inventory/stock/{ids['bal']}/",f"app/sla/profiles/{ids['slap']}/",f"app/sla/trackings/{ids['slat']}/",f"app/roles/{ids['role']}/",f"app/users/{ids['mem']}/",f"app/portal/accounts/{ids['acct']}/",f"app/audit/{ids['aud']}/",f"app/inspections/{ids['insp']}/",f"app/search/?q=GEN"]
pages=sorted(set(static+detail))
res=[]
with sync_playwright() as p:
    b=launch(p); c=b.new_context(viewport={"width":1440,"height":900}); pg=login(c,"owner@alpha.qa.test")
    for path in pages:
        m=Mon(pg)
        try:
            r=pg.goto(BASE+"/"+path); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
            res.append((path,r.status,[x for x in m.console if "violates" in x[1] or x[0]=="pageerror"],[x for x in m.failed],[x for x in m.bad if x[0]>=400 and x[1].rstrip("/")!=(BASE+"/"+path).rstrip("/")]))
        except Exception as e: res.append((path,"ERR",[str(e)[:100]],[],[]))
        pg.remove_listener if False else None
    b.close()
bad=[r for r in res if r[1]!=200 or r[2] or r[3] or r[4]]
print("pages crawled:",len(res)," with problems:",len(bad))
for r in bad: print(r)
json.dump(res,open("crawl_owner.json","w"))
