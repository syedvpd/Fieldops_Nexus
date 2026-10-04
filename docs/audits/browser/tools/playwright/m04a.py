import sys, time, json, math, re; sys.path.insert(0, '.')
from bx import *
r = Run("M04").start()
U = str(int(time.time()))[-5:]
O = "owner"
pg = r.page(O)
PL = "/app/maintenance/plans/"
HYD, BLR = sid("HYD-1"), sid("BLR-1")
CAT = lambda n: sql(f"select id from assets_assetcategory where name='{n}' and organization_id={ALPHA}")
PUMP = CAT("Pump")
ASSET = lambda tag: sql(f"select id from assets_asset where lower(asset_tag)=lower('{tag}') and organization_id={ALPHA}")
PLAN = lambda name, asset=None: sql(f"select id from maintenance_maintenanceplan where name='{name}' and organization_id={ALPHA}" + (f" and asset_id='{asset}'" if asset else ""))


class contextlib_null:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def mk(tag, site=HYD):
    bapi(pg, "POST", "/api/v1/assets/", {"asset_tag": tag, "name": f"PM asset {tag}", "category": PUMP, "site": site})
    return ASSET(tag)


A1, A2, AB = mk(f"PMA-{U}"), mk(f"PMA2-{U}"), mk(f"PMB-{U}", BLR)
CK = sql(f"select key from checklists_checklisttemplate where organization_id={ALPHA} order by name limit 1")
CKN = sql(f"select name from checklists_checklisttemplate where key='{CK}' limit 1")
# extra plans for pagination (not under test): 24 via API once
if int(sql(f"select count(*) from maintenance_maintenanceplan where name like 'PGPLAN%' and organization_id={ALPHA}")) < 24:
    for i in range(24):
        bapi(pg, "POST", "/api/v1/maintenance-plans/", {"asset": A2, "name": f"PGPLAN {U} {i:02d}", "priority": ["LOW", "MEDIUM", "HIGH", "URGENT"][i % 4]})


def rows(p):
    return [[c.strip() for c in row.locator("td").all_inner_texts()] for row in p.locator("main table tbody tr").all()]


def new_plan(p, vals, ok=True):
    p.goto(BASE + PL + "new/"); p.wait_for_load_state("networkidle")
    p.evaluate("()=>document.querySelectorAll('main form input').forEach(e=>{e.removeAttribute('maxlength'); e.removeAttribute('min'); e.removeAttribute('step'); if(e.type==='number') e.type='text'})")
    fill(p, vals)
    with (contextlib_null() if ok else r.expect_errors()):
        with p.expect_response(lambda x: x.request.method == "POST" and "/plans/new" in x.url) as ri:
            p.locator("main form button:has-text('Create plan')").click()
        p.wait_for_load_state("networkidle")
    return ri.value.status


