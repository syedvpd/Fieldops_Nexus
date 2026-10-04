import sys, json; sys.path.insert(0,'.')
from bx import *
r=Run("DISC").start()
q=lambda s: sql(s)
ids=dict(site=q("select id from sites_site where code='HYD-1'"), zone=q("select id from sites_zone where name='Generator Room'"), cal=q("select c.id from sites_operatingcalendar c join sites_site s on s.id=c.site_id where s.code='HYD-1' limit 1"),
 contact=q("select c.id from sites_sitecontact c join sites_site s on s.id=c.site_id where s.code='HYD-1' limit 1"), asset=q("select id from assets_asset where asset_tag='GEN-001'"), eng=q("select id from assets_asset where asset_tag='GEN-001-ENG'"),
 plan=q("select id from maintenance_maintenanceplan where name like 'GEN-001 monthly%'"), sch=q("select s.id from maintenance_maintenanceschedule s join maintenance_maintenanceplan p on p.id=s.plan_id where p.name like 'GEN-001 monthly%'"),
 sch2=q("select s.id from maintenance_maintenanceschedule s join maintenance_maintenanceplan p on p.id=s.plan_id where p.name like 'GEN-001 500%'"),
 link=q("select id from assets_assetcomponent limit 1"), cat=q("select id from assets_assetcategory where name='Generator'"), doc=q("select id from assets_assetdocument limit 1"), meter=q("select id from assets_assetmeter limit 1"))
json.dump(ids,open(OUT+"/ids.json","w"))
paths=["/app/sites/","/app/sites/new/",f"/app/sites/{ids['site']}/",f"/app/sites/{ids['site']}/?tab=locations",f"/app/sites/{ids['site']}/?tab=calendars",f"/app/sites/{ids['site']}/?tab=contacts",f"/app/sites/{ids['site']}/?tab=assets",f"/app/sites/{ids['site']}/edit/",f"/app/sites/{ids['site']}/locations/new/",f"/app/sites/{ids['site']}/calendars/new/",f"/app/sites/{ids['site']}/contacts/new/",f"/app/locations/{ids['zone']}/edit/",f"/app/calendars/{ids['cal']}/edit/",f"/app/contacts/{ids['contact']}/edit/",
"/app/assets/","/app/assets/new/","/app/assets/categories/",f"/app/assets/{ids['asset']}/",f"/app/assets/{ids['asset']}/?tab=documents",f"/app/assets/{ids['asset']}/?tab=meters",f"/app/assets/{ids['asset']}/?tab=history",f"/app/assets/{ids['asset']}/?tab=hierarchy",f"/app/assets/{ids['asset']}/?tab=coverage",f"/app/assets/{ids['asset']}/?tab=labels",f"/app/assets/{ids['asset']}/edit/",f"/app/assets/{ids['eng']}/?tab=hierarchy",
"/app/maintenance/plans/","/app/maintenance/plans/new/",f"/app/maintenance/plans/{ids['plan']}/",f"/app/maintenance/plans/{ids['plan']}/edit/",f"/app/maintenance/plans/{ids['plan']}/schedules/new/",f"/app/maintenance/schedules/{ids['sch']}/",f"/app/maintenance/schedules/{ids['sch']}/edit/",f"/app/maintenance/schedules/{ids['sch2']}/","/app/maintenance/due/","/app/maintenance/history/"]
pg=r.page("owner")
inv={}
for p in paths:
    pg.goto(BASE+p); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(500)
    i=inventory(pg); inv[p]=i
    print(f"\n== {p} | {i['title']} | links={len(i['links'])} btn={len(i['buttons'])} forms={len(i['forms'])} hx={len(i['hx'])} tables={len(i['tables'])} tabs={[t['t'] for t in i['tabs']]}")
    for f in i['forms']:
        if f['action'] and '/logout' in f['action']: continue
        if f['method']=='get' and not f['fields']: continue
        print("  FORM",f['method'],f['action'],f['hx'] or '',[ (x['n'],x['type'],'*' if x['req'] else '') for x in f['fields']][:16])
    print("  BTN",[b['t'] for b in i['buttons'] if b['t'] and b['t'] not in('Sign out','Cancel','Confirm')][:25])
    if i['hx']: print("  HX",i['hx'][:6])
    print("  MODALS",i['modals'])
json.dump(inv,open(OUT+"/inventory_owner.json","w"),indent=1)
nav=inv["/app/sites/"]["nav"]; print("\nNAV:",[(n['t'],n['h']) for n in nav][:60])
print("issues:",[(x['kind'],x['text'][:100]) for x in r.issues][:10])
r.stop()
