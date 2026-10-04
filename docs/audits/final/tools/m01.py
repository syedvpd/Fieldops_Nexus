import sys; sys.path.insert(0,'.')
from pw import *
M="M01"; CODE="AUD-"+R
def sid(code=CODE): return sql(f"select id from sites_site where code='{code}'")
with sync_playwright() as p:
    b=launch(p); ctx=b.new_context(viewport={"width":1440,"height":900}); pg=login(ctx,"owner@alpha.qa.test"); mon=Mon(pg)
    pg.goto(BASE+"/app/sites/new/")
    fill(pg,dict(code=CODE,name="Audit Plant One",city="Chennai",country="IN",timezone="Asia/Kolkata",address="1 Audit Rd",contact_name="Ann Audit",contact_email="ann@audit.test",contact_phone="+91 44 1"))
    pg.click("main form button:has-text('Create site')"); pg.wait_for_load_state()
    rec(M,"Create site via form","PASS" if sid() and CODE in pg.inner_text("main") else "FAIL",f"url={pg.url} id={sid()}")
    site_url=BASE+f"/app/sites/{sid()}/"
    org=sql(f"select organization_id=(select id from tenancy_organization where slug='alpha-field-services') from sites_site where code='{CODE}'")
    rec(M,"Site owned by active org (organization_id)","PASS" if org=="t" else "FAIL",org)
    def neg(label, vals, check_sql, expect="0"):
        pg.goto(BASE+"/app/sites/new/"); fill(pg,vals); pg.click("main form button:has-text('Create site')"); pg.wait_for_load_state()
        got=sql(check_sql); rec(M,label,"PASS" if got==expect and msgs(pg) else "FAIL",f"count={got} msg={msgs(pg)[:100]}")
    neg("Duplicate site code rejected, 1 DB row",dict(code=CODE,name="Dup",timezone="Asia/Kolkata"),f"select count(*) from sites_site where lower(code)=lower('{CODE}')","1")
    neg("Case-insensitive duplicate code rejected",dict(code=CODE.lower(),name="Dup2",timezone="Asia/Kolkata"),f"select count(*) from sites_site where lower(code)=lower('{CODE}')","1")
    neg("Invalid timezone rejected",dict(code="BADTZ"+R,name="Bad tz",timezone="Mars/Olympus"),f"select count(*) from sites_site where code='BADTZ{R}'")
    neg("Bad contact email rejected",dict(code="BADM"+R,name="Bad mail",timezone="Asia/Kolkata",contact_email="not-an-email"),f"select count(*) from sites_site where code='BADM{R}'")
    pg.goto(BASE+"/app/sites/new/"); fill(pg,dict(code="XSS"+R,name="<script>alert(1)</script>",timezone="Asia/Kolkata")); pg.click("main form button:has-text('Create site')"); pg.wait_for_load_state()
    pg.goto(BASE+"/app/sites/?q=XSS"+R); html=pg.content()
    rec(M,"XSS payload in site name rendered escaped","PASS" if "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html else "FAIL","")
    pg.goto(site_url+"edit/"); fill(pg,dict(name="Audit Plant One (edited)",city="Madurai")); pg.click("main form button.btn-primary"); pg.wait_for_load_state()
    v=sql(f"select name||'/'||city from sites_site where code='{CODE}'")
    rec(M,"Edit site persists to DB","PASS" if v=="Audit Plant One (edited)/Madurai" else "FAIL",v)
    a=audits(sid()); rec(M,"Create+edit audited (site.*)","PASS" if "site.created" in a and "site.updated" in a else "FAIL",a)
    # zones
    def zone(name,typ,parent=None):
        pg.goto(site_url+"locations/new/"); vals=dict(name=name,zone_type=typ)
        if parent: vals["parent"]=parent
        fill(pg,vals); pg.click("main form button:has-text('Create location')"); pg.wait_for_load_state()
    zone("Block A","Building"); zone("Floor 1","Zone / area","Block A"); zone("Room 101","Zone / area","Floor 1"); zone("Service Area N","Service area","Room 101")
    d=sql(f"select z.name||'>'||coalesce(p.name,'-') from sites_zone z left join sites_zone p on p.id=z.parent_id where z.site_id='{sid()}' order by z.created_at").replace("\n",";")
    rec(M,"4-level nested zones persisted (UI->DB)","PASS" if d=="Block A>-;Floor 1>Block A;Room 101>Floor 1;Service Area N>Room 101" else "FAIL",d)
    pg.goto(site_url+"?tab=locations"); t=pg.inner_text("main"); pg.screenshot(path="shots/m01_tree.png")
    rec(M,"Locations tab renders hierarchy","PASS" if all(x in t for x in("Block A","Floor 1","Room 101","Service Area N")) else "FAIL","")
    zid=sql(f"select id from sites_zone where name='Block A' and site_id='{sid()}'")
    pg.goto(BASE+f"/app/locations/{zid}/edit/")
    opts=pg.eval_on_selector("select[name=parent]","s=>[...s.options].map(o=>o.text)")
    rec(M,"Zone edit parent dropdown excludes self and descendants (cycle prevention in UI)","PASS" if not any(x in " ".join(opts) for x in("Block A","Floor 1","Room 101","Service Area N")) else "FAIL",str(opts))
    # force cycle via crafted POST (backend authoritative)
    child=sql(f"select id from sites_zone where name='Service Area N' and site_id='{sid()}'")
    pg.select_option("select[name=parent]", index=0)
    pg.evaluate("""(id)=>{const s=document.querySelector('select[name=parent]');const o=document.createElement('option');o.value=id;o.text='x';s.add(o);s.value=id}""",child)
    pg.click("main form button.btn-primary"); pg.wait_for_load_state()
    par=sql(f"select coalesce(parent_id::text,'') from sites_zone where id='{zid}'")
    rec(M,"Backend rejects zone cycle on crafted POST","PASS" if par=="" else "FAIL",f"parent={par!r} msg={msgs(pg)[:100]}")
    # calendar
    pg.goto(site_url+"calendars/new/"); fill(pg,dict(name="Audit shift",start_time="09:00",end_time="17:00",is_default=True))
    pg.locator("main form input[name=working_days]").nth(0).check(); pg.locator("main form input[name=working_days]").nth(1).check()
    pg.click("main form button:has-text('Create calendar')"); pg.wait_for_load_state()
    rec(M,"Create operating calendar","PASS" if sql(f"select count(*) from sites_operatingcalendar where site_id='{sid()}'")=="1" else "FAIL",msgs(pg)[:100])
    pg.goto(site_url+"calendars/new/"); fill(pg,dict(name="Bad hours",start_time="18:00",end_time="08:00"))
    pg.locator("main form input[name=working_days]").nth(0).check(); pg.click("main form button:has-text('Create calendar')"); pg.wait_for_load_state()
    rec(M,"Calendar with end<start rejected","PASS" if sql(f"select count(*) from sites_operatingcalendar where site_id='{sid()}' and name='Bad hours'")=="0" else "FAIL",msgs(pg)[:100])
    pg.goto(site_url+"?tab=calendars"); dump(pg,True) if False else None
    # contact
    pg.goto(site_url+"contacts/new/"); fill(pg,dict(name="Site Mgr",role_title="Manager",phone="+91 1",email="m@audit.test",escalation_order="1")); pg.click("main form button:has-text('Add contact')"); pg.wait_for_load_state()
    rec(M,"Add site contact","PASS" if sql(f"select count(*) from sites_sitecontact where site_id='{sid()}'")=="1" else "FAIL",msgs(pg)[:100])
    # deactivate / reactivate
    pg.goto(site_url); pg.fill("main form input[name=reason]","Audit decommission"); pg.click("main form button:has-text('Deactivate')"); pg.wait_for_load_state()
    st=sql(f"select status from sites_site where code='{CODE}'"); rec(M,"Deactivate site with reason (state machine)","PASS" if st=="INACTIVE" else "FAIL",f"{st} {audits(sid())}")
    pg.goto(site_url); t=pg.inner_text("main"); btn=pg.locator("main form button:has-text('Activate'), main form button:has-text('Reactivate')").first
    if btn.count():
        pg.fill("main form input[name=reason]","back") if pg.locator("main form input[name=reason]").count() else None
        btn.click(); pg.wait_for_load_state(); st=sql(f"select status from sites_site where code='{CODE}'"); rec(M,"Reactivate site","PASS" if st=="ACTIVE" else "FAIL",st)
    else: rec(M,"Reactivate site","FAIL","no reactivate button on detail page: "+t[:200].replace("\n"," | "))
    # deactivate site that has active assets
    hyd=sql("select id from sites_site where code='HYD-1'"); pg.goto(BASE+f"/app/sites/{hyd}/")
    pg.fill("main form input[name=reason]","audit probe"); pg.click("main form button:has-text('Deactivate')"); pg.wait_for_load_state()
    st=sql("select status from sites_site where code='HYD-1'")
    rec(M,"Deactivating a site that still has ACTIVE assets/zones","PASS" if st=="ACTIVE" else "UNVERIFIED",f"status after={st} msg={msgs(pg)[:150]} (business rule: see note)")
    if st=="INACTIVE":
        pg.goto(BASE+f"/app/sites/{hyd}/"); pg.fill("main form input[name=reason]","restore"); pg.click("main form button:has-text('Activate')"); pg.wait_for_load_state()
    # list / search / filter / pagination
    pg.goto(BASE+"/app/sites/?q=Audit"); rec(M,"Search filter","PASS" if CODE in pg.inner_text("main") and "HYD-1" not in pg.inner_text("main") else "FAIL","")
    pg.goto(BASE+"/app/sites/?status=INACTIVE"); rec(M,"Status filter","PASS" if "HYD-1" not in pg.inner_text("main") else "FAIL","")
    rec(M,"Console/network on M01 flow","PASS" if not [c for c in mon.console if c[0]=="pageerror"] and not [x for x in mon.bad if x[0]>=500] else "FAIL",f"console={mon.console[:3]} bad={[x for x in mon.bad][:6]}")
    ctx.close()
    # tenant isolation both directions
    cb=b.new_context(); pb=login(cb,"owner@beta.qa.test")
    r=pb.goto(BASE+f"/app/sites/{sid()}/"); rec(M,"BETA owner opening ALPHA site URL","PASS" if r.status in(403,404) and CODE not in pb.content() else "FAIL",str(r.status))
    pb.goto(BASE+"/app/sites/"); rec(M,"BETA site list excludes ALPHA sites","PASS" if "HYD-1" not in pb.inner_text("main") and CODE not in pb.inner_text("main") else "FAIL","")
    r=pb.goto(BASE+f"/app/sites/{sid()}/edit/"); rec(M,"BETA owner opening ALPHA site edit URL","PASS" if r.status in(403,404) else "FAIL",str(r.status))
    bs=sql("select id from sites_site where code='PUN-1'"); r=pb.goto(BASE+f"/app/sites/{bs}/")
    ca=b.new_context(); pa=login(ca,"owner@alpha.qa.test"); r2=pa.goto(BASE+f"/app/sites/{bs}/")
    rec(M,"ALPHA owner opening BETA site URL","PASS" if r2.status in(403,404) and "Pune" not in pa.content() else "FAIL",f"{r2.status}; beta sees own={r.status}")
    # zone parent from other site via API
    b.close()
    responsive_b=sync_playwright
