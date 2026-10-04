import sys, json, uuid; sys.path.insert(0,'.')
from pw import *
site=sql("select id from sites_site where code='HYD-1'"); asset=sql("select id from assets_asset where asset_tag='HVAC-001'"); cat=sql("select id from assets_assetcategory where name='Pump'")
wh=sql("select id from inventory_warehouse where code='HYD-WH'"); part=sql("select id from inventory_part where part_number='FLT-OIL-01'")
sr_new=sql("select id from incidents_servicerequest where status='NEW' limit 1")
ROLES={"owner":"owner@alpha.qa.test","admin":"admin@alpha.qa.test","ops":"ops@alpha.qa.test","supervisor":"supervisor@alpha.qa.test","assets":"assets@alpha.qa.test","planner":"planner@alpha.qa.test","tech":"tech1@alpha.qa.test","stores":"stores@alpha.qa.test","service":"service@alpha.qa.test","auditor":"auditor@alpha.qa.test","client":"client@alpha.qa.test"}
audit_id=sql("select id from audit_auditlog limit 1")
def wo_draft():
    return sql("select id from workorders_workorder where status='DRAFT' order by created_at desc limit 1")
tests=[
 ("site.create","post","/api/v1/sites/",lambda:{"code":"RB"+R+str(uuid.uuid4())[:4],"name":"rbac probe","timezone":"Asia/Kolkata"}),
 ("asset.create","post","/api/v1/assets/",lambda:{"asset_tag":"RBA"+str(uuid.uuid4())[:6],"name":"rbac","category":cat,"site":site}),
 ("incident.create","post","/api/v1/service-requests/",lambda:{"asset":asset,"title":"rbac probe","kind":"INCIDENT","severity":"LOW"}),
 ("work_order.create","post","/api/v1/work-orders/",lambda:{"asset":asset,"title":"rbac probe","work_type":"OTHER","priority":"LOW"}),
 ("work_order.cancel","post",lambda:f"/api/v1/work-orders/{wo_draft()}/transition/",lambda:{"action":"cancel","reason":"rbac probe cancel"}),
 ("incident.triage","post",lambda:f"/api/v1/service-requests/{sr_new}/transition/",lambda:{"action":"triage"}),
 ("part.create","post","/api/v1/parts/",lambda:{"part_number":"RBP"+str(uuid.uuid4())[:5],"name":"rbac part","unit":"pcs"}),
 ("stock.receive","post","/api/v1/stock/receive/",lambda:{"warehouse":wh,"part":part,"quantity":"1","reference":"rbac"}),
 ("role.manage","post","/api/v1/roles/",lambda:{"name":"RBAC "+str(uuid.uuid4())[:5],"permissions":["asset.view"]}),
 ("user.invite","post","/api/v1/members/",lambda:{"email":f"rbac{str(uuid.uuid4())[:6]}@probe.test","full_name":"Probe","role_ids":[]}),
 ("maintenance.create","post","/api/v1/maintenance-plans/",lambda:{"asset":asset,"name":"rbac plan "+str(uuid.uuid4())[:4]}),
 ("sla.manage","post","/api/v1/sla-profiles/",lambda:{"name":"rbac sla "+str(uuid.uuid4())[:4],"applies_to":"REQUEST"}),
 ("contract.create","post","/api/v1/coverage-agreements/",lambda:{"kind":"WARRANTY","reference":"RB"+str(uuid.uuid4())[:5],"title":"x","start_date":"2026-01-01","end_date":"2026-12-31","asset_ids":[asset]}),
 ("org.update","patch","/api/v1/organization/",lambda:{"name":"Alpha Field Services"}),
 ("audit.patch","patch",lambda:f"/api/v1/audit-logs/{audit_id}/",lambda:{"action":"tampered"}),
 ("audit.delete","delete",lambda:f"/api/v1/audit-logs/{audit_id}/",lambda:None),
 ("checklist.create","post","/api/v1/checklist-templates/",lambda:{"name":"rbac cl "+str(uuid.uuid4())[:4],"work_type":"OTHER"}),
 ("warehouse.create","post","/api/v1/warehouses/",lambda:{"code":"RB"+str(uuid.uuid4())[:4].upper(),"name":"rbac wh","site":site}),
]
out={}
with sync_playwright() as p:
    b=launch(p)
    for role,email in ROLES.items():
        c=b.new_context(); login(c,email); row={}
        for name,m,path,body in tests:
            pth=path() if callable(path) else path
            s,j=api(c,m,pth,body())
            row[name]=s
        out[role]=row; c.close()
    json.dump(out,open("rbac_matrix.json","w"),indent=1)
    b.close()
names=[t[0] for t in tests]
print("%-10s"%"role"+" ".join("%-6s"%n[:6] for n in names))
for r,row in out.items(): print("%-10s"%r+" ".join("%-6s"%row[n] for n in names))
print(names)
