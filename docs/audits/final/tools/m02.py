import sys; sys.path.insert(0,'.')
from pw import *
M="M02"; TAG="AST-"+R
def aid(t=TAG): return sql(f"select id from assets_asset where asset_tag='{t}'")
with sync_playwright() as p:
    b=launch(p); ctx=b.new_context(viewport={"width":1440,"height":900}); pg=login(ctx,"owner@alpha.qa.test"); mon=Mon(pg)
    # category with attributes
    pg.goto(BASE+"/app/assets/categories/")
    fill(pg,dict(name="AuditCat"+R,description="audit",attribute_text="Voltage | number | required\nPhase | choice | optional | Single, Three"),scope="main form:last-of-type")
    pg.locator("main form:has(button:has-text('Create category')) button:has-text('Create category')").click(); pg.wait_for_load_state()
    rec(M,"Create asset category with custom attributes","PASS" if sql(f"select count(*) from assets_assetcategory where name='AuditCat{R}'")=="1" else "FAIL",msgs(pg)[:100])
    # asset create
    pg.goto(BASE+"/app/assets/new/")
    fill(pg,dict(asset_tag=TAG,name="Audit Asset",category="AuditCat"+R,site="HYD-1 · Hyderabad Operations Site",zone="HYD-1 · Building A",manufacturer="ACME",model="X1",serial_number="SN-"+R,purchase_date="2025-01-10",commission_date="2025-02-01",owner="Alpha Asset Manager",warranty_ref="W-"+R,description="d",attr_voltage="415",attr_phase="Three"))
    d=pg.locator("main form [name^='attr']")
    print("attr fields:",d.count(), pg.eval_on_selector_all("main form [name]","e=>e.map(x=>x.name)")[-8:])
    pg.screenshot(path="shots/m02_new.png")
    pg.click("main form button:has-text('Register asset')"); pg.wait_for_load_state()
    rec(M,"Register asset (UI->DB) with attrs, owner, dates","PASS" if aid() and "/assets/"+aid() in pg.url else "FAIL",msgs(pg)[:150])
    A=aid(); url=BASE+f"/app/assets/{A}/"
    row=sql(f"select status,attributes->>'voltage',purchase_date from assets_asset where id='{A}'"); rec(M,"Initial status ACTIVE + custom attributes stored","PASS" if row.startswith("ACTIVE|415") else "FAIL",row)
    rec(M,"Status history row created on register","PASS" if sql(f"select count(*) from assets_assetstatushistory where asset_id='{A}'")=="1" else "FAIL","")
    # validations
    def neg(label, vals, q, expect="0"):
        pg.goto(BASE+"/app/assets/new/"); base=dict(asset_tag="NEG"+R,name="n",category="AuditCat"+R,site="HYD-1 · Hyderabad Operations Site",attr_voltage="1"); base.update(vals); fill(pg,base)
        pg.click("main form button:has-text('Register asset')"); pg.wait_for_load_state(); g=sql(q); rec(M,label,"PASS" if g==expect else "FAIL",f"count={g} {msgs(pg)[:100]}")
    neg("Duplicate asset tag (case-insens) rejected",dict(asset_tag=TAG.lower()),f"select count(*) from assets_asset where lower(asset_tag)=lower('{TAG}')","1")
    neg("Duplicate serial per manufacturer rejected",dict(asset_tag="NEG2"+R,manufacturer="ACME",serial_number="SN-"+R),f"select count(*) from assets_asset where serial_number='SN-{R}' and lower(manufacturer)='acme'","1")
    neg("Commission date before purchase date rejected",dict(asset_tag="NEG3"+R,purchase_date="2025-05-01",commission_date="2025-01-01"),f"select count(*) from assets_asset where asset_tag='NEG3{R}'")
    neg("Required custom attribute enforced",dict(asset_tag="NEG4"+R,attr_voltage=""),f"select count(*) from assets_asset where asset_tag='NEG4{R}'")
    # zone from another site via crafted POST (backend authoritative)
    cat=sql(f"select id from assets_assetcategory where name='AuditCat{R}'"); hyd=sql("select id from sites_site where code='HYD-1'"); blz=sql("select id from sites_zone where name='Warehouse'")
    s,_=post(ctx,"/app/assets/new/",dict(asset_tag="NEG6"+R,name="n",category=cat,site=hyd,zone=blz,attr_voltage="1"))
    rec(M,"Zone from different site rejected (crafted POST)","PASS" if sql(f"select count(*) from assets_asset where asset_tag='NEG6{R}'")=="0" else "FAIL",str(s))
    # edit
    pg.goto(url+"edit/"); fill(pg,dict(name="Audit Asset EDITED",model="X2")); pg.click("main form button.btn-primary"); pg.wait_for_load_state()
    rec(M,"Edit asset persists","PASS" if sql(f"select name||model from assets_asset where id='{A}'")=="Audit Asset EDITEDX2" else "FAIL",msgs(pg)[:80])
    pg.goto(url); t=pg.inner_text("main"); rec(M,"Detail shows identity, location, owner, lifecycle, coverage","PASS" if all(x in t for x in("ACME","Building A","Alpha Asset Manager","Warranty ref","Coverage")) else "FAIL",t[:100].replace("\n"," "))
    # status machine via UI
    def tr(action,reason="audit transition",label=None):
        pg.goto(url); f=pg.locator(f"main form[action$='/transition/{action}/']")
        if not f.count(): return False
        f.locator("input[name=reason]").fill(reason); cclick(pg,f.locator("button"))
        return True
    for act,exp in [("start_maintenance","UNDER_MAINTENANCE"),("mark_out_of_service","OUT_OF_SERVICE"),("return_to_service","ACTIVE"),("start_maintenance","UNDER_MAINTENANCE"),("complete_maintenance","ACTIVE")]:
        ok=tr(act); st=sql(f"select status from assets_asset where id='{A}'"); rec(M,f"Asset status {act} via UI -> {exp}","PASS" if ok and st==exp else "FAIL",st)
    # invalid transitions: crafted POSTs
    s,_=post(ctx,f"/app/assets/{A}/transition/retire/",{"reason":"invalid probe"}); st=sql(f"select status from assets_asset where id='{A}'")
    rec(M,"Invalid transition ACTIVE->retire blocked server-side","PASS" if st=="ACTIVE" else "FAIL",f"http={s} status={st}")
    s,_=post(ctx,f"/app/assets/{A}/transition/start_maintenance/",{"reason":""}); rec(M,"Transition without reason rejected","PASS" if sql(f"select status from assets_asset where id='{A}'")=="ACTIVE" else "FAIL",str(s))
    s,_=post(ctx,f"/app/assets/{A}/transition/bogus/",{"reason":"x y z"}); rec(M,"Unknown action rejected","PASS" if s in(302,400,404,409) and sql(f"select status from assets_asset where id='{A}'")=="ACTIVE" else "FAIL",str(s))
    h=sql(f"select count(*) from assets_assetstatushistory where asset_id='{A}'"); rec(M,"Status history has one row per change (1+5)","PASS" if h=="6" else "FAIL",h)
    pg.goto(url+"?tab=history"); rec(M,"History tab shows status changes with actor/reason","PASS" if "audit transition" in pg.inner_text("main") else "FAIL","")
    a=audits(A); rec(M,"Status changes audited","PASS" if a.count("asset.status")>=5 else "FAIL",a)
    # location move
    pg.goto(url+"edit/"); fill(pg,dict(zone="HYD-1 · Building B")); pg.click("main form button.btn-primary"); pg.wait_for_load_state()
    rec(M,"Location move recorded in location history","PASS" if int(sql(f"select count(*) from assets_assetlocationhistory where asset_id='{A}'") or 0)>=2 else "FAIL",sql(f"select count(*) from assets_assetlocationhistory where asset_id='{A}'"))
    # documents
    open("audit_doc.txt","w").write("audit doc"); open("evil.exe","wb").write(b"MZ\x90\x00evil"); open("fake.pdf","wb").write(b"not really a pdf")
    pg.goto(url+"?tab=documents"); f=pg.locator("main form[action$='/documents/']")
    f.locator("input[name=file]").set_input_files("audit_doc.txt"); f.locator("input[name=title]").fill("Audit doc"); f.locator("button:has-text('Upload')").click(); pg.wait_for_load_state()
    rec(M,"Upload asset document","PASS" if sql(f"select count(*) from assets_assetdocument where asset_id='{A}'")=="1" else "FAIL",msgs(pg)[:100])
    for fn,label in [("evil.exe","Executable upload rejected"),("fake.pdf","Fake PDF (bad magic bytes) rejected")]:
        pg.goto(url+"?tab=documents"); f=pg.locator("main form[action$='/documents/']"); f.locator("input[name=file]").set_input_files(fn); f.locator("button:has-text('Upload')").click(); pg.wait_for_load_state()
        rec(M,label,"PASS" if sql(f"select count(*) from assets_assetdocument where asset_id='{A}'")=="1" else "FAIL",msgs(pg)[:100])
    pg.goto(url+"?tab=documents")
    with pg.expect_download() as dl: pg.click("main a:has-text('Download')")
    d=dl.value; rec(M,"Download document returns uploaded bytes","PASS" if open(d.path(),"rb").read()==b"audit doc" else "FAIL",d.suggested_filename)
    # meters
    pg.goto(url+"?tab=meters"); f=pg.locator("main form[action$='/meters/new/']"); f.locator("input[name=name]").fill("Cycles"); f.locator("input[name=unit]").fill("cyc"); f.locator("button").click(); pg.wait_for_load_state()
    mid=sql(f"select id from assets_assetmeter where asset_id='{A}'"); rec(M,"Create meter","PASS" if mid else "FAIL","")
    def reading(v):
        pg.goto(url+"?tab=meters"); f=pg.locator(f"main form[action$='/meters/{mid}/reading/']"); f.locator("input[name=value]").fill(str(v)); f.locator("button").click(); pg.wait_for_load_state()
    reading(100); reading(150); reading(120)
    vals=sql(f"select string_agg(value::text,',' order by read_at) from assets_assetmeterreading where meter_id='{mid}'"); rec(M,"Meter readings: 100,150 stored; decreasing 120 rejected","PASS" if vals=="100.000,150.000" else "FAIL",vals)
    reading(-5); rec(M,"Negative reading rejected","PASS" if "-5" not in sql(f"select string_agg(value::text,',') from assets_assetmeterreading where meter_id='{mid}'") else "FAIL","")
    # tenant isolation
    cb=b.new_context(); pb=login(cb,"owner@beta.qa.test")
    for path,label in [(f"/app/assets/{A}/","detail"),(f"/app/assets/{A}/edit/","edit"),(f"/app/assets/{A}/tree/","tree")]:
        r=pb.goto(BASE+path); rec(M,f"BETA owner -> ALPHA asset {label}","PASS" if r.status in(403,404) else "FAIL",str(r.status))
    s,_=post(cb,f"/app/assets/{A}/transition/start_maintenance/",{"reason":"cross tenant"}); rec(M,"BETA cross-tenant status POST","PASS" if s in(403,404) and sql(f"select status from assets_asset where id='{A}'")=="ACTIVE" else "FAIL",str(s))
    s,_=post(cb,f"/app/meters/{mid}/reading/",{"value":"999"}); rec(M,"BETA cross-tenant meter reading POST","PASS" if s in(403,404) and "999" not in sql(f"select string_agg(value::text,',') from assets_assetmeterreading where meter_id='{mid}'") else "FAIL",str(s))
    pb.goto(BASE+"/app/assets/"); rec(M,"BETA asset list excludes ALPHA assets","PASS" if TAG not in pb.inner_text("main") and "GEN-001" not in pb.inner_text("main") else "FAIL","")
    ba=sql("select id from assets_asset where asset_tag='BETA-CMP-001'"); r=pg.goto(BASE+f"/app/assets/{ba}/"); rec(M,"ALPHA owner -> BETA asset","PASS" if r.status in(403,404) else "FAIL",str(r.status))
    # list: search/filter/pagination
    pg.goto(BASE+"/app/assets/?q="+TAG); rec(M,"Asset list search","PASS" if TAG in pg.inner_text("main") and "GEN-001" not in pg.inner_text("main") else "FAIL","")
    pg.goto(BASE+"/app/assets/"); fl=pg.eval_on_selector_all("main form[method=get] [name]","e=>e.map(x=>x.name)"); rec(M,"Asset list filters present","PASS" if len(fl)>=3 else "PARTIAL",str(fl))
    rec(M,"M02 console/network (5xx / JS exceptions)","PASS" if not [c for c in mon.console if c[0]=="pageerror"] and not [x for x in mon.bad if x[0]>=500] else "FAIL",str([x for x in mon.bad if x[0]>=500])+str([c for c in mon.console if c[0]=="pageerror"]))
    b.close()
