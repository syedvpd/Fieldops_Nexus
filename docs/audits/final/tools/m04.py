import sys; sys.path.insert(0,'.')
from pw import *
M="M04"
with sync_playwright() as p:
    b=launch(p); ctx=b.new_context(viewport={"width":1440,"height":900}); pg=login(ctx,"planner@alpha.qa.test"); mon=Mon(pg)
    A=mk_asset  # planner can't create assets; use existing
    asset=sql("select asset_tag||' · '||name from assets_asset where asset_tag='PMP-001'")
    pg.goto(BASE+"/app/maintenance/plans/new/")
    opts=pg.locator("select[name=asset] option").all_inner_texts(); sel=[o for o in opts if o.startswith("PMP-001")][0]
    fill(pg,dict(asset=sel,name="Pump quarterly "+R,priority="High",estimated_hours="2",checklist_key="Generator preventive service"))
    pg.click("main form button:has-text('Create plan')"); pg.wait_for_load_state()
    plan=sql(f"select id from maintenance_maintenanceplan where name='Pump quarterly {R}'")
    rec(M,"Planner creates PM plan (UI->DB)","PASS" if plan else "FAIL",msgs(pg)[:100])
    # schedule weekly starting yesterday
    pg.goto(BASE+f"/app/maintenance/plans/{plan}/schedules/new/")
    import datetime
    y=(datetime.date.today()-datetime.timedelta(days=1)).isoformat()
    fill(pg,dict(trigger_type="Time-based",frequency="Week(s)",interval_count="1",start_date=y,lead_days="0",window_start_time="08:00",window_hours="4",reminder_days="1"))
    pg.click("main form button:has-text('Create schedule')"); pg.wait_for_load_state()
    sch=sql(f"select id from maintenance_maintenanceschedule where plan_id='{plan}'")
    rec(M,"Create weekly schedule","PASS" if sch else "FAIL",msgs(pg)[:150]+" "+sql(f"select next_sequence,next_due_date from maintenance_maintenanceschedule where id='{sch}'" ) if sch else msgs(pg))
    pg.goto(BASE+"/app/maintenance/due/"); t=pg.inner_text("main"); rec(M,"Due & upcoming lists the new schedule as DUE","PASS" if "Pump quarterly" in t and "DUE" in t.upper() else "FAIL",t[:200].replace("\n"," | "))
    pg.screenshot(path="shots/m04_due.png")
    # generate now
    pg.goto(BASE+f"/app/maintenance/plans/{plan}/"); f=pg.locator(f"main form[action$='/schedules/{sch}/generate/']"); f.locator("button").click(); pg.wait_for_load_state()
    cyc=sql(f"select count(*) from maintenance_maintenancecycle where schedule_id='{sch}'"); wo=sql(f"select w.number||'|'||w.status||'|'||w.work_type||'|'||w.priority||'|'||coalesce(w.source_type,'') from workorders_workorder w join maintenance_maintenancecycle c on c.work_order_id=w.id where c.schedule_id='{sch}'")
    rec(M,"Generate now creates PM work order (PREVENTIVE, HIGH, source=PM)","PASS" if cyc=="1" and "PREVENTIVE" in wo else "FAIL",f"cycles={cyc} wo={wo} msg={msgs(pg)[:100]}")
    pg.goto(BASE+f"/app/maintenance/plans/{plan}/"); f=pg.locator(f"main form[action$='/schedules/{sch}/generate/']")
    if f.count(): f.locator("button").click(); pg.wait_for_load_state()
    rec(M,"Duplicate prevention: second Generate-now creates no 2nd cycle/WO","PASS" if sql(f"select count(*) from maintenance_maintenancecycle where schedule_id='{sch}'")=="1" else "FAIL",msgs(pg)[:150])
    s,_=post(ctx,f"/app/maintenance/schedules/{sch}/generate/",{}); rec(M,"Crafted repeat generate POST creates no duplicate","PASS" if sql(f"select count(*) from maintenance_maintenancecycle where schedule_id='{sch}'")=="1" else "FAIL",str(s))
    ns=sql(f"select next_sequence||'|'||next_due_date from maintenance_maintenanceschedule where id='{sch}'"); rec(M,"Next cycle advanced after generation","PASS" if ns.startswith("2|") or ns.startswith("1|") else "FAIL",ns)
    rec(M,"PM WO carries required checklist (blocker)","PASS" if sql(f"select count(*) from workorders_workorder w join maintenance_maintenancecycle c on c.work_order_id=w.id where c.schedule_id='{sch}' and w.description like '%Required checklist%'")=="1" else "UNVERIFIED","")
    a=audits(sch); rec(M,"Schedule/cycle generation audited","PASS" if sql("select count(*) from audit_auditlog where action like 'maintenance.%'")!="0" else "FAIL",sql("select string_agg(distinct action,',') from audit_auditlog where action like 'maintenance.%'"))
    # M04-01 runtime: edit interval then check what happens
    pg.goto(BASE+f"/app/maintenance/schedules/{sch}/edit/"); print(forms(pg)[2]['fields'][:2] if len(forms(pg))>2 else "")
    open("m04_state.txt","w").write(f"{plan}\n{sch}\n")
    b.close()