@feature(r, "Plan list")
def t_list():
    st, p = visit(r, O, PL)
    heads = [h.strip().upper() for h in p.locator("main table thead th").all_inner_texts()]
    r.ok(st == 200 and "New plan" in p.inner_text("main"), "Plan list opens with 'New plan' button", PL, O, "open", "200 + button", st)
    r.ok(heads == ["PLAN", "ASSET", "SITE", "PRIORITY", "CHECKLIST", "STATUS"], "Plan list columns", PL, O, "read thead", "PLAN/ASSET/SITE/PRIORITY/CHECKLIST/STATUS", heads)
    total = int(sql(f"select count(*) from maintenance_maintenanceplan where organization_id={ALPHA}")); pages = math.ceil(total / 20)
    rr = rows(p); r.ok(len(rr) == min(20, total) and pages >= 2, "Page 1 shows 20 rows; data spans several pages", PL, O, "count", f"20 of {total}", len(rr), db=str(total))
    bad = []
    for x in rr[:8]:
        d = sql(f"select a.asset_tag||'|'||s.code||'|'||p.priority||'|'||(p.checklist_key<>'')||'|'||p.is_active from maintenance_maintenanceplan p join assets_asset a on a.id=p.asset_id join sites_site s on s.id=p.site_id where p.name='{x[0].replace(chr(39), chr(39)*2)}' and a.asset_tag='{x[1]}' and p.organization_id={ALPHA} limit 1")
        tag, site, pri, ck, act = d.split("|")
        if not (x[1] == tag and x[2] == site and x[3].lower().replace(" ", "") == pri.lower() and (x[4] == "Yes") == (ck in ("true", "t")) and ((x[5].upper() == "ACTIVE") == (act in ("true", "t")))): bad.append((x, d))
    r.ok(not bad, "Row values (asset, site, priority, checklist, status) match the database", PL, O, "compare 8 rows", "equal", bad[:2] or "all equal")
    first = p.locator("main table tbody tr td a").first; nm = first.inner_text(); first.click(); p.wait_for_load_state("networkidle")
    r.ok("/maintenance/plans/" in p.url and nm in p.inner_text("main h1"), "Plan name link opens the plan detail", p.url, O, "click plan", "detail", p.url)
    p.goto(BASE + PL); p.locator("main a:has-text('New plan')").click(); p.wait_for_load_state("networkidle"); r.ok("/plans/new" in p.url, "'New plan' opens the create form", p.url, O, "click", "form", p.url)
    # search
    def s(qs): p.goto(BASE + PL + "?" + qs); p.wait_for_load_state("networkidle"); return rows(p)
    got = s("q=PGPLAN"); exp = sql(f"select count(*) from maintenance_maintenanceplan where organization_id={ALPHA} and (name ilike '%PGPLAN%' or exists(select 1 from assets_asset a where a.id=asset_id and a.asset_tag ilike '%PGPLAN%'))")
    r.ok(len(got) == min(20, int(exp)) and int(exp) > 0, "Search by plan name", PL, O, "q=PGPLAN", f"{min(20,int(exp))}", len(got), db=exp)
    s_all = s; s = lambda qs: [x for x in s_all(qs) if len(x) > 3]
    got = s(f"q=PMA2-{U}"); exp = sql(f"select count(*) from maintenance_maintenanceplan where organization_id={ALPHA} and asset_id='{A2}'")
    r.ok(len(got) == min(20, int(exp)), "Search by asset tag", PL, O, f"q=PMA2-{U}", exp, len(got), db=exp)
    got = s("q=gen-001"); r.ok(len(got) >= 2 and all("GEN-001" in x[1] or "gen-001" in x[0].lower() for x in got), "Search is case-insensitive and also matches asset tags (GEN-001)", PL, O, "q=gen-001", ">=2 GEN-001 plans", [x[0] for x in got])
    got = s("q=zzz-nothing"); r.ok("No plans match" in p.inner_text("main"), "Empty state when nothing matches", PL, O, "q=zzz-nothing", "'No plans match'", p.inner_text("main")[-100:].replace("\n", " "))
    got = s("q=%27%20OR%201%3D1--%20"); r.ok(p.locator("main table").count() > 0 and len(got) <= 1, "SQL-injection-like search is harmless", PL, O, "q=' OR 1=1--", "no results/no error", len(got))
    got = s("q=%3Cscript%3Ewindow.__qx%3D1%3C%2Fscript%3E"); r.ok(p.evaluate("()=>!window.__qx"), "XSS in search term is escaped", PL, O, "q=<script>", "inert", "ok")
    got = s("q=%25"); r.ok(p.locator("main table").count() > 0, "Search '%' is handled literally", PL, O, "q=%", "no error", len(got))
    # filters
    p.goto(BASE + PL); so = p.locator("main select[name=site] option").all_inner_texts(); ao = p.locator("main select[name=active] option").all_inner_texts()
    r.ok(so[0] == "All sites" and "HYD-1" in so and ao == ["All", "Enabled", "Disabled"], "Filter controls: site list + All/Enabled/Disabled", PL, O, "read options", "ok", [so[:3], ao])
    for site in ("HYD-1", "BLR-1"):
        sidv = sid(site); got = []; p.goto(BASE + PL + f"?site={sidv}")
        while True:
            got += [x[0] for x in rows(p) if len(x) > 3]; nx = p.locator("main a:has-text('Next')")
            if nx.count() == 0: break
            nx.first.click(); p.wait_for_load_state("networkidle")
        exp = sql(f"select count(*) from maintenance_maintenanceplan where organization_id={ALPHA} and site_id='{sidv}'")
        r.ok(len(got) == int(exp), f"Site filter {site}: exactly its plans ({exp})", PL, O, f"site={site}", exp, len(got), db=exp)
    # disabled filter after a plan is disabled (set up through the UI later) -> check Enabled count
    exp = sql(f"select count(*) from maintenance_maintenanceplan where organization_id={ALPHA} and is_active"); p.goto(BASE + PL + "?active=1"); n = 0
    while True:
        n += len([x for x in rows(p) if len(x) > 3]); nx = p.locator("main a:has-text('Next')")
        if nx.count() == 0: break
        nx.first.click(); p.wait_for_load_state("networkidle")
    r.ok(n == int(exp), f"'Enabled' filter matches the database ({exp})", PL, O, "active=1", exp, n, db=exp)
    for bad_ in ("site=not-a-uuid", "active=maybe"):
        resp = p.goto(BASE + PL + "?" + bad_); r.ok(resp.status == 200 and p.locator("main table").count() > 0, f"Malformed filter '{bad_}' shows a page, not an error", p.url, O, bad_, "200", resp.status)
    p.goto(BASE + PL); fill(p, {"site": HYD, "active": "1"}, "main form"); p.locator("main form button:has-text('Filter')").click(); p.wait_for_load_state("networkidle"); p.reload()
    r.ok(p.locator("main select[name=site]").input_value() == HYD and p.locator("main select[name=active]").input_value() == "1", "Selected filters persist after submit + refresh", p.url, O, "filter + reload", "kept", "ok")
    r.T("Column sorting control", PL, O, "look for sortable headers", "click to sort", "Plan table has no sorting UI or ?ordering= parameter (fixed order by plan name)", "PARTIAL")
    # pagination
    seen = []
    for n_ in range(1, pages + 1):
        p.goto(BASE + PL + f"?page={n_}"); tg = [x[0] for x in rows(p) if len(x) > 3]; seen += tg
        prev, nxt = p.locator("main a:has-text('Previous')").count(), p.locator("main a:has-text('Next')").count()
        exp = 20 if n_ < pages else total - 20 * (pages - 1)
        r.ok(len(tg) == exp and (prev > 0) == (n_ > 1) and (nxt > 0) == (n_ < pages), f"Pagination page {n_}/{pages}: {exp} rows, Previous/Next correct", p.url, O, f"page={n_}", f"{exp} rows", f"{len(tg)} prev={prev} next={nxt}")
    r.ok(len(seen) == total and len(set(seen)) == len(set(x for x in seen)), "All pages together list every plan once", PL, O, "walk pages", f"{total}", len(seen), db=str(total))
    p.goto(BASE + PL + "?active=1&page=2"); lk = p.locator("main a:has-text('Previous')"); r.ok(lk.count() and "active=1" in (lk.first.get_attribute("href") or ""), "Pagination links keep the filters", p.url, O, "page 2 + filter", "kept", lk.first.get_attribute("href") if lk.count() else "none")
    for bad_ in ("0", "-1", "abc", "9999"):
        resp = p.goto(BASE + PL + f"?page={bad_}"); r.ok(resp.status == 200 and p.locator("main table").count() > 0, f"Invalid page value '{bad_}' does not error", p.url, O, f"page={bad_}", "200", resp.status)


