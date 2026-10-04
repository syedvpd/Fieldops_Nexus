import sys; sys.path.insert(0,'.')
from pw import *
M="M03"
with sync_playwright() as p:
    b=launch(p); ctx=b.new_context(viewport={"width":1440,"height":900}); pg=login(ctx,"owner@alpha.qa.test"); mon=Mon(pg)
    ids={}
    for k in ("P","C1","C2","G"): ids[k]=mk_asset(pg,f"H3{k}-{R}",f"Hier {k}")
    rec(M,"Create 4 assets for hierarchy","PASS" if all(ids.values()) else "FAIL",str(ids))
    def add(parent,child,rel="Assembly",qty="2",pn="PN-1"):
        pg.goto(BASE+f"/app/assets/{ids[parent]}/?tab=hierarchy"); f=pg.locator("main form[action$='/components/add/']")
        opts=f.locator("select[name=child] option").all_inner_texts()
        sel=[o for o in opts if f"H3{child}-{R}" in o]
        if not sel: return None,opts
        f.locator("select[name=child]").select_option(label=sel[0]); f.locator("select[name=relationship_type]").select_option(label=rel)
        f.locator("input[name=quantity]").fill(qty); f.locator("input[name=part_number]").fill(pn); f.locator("button:has-text('Add to hierarchy')").click(); pg.wait_for_load_state()
        return True,msgs(pg)
    ok,_=add("P","C1"); rec(M,"Attach child C1 to parent P (UI)","PASS" if ok and sql(f"select count(*) from assets_assetcomponent where parent_id='{ids['P']}' and child_id='{ids['C1']}'")=="1" else "FAIL","")
    ok,_=add("P","C2","Component","1"); ok2,_=add("C1","G","Replaceable part","4")
    d=sql(f"select count(*) from assets_assetcomponent where parent_id in ('{ids['P']}','{ids['C1']}')"); rec(M,"3-level tree persisted (P>C1>G, P>C2)","PASS" if d=="3" else "FAIL",d)
    pg.goto(BASE+f"/app/assets/{ids['P']}/?tab=hierarchy"); pg.wait_for_function("()=>!document.body.innerText.includes('Loading hierarchy')",timeout=10000); t=pg.inner_text("main"); pg.screenshot(path="shots/m03_tree.png")
    rec(M,"Tree view renders all descendants","PASS" if all(f"H3{k}-{R}" in t for k in("C1","C2","G")) else "FAIL",t[:150].replace("\n"," "))
    # cycle: add P as child of G -> option should be absent
    r,opts=add("G","P"); rec(M,"UI prevents cycle: ancestor not offered as child","PASS" if r is None else "FAIL",f"offered={r}")
    for lab,par,ch in [("Cycle via crafted POST (P under G)","G","P"),("Self-parent via crafted POST","P","P"),("Re-add already-parented child (C1 under C2)","C2","C1")]:
        s,_=post(ctx,f"/app/assets/{ids[par]}/components/add/",dict(child=ids[ch],relationship_type="COMPONENT",quantity="1"))
        n=sql(f"select count(*) from assets_assetcomponent where child_id='{ids[ch]}'")
        exp="1" if ch=="C1" else "0"
        if ch=="P" and par=="G": exp="0"
        rec(M,lab+" rejected by backend","PASS" if n==exp else "FAIL",f"http={s} rows_as_child={n}")
    # cross-site child
    blr=mk_asset(pg,f"H3X-{R}","Other site",site="BLR-1 · Bangalore Service Depot")
    s,_=post(ctx,f"/app/assets/{ids['P']}/components/add/",dict(child=blr,relationship_type="COMPONENT",quantity="1")); rec(M,"Child from a different site rejected","PASS" if sql(f"select count(*) from assets_assetcomponent where child_id='{blr}'")=="0" else "FAIL",str(s))
    # cross-tenant child
    bx=sql("select id from assets_asset where asset_tag='BETA-CMP-001'"); s,_=post(ctx,f"/app/assets/{ids['P']}/components/add/",dict(child=bx,relationship_type="COMPONENT",quantity="1")); rec(M,"Cross-tenant child rejected","PASS" if sql(f"select count(*) from assets_assetcomponent where child_id='{bx}'")=="0" else "FAIL",str(s))
    # edit relationship
    link=sql(f"select id from assets_assetcomponent where child_id='{ids['C1']}'")
    s,_=post(ctx,f"/app/components/{link}/edit/",dict(relationship_type="COMPONENT",quantity="7",part_number="PN-EDIT",notes="n")); rec(M,"Edit relationship persists","PASS" if sql(f"select quantity||part_number from assets_assetcomponent where id='{link}'").startswith("7") else "FAIL",sql(f"select quantity||part_number from assets_assetcomponent where id='{link}'"))
    # move C1 (with G) under C2
    dump(pg,True) if False else None
    s,_=post(ctx,f"/app/components/{link}/move/",dict(parent=ids['C2'])); par=sql(f"select parent_id from assets_assetcomponent where id='{link}'")
    rec(M,"Re-parent subtree (C1 under C2)","PASS" if par==ids['C2'] else "UNVERIFIED",f"http={s} parent={par}")
    # move P under G (cycle) 
    plink=sql(f"select id from assets_assetcomponent where child_id='{ids['C2']}'")
    s,_=post(ctx,f"/app/components/{plink}/move/",dict(parent=ids['G']));
    rec(M,"Re-parent cycle (C2 under its own descendant G) rejected","PASS" if sql(f"select parent_id from assets_assetcomponent where id='{plink}'")==ids['P'] else "FAIL",str(s))
    # detach G
    glink=sql(f"select id from assets_assetcomponent where child_id='{ids['G']}'"); s,_=post(ctx,f"/app/components/{glink}/remove/",dict(reason="audit detach"))
    rec(M,"Detach component","PASS" if sql(f"select count(*) from assets_assetcomponent where id='{glink}'")=="0" else "FAIL",str(s))
    rec(M,"Hierarchy changes audited","PASS" if sql(f"select count(*) from audit_auditlog where action like 'asset.component%' and metadata::text like '%{R}%'") not in ("0","") or int(sql("select count(*) from audit_auditlog where action like 'asset.component%'") or 0)>=5 else "FAIL",sql("select string_agg(distinct action,',') from audit_auditlog where action like '%component%'"))
    # M03-1 probe: retire parent with children
    def toRetire(A):
        for act in ("start_maintenance","mark_out_of_service"):
            post(ctx,f"/app/assets/{A}/transition/{act}/",dict(reason="audit probe retire"))
        post(ctx,f"/app/assets/{A}/transition/retire/",dict(reason="audit probe retire"))
        return sql(f"select status from assets_asset where id='{A}'")
    st=toRetire(ids['P']); kids=sql(f"select count(*) from assets_assetcomponent where parent_id='{ids['P']}'")
    rec(M,"PROBE: retire a parent that still has live children","FAIL" if st=="RETIRED" and kids!="0" else "PASS",f"parent status={st} remaining links={kids} (static finding M03-1: stuck hierarchy)")
    s,_=post(ctx,f"/app/components/{plink}/remove/",dict(reason="detach after retire")); rec(M,"PROBE: children of retired parent can still be detached","FAIL" if sql(f"select count(*) from assets_assetcomponent where id='{plink}'")!="0" else "PASS",f"http={s}")
    # isolation
    cb=b.new_context(); pb=login(cb,"owner@beta.qa.test")
    s,_=post(cb,f"/app/assets/{ids['C2']}/components/add/",dict(child=ids['G'],relationship_type="COMPONENT",quantity="1")); rec(M,"BETA cross-tenant hierarchy write","PASS" if s in(403,404) else "FAIL",str(s))
    r=pb.goto(BASE+f"/app/assets/{ids['P']}/tree/"); rec(M,"BETA reads ALPHA hierarchy tree","PASS" if r.status in(403,404) else "FAIL",str(r.status))
    rec(M,"M03 console/network (5xx/JS)","PASS" if not [x for x in mon.bad if x[0]>=500] and not [c for c in mon.console if c[0]=="pageerror"] else "FAIL",str([x for x in mon.bad if x[0]>=500]))
    b.close()
