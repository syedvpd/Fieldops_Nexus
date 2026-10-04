import sys, datetime; sys.path.insert(0,'.')
from pw import *
def fx(b,email,vp=(1280,900)):
    c=b.new_context(viewport={"width":vp[0],"height":vp[1]}); pg=login(c,email); return c,pg
def client_request(b,title):
    c,pg=fx(b,"client@alpha.qa.test",(390,844)); s,j=api(c,"post","/api/v1/portal/requests/",{"asset":sql("select id from assets_asset where asset_tag='HVAC-001'"),"kind":"INCIDENT","title":title,"description":"probe","urgency":"MEDIUM"})
    rid=sql(f"select id from incidents_servicerequest where title='{title}' order by created_at desc limit 1"); return rid,(s,str(j)[:150]),c
def rs(rid): return sql(f"select status from incidents_servicerequest where id='{rid}'")
def staff_to_wo(b,rid):
    c,pg=fx(b,"service@alpha.qa.test")
    for act in ("triage","approve"): api(c,"post",f"/api/v1/service-requests/{rid}/transition/",{"action":act})
    c2,pg2=fx(b,"planner@alpha.qa.test"); s,j=api(c2,"post",f"/api/v1/service-requests/{rid}/create-work-order/",{"title":"probe wo","priority":"MEDIUM"})
    wo=sql(f"select id from workorders_workorder where source_request_id='{rid}' order by created_at desc limit 1")
    now=datetime.datetime.now()+datetime.timedelta(hours=1)
    api(c2,"post",f"/api/v1/work-orders/{wo}/transition/",{"action":"plan","planned_start":now.isoformat(),"planned_end":(now+datetime.timedelta(hours=2)).isoformat(),"estimated_hours":"1"})
    tech=sql("select m.id from tenancy_membership m join accounts_user u on u.id=m.user_id where u.email='tech1@alpha.qa.test'")
    api(c2,"post",f"/api/v1/work-orders/{wo}/transition/",{"action":"assign","technician":tech}); api(c2,"post",f"/api/v1/work-orders/{wo}/transition/",{"action":"dispatch"})
    return wo,(s,str(j)[:150])
def tech_complete(b,wo):
    c,pg=fx(b,"tech1@alpha.qa.test",(390,844)); u=BASE+f"/app/workspace/{wo}/"
    pg.goto(u); f=pg.locator("main form[action$='/transition/start/']")
    if f.count(): cclick(pg,f.locator("button"))
    pg.goto(u); f=pg.locator("main form[action*='/checklists/'][action$='/start/']")
    if f.count(): cclick(pg,f.locator("button").first)
    ins=sql(f"select id from checklists_inspection where work_order_id='{wo}'")
    if ins:
        pg.goto(BASE+f"/app/workspace/inspections/{ins}/"); F="main form[action$='/save/']"
        pg.locator(F+" label.btn",has_text="Pass").first.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
        pg.locator(F+" input:not([type=radio]):not([type=hidden]):not([type=checkbox])").first.fill("400"); pg.wait_for_timeout(700); pg.locator(F+" select").select_option(label="Good"); pg.wait_for_timeout(900)
        pg.locator(F+" button[name=action]",has_text="Save answers").click(); pg.wait_for_load_state("networkidle")
        pg.locator(F+" button[name=action]",has_text="Complete inspection").click(); pg.wait_for_timeout(300); pg.locator("#fx-confirm button:has-text('Confirm')").click(); pg.wait_for_load_state("networkidle")
    pg.goto(u); f=pg.locator("main form[action$='/labor/']"); f.locator("input[name=work_date]").fill(datetime.date.today().isoformat()); f.locator("input[name=hours]").fill("1"); f.locator("button").click(); pg.wait_for_load_state()
    pg.goto(u); f=pg.locator("main form[action$='/evidence/']"); f.locator("input[name=file]").set_input_files("ev.png"); f.locator("button").click(); pg.wait_for_load_state()
    pg.goto(u); f=pg.locator("main form[action$='/transition/complete/']"); f.locator("textarea").fill("Probe completion notes long enough"); cclick(pg,f.locator("button"))
    return sql(f"select status from workorders_workorder where id='{wo}'")

def complete_inspection_post(c, ins):
    items=sql(f"select ci.id||'|'||ci.item_type||'|'||ci.prompt from checklists_checklistitem ci join checklists_inspection i on i.template_id=ci.template_id where i.id='{ins}' order by ci.position").split("\n")
    data={}
    for it in items:
        iid,typ,prompt=it.split("|",2)
        data["item_"+iid]={"BOOLEAN":"pass","NUMERIC":"400","SELECTION":"Good"}.get(typ,"" )
    data["action"]="save"; s1,_=post(c,f"/app/workspace/inspections/{ins}/save/",data); data["action"]="complete"; s2,_=post(c,f"/app/workspace/inspections/{ins}/save/",data)
    return s1,s2,sql(f"select status from checklists_inspection where id='{ins}'")
def tech_finish(b,wo):
    c,pg=fx(b,"tech1@alpha.qa.test",(390,844)); u=BASE+f"/app/workspace/{wo}/"
    ins=sql(f"select id from checklists_inspection where work_order_id='{wo}'")
    if ins and sql(f"select status from checklists_inspection where id='{ins}'")!="COMPLETED": print(complete_inspection_post(c,ins))
    pg.goto(u); f=pg.locator("main form[action$='/transition/complete/']"); f.locator("textarea").fill("Probe completion notes long enough"); cclick(pg,f.locator("button"))
    return sql(f"select status from workorders_workorder where id='{wo}'")