@feature(r, "Plan create")
def t_create():
    p = r.page(O)
    st, p = visit(r, O, PL + "new/")
    names = p.eval_on_selector_all("main form [name]", "e=>e.filter(x=>x.type!=='hidden').map(x=>x.name)")
    r.ok(names == ["asset", "name", "description", "priority", "estimated_hours", "checklist_key"], "Create form fields: asset, name, description, priority, estimated hours, checklist", PL + "new/", O, "read form", "6 fields", names)
    ao = p.locator("main select[name=asset] option").all_inner_texts(); po = p.locator("main select[name=priority] option").all_inner_texts(); co = p.locator("main select[name=checklist_key] option").all_inner_texts()
    r.ok(any(f"PMA-{U}" in o for o in ao) and any("GEN-001" in o for o in ao), "Asset dropdown lists assets as 'tag · name (site)'", PL + "new/", O, "read", "assets", ao[:3])
    r.ok(po == ["Low", "Medium", "High", "Urgent"] and co[0] == "None" and CKN in co, "Priority = Low/Medium/High/Urgent; checklist = None + org checklists", PL + "new/", O, "read", "options", [po, co])
    r.ok(p.locator("main select[name=priority]").input_value() == "MEDIUM", "Priority defaults to Medium", PL + "new/", O, "read", "MEDIUM", p.locator("main select[name=priority]").input_value())
    # retired assets are not offered
    rt = mk(f"PMT-{U}")
    for lab, rs in (("Start maintenance", "pt one"), ("Mark out of service", "pt two")):
        p.goto(BASE + f"/app/assets/{rt}/"); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{lab}')")); f.locator("[name=reason]").fill(rs)
        with p.expect_navigation(): f.locator("button").click()
    p.goto(BASE + f"/app/assets/{rt}/"); f = p.locator("main form[action*='/transition/']", has=p.locator("button:has-text('Retire')")); f.locator("[name=reason]").fill("pm test retire"); cclick(p, f.locator("button"))
    p.goto(BASE + PL + "new/"); ao = p.eval_on_selector_all("main select[name=asset] option", "o=>o.map(x=>x.value)")
    r.ok(rt not in ao, "Retired assets are not offered for new plans", PL + "new/", O, "read options", "absent", rt in ao)
    # full create
    nm = f"Full plan {U}"
    s = new_plan(p, dict(asset=A1, name=nm, description="Line1\nLine2 <b>x</b>", priority="High", estimated_hours="4.5", checklist_key=CK))
    pl = PLAN(nm); row = sql(f"select asset_id||'|'||site_id||'|'||name||'|'||replace(description,E'\\r','')||'|'||priority||'|'||estimated_hours||'|'||checklist_key||'|'||is_active from maintenance_maintenanceplan where id='{pl}'")
    exp = f"{A1}|{HYD}|{nm}|Line1\nLine2 <b>x</b>|HIGH|4.50|{CK}|true"
    r.ok(pl and row == exp and "/plans/" in p.url and "created" in p.inner_text("main").lower(), "Create plan with all fields: persisted exactly, redirect to detail + success message", p.url, O, "fill 6 fields + Create plan", "row saved", row[:120], db=row[:140], audit=audits(pl, "maintenance.plan_created"))
    t = p.inner_text("main"); r.ok(nm in t and "4.5" in t and CKN in t and "Line2" in t and "<b>x</b>" in t and "high" in t.lower() and f"PMA-{U}" in t, "Plan detail shows every value (HTML in description shown as text)", p.url, O, "read detail", "all values", t[:100].replace("\n", " "))
    r.ok(p.evaluate("()=>document.querySelectorAll('main dd b').length===0"), "HTML in the description is escaped (no <b> element)", p.url, O, "inspect DOM", "escaped", "ok")
    r.ok("No schedules" in t, "New plan shows 'No schedules' empty state", p.url, O, "read", "empty state", "ok")
    p.reload(); r.ok(nm in p.inner_text("main h1"), "Created plan survives refresh", p.url, O, "reload", "ok", "ok")
    # minimal create
    nm2 = f"Min plan {U}"; s = new_plan(p, dict(asset=A1, name=nm2)); pl2 = PLAN(nm2)
    r.ok(pl2 and sql(f"select priority||'|'||coalesce(estimated_hours::text,'-')||'|'||checklist_key||'|'||description from maintenance_maintenanceplan where id='{pl2}'") == "MEDIUM|-||", "Minimal create (asset + name): defaults MEDIUM, no hours/checklist", p.url, O, "asset+name only", "defaults", "ok", audit=audits(pl2))
    # same name on different asset is fine
    new_plan(p, dict(asset=A2, name=nm2)); r.ok(PLAN(nm2, A2), "Same plan name on a different asset is allowed", p.url, O, "same name, asset 2", "created", bool(PLAN(nm2, A2)))
    # prefill from asset link
    p.goto(BASE + PL + f"new/?asset={A1}"); r.ok(p.locator("main select[name=asset]").input_value() == A1, "Asset preselected via ?asset=", p.url, O, "open ?asset=", "preselected", p.locator("main select[name=asset]").input_value())
    p.goto(BASE + PL + "new/"); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state("networkidle"); r.ok(p.url.rstrip("/").endswith("/plans"), "Cancel returns to the plan list", p.url, O, "Cancel", "list", p.url)
    # validation
    cnt = lambda: sql(f"select count(*) from maintenance_maintenanceplan where organization_id={ALPHA}")
    def bad(label, vals, frag=None, forge=False):
        b = cnt(); base = dict(asset=A1, name=f"V {U} {abs(hash(label))%9999}"); base.update(vals)
        if forge:
            p.goto(BASE + PL + "new/")
            with r.expect_errors(): res = bfetch(p, "POST", PL + "new/", {k: v for k, v in base.items()})
            ok = cnt() == b and res["status"] in (400, 403, 404); act = f"http={res['status']} rows {b}->{cnt()}"
            if frag: ok = ok and frag.lower() in res["html"].lower();
        else:
            s_ = new_plan(p, base, ok=False); ok = cnt() == b and s_ == 400 and (frag is None or frag.lower() in p.inner_text("main").lower()); act = f"http={s_} rows {b}->{cnt()} {msgs(p)[:70]}"
        r.ok(ok, f"Validation: {label}", PL + "new/", O, "submit invalid", "400/403/404 + inline error, nothing saved" + (f" ('{frag}')" if frag else ""), act, db=f"{b}->{cnt()}")
    bad("name required", dict(name=""), "required"); bad("name whitespace only", dict(name="   "), "required"); bad("name 2 chars (min 3)", dict(name="ab"), "3 characters")
    bad("name 151 chars (max 150)", dict(name="N" * 151), "150")
    bad("duplicate name on the same asset", dict(name=nm), "already has a plan"); bad("duplicate name, different case", dict(name=nm.upper()), "already has a plan"); bad("duplicate name with padding", dict(name=f"  {nm}  "), "already has a plan")
    bad("estimated hours negative", dict(estimated_hours="-1")); bad("estimated hours text", dict(estimated_hours="abc")); bad("estimated hours 3 decimals", dict(estimated_hours="1.234")); bad("estimated hours 10000 (over 6 digits)", dict(estimated_hours="10000000"))
    bad("asset required", dict(asset=""), "required")
    nm3 = f"B3 {U}"; new_plan(p, dict(asset=A1, name="abc")); r.ok(PLAN("abc", A1), "Boundary: 3-character name accepted", p.url, O, "name 'abc'", "created", bool(PLAN("abc", A1)), audit=audits(PLAN("abc", A1)))
    new_plan(p, dict(asset=A1, name="M" * 150)); r.ok(PLAN("M" * 150, A1), "Boundary: 150-character name accepted", p.url, O, "name 150", "created", bool(PLAN("M" * 150, A1)))
    s0 = new_plan(p, dict(asset=A1, name=f"Zero hrs {U}", estimated_hours="0"), ok=False)
    r.T("Boundary: estimated hours = 0", p.url, O, "hours 0 (form allows min 0)", "accepted, or refused with a clear message consistent with the form", f"http={s0}; created={bool(PLAN(f'Zero hrs {U}', A1))}; message='{msgs(p)[:80]}'", "PARTIAL" if (s0 == 400 and "positive" in p.inner_text("main").lower()) else ("PASS" if PLAN(f"Zero hrs {U}", A1) else "FAIL"), db=str(bool(PLAN(f"Zero hrs {U}", A1))), ev="LOW: the number field accepts 0 (min=0) but the server requires > 0")
    new_plan(p, dict(asset=A1, name=f"Max hrs {U}", estimated_hours="9999.99")); r.ok(PLAN(f"Max hrs {U}", A1), "Boundary: estimated hours 9999.99 accepted", p.url, O, "hours 9999.99", "created", bool(PLAN(f"Max hrs {U}", A1)))
    new_plan(p, dict(asset=A1, name=f"<img src=x onerror=window.__px=1> {U}")); pa = r.page(O); pa.goto(BASE + PL + f"?q={U}"); r.ok(pa.evaluate("()=>!window.__px") and "<img src=x" not in pa.content(), "Stored XSS in plan name is escaped (list + detail)", pa.url, O, "name=<img onerror>", "inert", "ok")
    betaasset = sql("select id from assets_asset where organization_id<>%s limit 1" % ALPHA)
    bad("asset of another tenant (forged)", dict(asset=betaasset), forge=True); bad("non-existent asset id (forged)", dict(asset="00000000-0000-0000-0000-000000000000"), forge=True)
    bad("malformed asset id (forged)", dict(asset="abc"), forge=True); bad("retired asset (forged)", dict(asset=rt), forge=True)
    bad("invalid priority (forged)", dict(priority="CRITICAL"), forge=True); bad("unknown checklist key (forged)", dict(checklist_key="not-a-key"), forge=True)
    bad("checklist key of another tenant (forged)", dict(checklist_key=sql("select key from checklists_checklisttemplate where organization_id<>%s limit 1" % ALPHA) or "00000000-0000-0000-0000-000000000009"), forge=True)
    r.T("Plan category linkage", PL + "new/", O, "look for a category field", "plan linked to an asset category", "Plans attach to ONE asset (no category-level plans); the category is reached through the asset", "NOT APPLICABLE")
    return nm


@feature(r, "Plan edit + enable/disable")
def t_edit():
    p = r.page(O); nm = f"Full plan {U}"; pl = PLAN(nm); D = f"{PL}{pl}/"; E = D + "edit/"
    st, p = visit(r, O, E)
    v = p.eval_on_selector_all("main form [name]", "e=>Object.fromEntries(e.filter(x=>x.type!=='hidden').map(x=>[x.name,x.value]))")
    r.ok(v.get("name") == nm and v.get("priority") == "HIGH" and v.get("estimated_hours") in ("4.50", "4.5") and v.get("checklist_key") == CK and "asset" not in v, "Edit form is pre-filled; the asset cannot be changed (no asset field)", E, O, "open edit", "prefilled", {k: v[k] for k in ("name", "priority")})
    p.evaluate("()=>document.querySelectorAll('main form input').forEach(e=>{e.removeAttribute('maxlength')})")
    fill(p, dict(name=f"Edited plan {U}", description="edited", priority="Urgent", estimated_hours="9", checklist_key=""))
    p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    row = sql(f"select name||'|'||description||'|'||priority||'|'||estimated_hours||'|'||checklist_key from maintenance_maintenanceplan where id='{pl}'")
    r.ok(row == f"Edited plan {U}|edited|URGENT|9.00|" and "Saved" in p.inner_text("main"), "Edit all fields persisted (name, description, priority, hours, checklist cleared) + message", p.url, O, "change 5 fields + Save", "saved", row, db=row, audit=audits(pl, "maintenance.plan_updated"))
    ev = sql(f"select before::text||' => '||after::text from audit_auditlog where target_id='{pl}' and action='maintenance.plan_updated' order by occurred_at desc limit 1"); r.ok("Full plan" in ev and "Edited plan" in ev, "Audit stores before/after", "-", O, "audit", "before/after", ev[:90], audit=ev[:90])
    p.goto(BASE + E); fill(p, dict(name=f"Min plan {U}"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select name from maintenance_maintenanceplan where id='{pl}'") == f"Edited plan {U}" and "already has a plan" in p.inner_text("main"), "Edit: duplicate name on the same asset refused", E, O, "name=existing", "refused", msgs(p)[:70])
    p.goto(BASE + E); fill(p, dict(name="ab"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select name from maintenance_maintenanceplan where id='{pl}'") == f"Edited plan {U}", "Edit: 2-character name refused", E, O, "name 'ab'", "refused", msgs(p)[:70])
    p.goto(BASE + E)
    with r.expect_errors(): res = bfetch(p, "POST", E, {"name": f"Edited plan {U}", "priority": "URGENT", "estimated_hours": "9", "asset": A2})
    r.ok(sql(f"select asset_id from maintenance_maintenanceplan where id='{pl}'") == A1, "Forged 'asset' on edit is ignored (asset cannot be changed)", E, O, "POST asset=other", "asset unchanged", sql(f"select asset_id from maintenance_maintenanceplan where id='{pl}'") == A1)
    p.goto(BASE + E); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state("networkidle"); r.ok(pl in p.url, "Edit: Cancel returns to the plan", p.url, O, "Cancel", "detail", p.url)
    with r.expect_errors(): resp = p.goto(BASE + PL + "00000000-0000-0000-0000-000000000000/")
    r.ok(resp.status == 404, "Unknown plan id -> 404", p.url, O, "random uuid", "404", resp.status)
    # disable / enable
    p.goto(BASE + D); btn = p.locator("main form[action*='/active/'] button")
    r.ok(btn.inner_text().strip() == "Disable plan", "Active plan shows 'Disable plan'", D, O, "read", "Disable plan", btn.inner_text())
    btn.click(); dlg = p.locator("#fx-confirm"); dlg.wait_for(state="visible", timeout=3000)
    r.ok("Disable this plan" in dlg.inner_text(), "Disable asks for confirmation", D, O, "click Disable plan", "dialog", dlg.inner_text()[:70])
    dlg.locator("button:has-text('Cancel')").click(); p.wait_for_timeout(400); r.ok(sql(f"select is_active from maintenance_maintenanceplan where id='{pl}'") in ("true", "t"), "Cancel keeps the plan enabled", D, O, "Cancel", "enabled", "true")
    cclick(p, p.locator("main form[action*='/active/'] button"))
    r.ok(sql(f"select is_active from maintenance_maintenanceplan where id='{pl}'") in ("false", "f") and "disabled" in p.inner_text("main").lower(), "Disable plan: persisted, banner shown", D, O, "Confirm", "is_active=false", sql(f"select is_active from maintenance_maintenanceplan where id='{pl}'"), audit=audits(pl, "maintenance.plan_disabled"))
    r.ok(p.locator("main .alert-secondary").count() >= 1 and p.locator("main form[action*='/active/'] button").inner_text().strip() == "Enable plan", "Disabled plan: info banner + 'Enable plan' button", D, O, "read", "banner + button", "ok")
    p.goto(BASE + PL + f"?active=0&q=Edited plan {U}"); r.ok([x[0] for x in rows(p)] == [f"Edited plan {U}"] and "DISABLED" in rows(p)[0][5].upper(), "List 'Disabled' filter finds it with a DISABLED badge", p.url, O, "active=0", "listed", rows(p)[:1])
    p.goto(BASE + PL + f"?active=1&q=Edited plan {U}"); r.ok(not [x for x in rows(p) if len(x) > 3], "List 'Enabled' filter no longer lists it", p.url, O, "active=1", "absent", "ok")
    p.goto(BASE + D); p.locator("main form[action*='/active/'] button").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select is_active from maintenance_maintenanceplan where id='{pl}'") in ("true", "t") and "enabled" in p.inner_text("main").lower(), "Enable plan: persisted (no confirmation needed)", D, O, "click Enable plan", "is_active=true", "true", audit=audits(pl, "maintenance.plan_enabled"))
    with r.expect_errors(): res = bfetch(p, "POST", D + "active/", {"active": "1"})
    r.ok(res["status"] in (200, 302) and "Server Error" not in res["html"], "Enabling an already-enabled plan is harmless", D, O, "POST active=1 twice", "no error", res["status"])
    with r.expect_errors(): res = bfetch(p, "GET", D + "active/")
    r.ok(res["status"] == 405, "GET on the enable/disable URL -> 405", D, O, "GET", "405", res["status"])
    # disabled plan on retired asset cannot be enabled
    rt = mk(f"PMR-{U}"); new_plan(p, dict(asset=rt, name=f"Retire me {U}")); rp = PLAN(f"Retire me {U}")
    bfetch(p, "POST", f"{PL}{rp}/active/", {"active": "0"})
    for lab, rs in (("Start maintenance", "pr one"), ("Mark out of service", "pr two")):
        p.goto(BASE + f"/app/assets/{rt}/"); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{lab}')")); f.locator("[name=reason]").fill(rs)
        with p.expect_navigation(): f.locator("button").click()
    p.goto(BASE + f"/app/assets/{rt}/"); f = p.locator("main form[action*='/transition/']", has=p.locator("button:has-text('Retire')")); f.locator("[name=reason]").fill("pm retire"); cclick(p, f.locator("button"))
    p.goto(BASE + f"{PL}{rp}/"); p.locator("main form[action*='/active/'] button").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select is_active from maintenance_maintenanceplan where id='{rp}'") in ("false", "f") and "cannot" in p.inner_text("main").lower(), "A plan on a retired asset cannot be re-enabled", p.url, O, "Enable on retired asset", "refused with message", msgs(p)[:80], db="false")
    # asset page link <-> plan: plan detail links back to the asset
    p.goto(BASE + D); lk = p.locator(f"main a[href='/app/assets/{A1}/']"); r.ok(lk.count() >= 1, "Plan detail links to its asset", D, O, "inspect", "asset link", lk.count())
    with r.expect_errors(): res = bfetch(p, "POST", D + "edit/", {"name": "x" * 3});


for f in (t_list, t_create, t_edit):
    f()

fails = [x for x in r.rows if x["status"] == "FAIL"]; unv = [x for x in r.rows if x["status"] == "UNVERIFIED"]
print("ROWS", len(r.rows), "FAIL", len(fails), "UNVF", len(unv), "PARTIAL", len([x for x in r.rows if x['status'] == 'PARTIAL']))
for x in fails + unv: print("  ", x["status"], x["feature"], "|", str(x["action"])[:50], "|", str(x["actual"])[:170])
print("ISSUES", len(r.issues))
for i in r.issues[:25]: print("  ", i["kind"], i["feature"], i["role"], i["text"][:130], i.get("url", "")[-60:])
r.stop()
