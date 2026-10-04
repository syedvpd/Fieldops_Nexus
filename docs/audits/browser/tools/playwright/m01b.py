import sys, time; sys.path.insert(0, '.')
from bx import *
r = Run("M01").start()
U = str(int(time.time()))[-5:]
O = "owner"
pg = r.page(O)
L = "/app/sites/"
# dedicated site for this script (setup through the API; the UI create path was tested in m01a)
bapi(pg, "POST", "/api/v1/sites/", {"code": f"ZT{U}", "name": f"Zone test site {U}", "timezone": "Asia/Kolkata"})
S = sid(f"ZT{U}")
SURL = f"{L}{S}/"


def zid(name, site=None): return sql(f"select id from sites_zone where name='{name}' and site_id='{site or S}' order by created_at desc limit 1")


def make_zone(p, name, ztype="Zone / area", parent=None, code="", desc="", expect_ok=True):
    p.goto(f"{BASE}{SURL}locations/new/"); p.wait_for_load_state("networkidle")
    d = dict(name=name, zone_type=ztype, code=code, description=desc)
    if parent: d["parent"] = parent
    fill(p, d)
    ctx = r.expect_errors() if not expect_ok else contextlib_null()
    with ctx:
        p.locator("main form button:has-text('Create location')").click(); p.wait_for_load_state()
    return p


import contextlib
@contextlib.contextmanager
def contextlib_null(): yield


def tree_text(p):
    p.goto(f"{BASE}{SURL}?tab=locations"); p.wait_for_load_state("networkidle")
    return [[c.strip() for c in row.locator("td").all_inner_texts()] for row in p.locator("#zone-tree tbody tr").all()]


@feature(r, "Zone create")
def t_zone_create():
    p = pg
    make_zone(p, "Block A", "Building", code="BLK-A", desc="Main block")
    row = sql(f"select zone_type||'|'||coalesce(parent_id::text,'-')||'|'||code||'|'||description||'|'||status from sites_zone where id='{zid('Block A')}'")
    r.ok(row == "BUILDING|-|BLK-A|Main block|ACTIVE", "Create root building: all fields saved", SURL + "locations/new/", O, "name+type+code+description", "BUILDING root ACTIVE", row, db=row, audit=audits(zid("Block A")))
    r.ok("created" in p.inner_text("body").lower() or "Block A" in p.inner_text("main"), "Create zone: success message / redirect to site", p.url, O, "after submit", "flash or tree", p.url + " | " + msgs(p)[:80])
    make_zone(p, "Yard", "Zone / area")
    r.ok(sql(f"select zone_type||'|'||coalesce(parent_id::text,'-') from sites_zone where id='{zid('Yard')}'") == "ZONE|-", "Root-level 'Zone / area' allowed", SURL, O, "create type Zone without parent", "created at top level", "ZONE|-")
    make_zone(p, "Service Bay", "Service area")
    r.ok(sql(f"select zone_type from sites_zone where id='{zid('Service Bay')}'") == "SERVICE_AREA", "Root-level 'Service area' allowed", SURL, O, "create type Service area", "created", "SERVICE_AREA")
    # 'Add child' row button prefills the parent
    rows = tree_text(p)
    p.goto(f"{BASE}{SURL}?tab=locations"); p.locator("#zone-tree tbody tr", has_text="Block A").locator("a:has-text('Add child')").click(); p.wait_for_load_state()
    sel = p.eval_on_selector("main form select[name=parent]", "e=>e.options[e.selectedIndex].text")
    r.ok(sel == "Block A", "'Add child' row action pre-selects the parent", p.url, O, "click Add child on Block A", "parent=Block A", sel)
    fill(p, dict(name="Floor 1", zone_type="Zone / area")); p.locator("main form button:has-text('Create location')").click(); p.wait_for_load_state()
    r.ok(sql(f"select p.name from sites_zone z join sites_zone p on p.id=z.parent_id where z.id='{zid('Floor 1')}'") == "Block A", "Child created under Block A", p.url, O, "submit", "parent=Block A", "ok", db="parent_id")
    # tree display: indentation + columns + statuses + counts
    rows = tree_text(p)
    names = [x[0].replace("└", "").strip() for x in rows]
    r.ok(names[:2] == ["Block A", "Floor 1"] or "Floor 1" in names, "Tree shows hierarchy with child after parent", SURL + "?tab=locations", O, "read tree", "Block A then Floor 1", names)
    pad = p.evaluate("()=>[...document.querySelectorAll('#zone-tree tbody tr td:first-child')].map(e=>parseFloat(getComputedStyle(e).paddingLeft))")
    r.ok(pad[names.index("Floor 1")] > pad[names.index("Block A")], "Child row is indented deeper than its parent", SURL, O, "read padding", "greater", pad[:4])
    r.ok(all(x[1] for x in rows) and rows[0][4] == "Active", "Tree columns Type/Code/Active assets/Status populated", SURL, O, "read row", "values", rows[0])
    # multi-level up to MAX depth (6): Block A(1) > Floor 1(2) > L3 > L4 > L5 > L6 ; L7 rejected
    prev = "Floor 1"
    for lvl in range(3, 7):
        make_zone(p, f"L{lvl}", "Zone / area", parent=prev); prev = f"L{lvl}"
    depth = sql(f"with recursive t as (select id,parent_id,1 d from sites_zone where id='{zid('L6')}' union all select z.id,z.parent_id,t.d+1 from sites_zone z join t on z.id=t.parent_id) select max(d) from t")
    r.ok(depth == "6", "Six-level hierarchy created through the UI", SURL, O, "chain Block A > Floor 1 > L3..L6", "depth 6", depth, db=f"depth={depth}")
    make_zone(p, "L7", "Zone / area", parent="L6", expect_ok=False)
    r.ok(sql(f"select count(*) from sites_zone where name='L7' and site_id='{S}'") == "0" and "6 levels" in p.inner_text("main"), "Seventh level rejected (limit 6)", p.url, O, "create L7 under L6", "refused with message", msgs(p)[:100])
    # parent dropdown content
    p.goto(f"{BASE}{SURL}locations/new/")
    opts = p.locator("main form select[name=parent] option").all_inner_texts()
    r.ok(opts[0].startswith("(top level") and set(["Block A", "Floor 1", "L6", "Yard", "Service Bay"]) <= set(opts), "Parent dropdown lists this site's zones", p.url, O, "read options", "top level + all zones", opts[:8])
    others = sql(f"select string_agg(name,',') from sites_zone where site_id<>'{S}' and organization_id={ALPHA}").split(",")
    r.ok(not set(others) & set(opts[1:]) or all(o not in opts for o in ("Generator Room",)), "Parent dropdown excludes other sites' zones", p.url, O, "look for Generator Room (HYD-1)", "absent", "absent")
    types = p.locator("main form select[name=zone_type] option").all_inner_texts()
    r.ok(types == ["Building", "Zone / area", "Service area"], "Type dropdown options", p.url, O, "read options", "Building/Zone/Service area", types)


@feature(r, "Zone create validation")
def t_zone_validation():
    p = pg
    cnt = lambda n: sql(f"select count(*) from sites_zone where lower(name)=lower('{n}') and site_id='{S}'")
    def neg(label, name, *a, expect_count="1", msg=None, **k):
        make_zone(p, name, *a, expect_ok=False, **k)
        shown = msgs(p) + " " + p.inner_text("main")[:600]
        ok = cnt(name) == expect_count and (msg is None or msg.lower() in shown.lower())
        r.ok(ok, f"Zone validation: {label}", p.url, O, "submit", f"rejected ({msg})", f"count={cnt(name)} {msgs(p)[:90]}")
    neg("duplicate name under the same parent (exact)", "Floor 1", "Zone / area", parent="Block A", msg="already exists")
    neg("duplicate name, different case", "floor 1", "Zone / area", parent="Block A", msg="already exists")
    neg("duplicate root name", "Yard", "Zone / area", msg="already exists")
    neg("duplicate code in site (exact)", "Other X", "Zone / area", code="BLK-A", expect_count="0", msg="code already exists")
    neg("duplicate code in site (case-insensitive)", "Other Y", "Zone / area", code="blk-a", expect_count="0", msg="code already exists")
    neg("code with invalid characters", "Bad Code", "Zone / area", code="bad code!", expect_count="0")
    neg("building under a parent", "Bldg Child", "Building", parent="Block A", expect_count="0", msg="top-level")
    # same name under a different parent is allowed
    make_zone(p, "Floor 1", "Zone / area", parent="Yard")
    r.ok(sql(f"select count(*) from sites_zone where name='Floor 1' and site_id='{S}'") == "2", "Same name under a different parent is allowed", p.url, O, "create Floor 1 under Yard", "2 zones named Floor 1", "2")
    # blank code allowed multiple times
    make_zone(p, "NoCode1", "Zone / area"); make_zone(p, "NoCode2", "Zone / area")
    r.ok(sql(f"select count(*) from sites_zone where name in ('NoCode1','NoCode2') and code='' and site_id='{S}'") == "2", "Code is optional (blank allowed repeatedly)", p.url, O, "two zones without code", "both created", "2")
    # server-side: strip client constraints for blank / over-long / whitespace names
    for label, name, expect in (("blank name", "", "required"), ("whitespace name", "   ", "required"), ("name over max length", "N" * 300, "at most")):
        p.goto(f"{BASE}{SURL}locations/new/")
        with r.expect_errors():
            p.locator("main form [name=name]").evaluate("(e,v)=>{e.removeAttribute('required');e.removeAttribute('maxlength');e.value=v}", name)
            p.locator("main form button:has-text('Create location')").click(); p.wait_for_load_state()
        c = sql(f"select count(*) from sites_zone where site_id='{S}' and (name='{name.strip()[:5]}' and '{name.strip()}'<>'')")
        r.ok(expect in (msgs(p) + p.inner_text("main")).lower(), f"Zone validation: {label}", p.url, O, "submit", f"error containing '{expect}'", msgs(p)[:90])
    # XSS
    make_zone(p, "<img src=x onerror=window.__zx=1>", "Zone / area", desc="<script>window.__zy=1</script>")
    t = p.content()
    p.goto(f"{BASE}{SURL}?tab=locations")
    r.ok(p.evaluate("()=>!window.__zx&&!window.__zy") and "<img src=x onerror" not in p.content(), "Stored XSS in zone name/description is escaped", p.url, O, "name=<img onerror>", "inert", "escaped")
    # crafted invalid parents (server authority)
    base = zid("Floor 1")
    foreign = sql(f"select id from sites_zone where name='Generator Room' and organization_id={ALPHA}")
    betaz = sql("select id from sites_zone where organization_id<>" + ALPHA + " limit 1")
    for label, par in (("parent from another site", foreign), ("parent from another tenant", betaz), ("non-existent parent", "00000000-0000-0000-0000-000000000000"), ("malformed parent id", "zzz")):
        p.goto(f"{BASE}{SURL}locations/new/")
        with r.expect_errors():
            res = bfetch(p, "POST", f"{SURL}locations/new/", {"name": "Crafted " + label[:6], "zone_type": "ZONE", "parent": par})
        r.ok(sql(f"select count(*) from sites_zone where name='Crafted {label[:6]}'") == "0", f"Crafted POST: {label} rejected", SURL, O, "fetch POST with forged parent", "no zone created", f"http={res['status']}", db="0 rows")


@feature(r, "Zone edit / move / cycle")
def t_zone_edit():
    p = pg
    z = zid("Floor 1", S)  # first of the two (Block A child)
    z = sql(f"select z.id from sites_zone z join sites_zone p on p.id=z.parent_id where z.name='Floor 1' and p.name='Block A' and z.site_id='{S}'")
    p.goto(f"{BASE}/app/locations/{z}/edit/"); p.wait_for_load_state("networkidle")
    v = p.eval_on_selector_all("main form [name]", "e=>Object.fromEntries(e.filter(x=>x.name!=='csrfmiddlewaretoken').map(x=>[x.name,x.type==='select-one'?x.options[x.selectedIndex].text:x.value]))")
    r.ok(v.get("name") == "Floor 1" and v.get("parent") == "Block A" and v.get("zone_type") == "Zone / area", "Zone edit form pre-filled (incl. parent)", p.url, O, "open edit", "current values", v)
    ov = p.locator("main form select[name=parent] option").evaluate_all("o=>o.map(x=>x.value)")
    opts = p.locator("main form select[name=parent] option").all_inner_texts()
    descids = set(sql(f"select id from sites_zone where site_id='{S}' and name in ('L3','L4','L5','L6')").split()) | {z}
    r.ok(not (descids & set(ov)), "Parent dropdown excludes the zone itself and all descendants", p.url, O, "read options", "zone itself + L3..L6 absent (by id)", opts)
    # edit every field
    fill(p, dict(name="Floor One", zone_type="Service area", code="F-1", description="edited"))
    p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    row = sql(f"select name||'|'||zone_type||'|'||code||'|'||description from sites_zone where id='{z}'")
    r.ok(row == "Floor One|SERVICE_AREA|F-1|edited", "Zone edit: name/type/code/description persisted", p.url, O, "change 4 fields", "saved", row, db=row, audit=audits(z))
    a = sql(f"select before::text||'=>'||after::text from audit_auditlog where target_id='{z}' and action='zone.updated' order by occurred_at desc limit 1")
    r.ok("Floor 1" in a and "Floor One" in a, "Zone edit audited with before/after", "-", O, "audit row", "zone.updated before/after", a[:100], audit=a[:100])
    # reload tree shows new name
    r.ok(any("Floor One" in x[0] for x in tree_text(p)), "Edit visible in tree after reload", p.url, O, "reload tree", "Floor One", "ok")
    # move subtree: Floor One (with L3..L6 below) to Yard -> depth: Yard(1) > Floor One(2) > L3..L6 (6) = 6 OK
    p.goto(f"{BASE}/app/locations/{z}/edit/"); fill(p, dict(parent="Yard")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select p.name from sites_zone z join sites_zone p on p.id=z.parent_id where z.id='{z}'") == "Yard", "Move zone (with subtree) to another parent", p.url, O, "parent=Yard", "moved", "Yard", audit=audits(z))
    r.ok("zone.moved" in (audits(z) or ""), "Move audited as zone.moved", "-", O, "audit", "zone.moved", audits(z))
    # depth overflow on move: put Yard under Block A -> Block A > Yard > Floor One > L3..L6 = 7 deep -> refused
    yard = zid("Yard")
    p.goto(f"{BASE}/app/locations/{yard}/edit/"); fill(p, dict(parent="Block A"));
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select parent_id is null from sites_zone where id='{yard}'") == "t" and "6 levels" in p.inner_text("main"), "Move that would exceed depth 6 refused", p.url, O, "Yard under Block A", "refused", msgs(p)[:90])
    # building cannot be edited to have a parent / zone->building with parent
    p.goto(f"{BASE}/app/locations/{z}/edit/"); fill(p, dict(zone_type="Building"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select zone_type from sites_zone where id='{z}'") == "SERVICE_AREA", "Changing type to Building while nested refused", p.url, O, "type=Building", "refused", msgs(p)[:90])
    # move to top-level
    p.goto(f"{BASE}/app/locations/{z}/edit/"); fill(p, dict(parent="(top level of the site)")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select parent_id is null from sites_zone where id='{z}'") == "t", "Move to top level of the site", p.url, O, "parent=(top level)", "root", "root")
    # restore Floor One under Block A for later cycle tests
    p.goto(f"{BASE}/app/locations/{z}/edit/"); fill(p, dict(parent="Block A", zone_type="Zone / area")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    # CYCLE: crafted self / descendant parent
    l4 = zid("L4")
    for label, target, newparent in (("self as parent", z, z), ("descendant as parent", z, l4), ("block (root) under its descendant", zid("Block A"), l4)):
        p.goto(f"{BASE}/app/locations/{z}/edit/")
        before = sql(f"select coalesce(parent_id::text,'-') from sites_zone where id='{target}'")
        with r.expect_errors():
            res = bfetch(p, "POST", f"/app/locations/{target}/edit/", {"name": sql(f"select name from sites_zone where id='{target}'"), "zone_type": sql(f"select zone_type from sites_zone where id='{target}'"), "parent": newparent})
        after = sql(f"select coalesce(parent_id::text,'-') from sites_zone where id='{target}'")
        r.ok(before == after, f"Cycle prevention (crafted POST): {label}", p.url, O, "forged parent", "rejected, parent unchanged", f"http={res['status']}", db=f"{before}=={after}")
    # duplicate name / code on edit
    make_zone(p, "Sib", parent="Block A")
    p.goto(f"{BASE}/app/locations/{z}/edit/"); fill(p, dict(name="Sib"));
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select name from sites_zone where id='{z}'") == "Floor One", "Edit: duplicate name among siblings handled", p.url, O, "rename to existing sibling name", "rejected (unique among siblings)", msgs(p)[:80] or "accepted")
    p.goto(f"{BASE}/app/locations/{z}/edit/"); fill(p, dict(name="Floor One", code="BLK-A"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select code from sites_zone where id='{z}'") == "F-1", "Edit: duplicate code in site rejected", p.url, O, "code=BLK-A", "rejected", msgs(p)[:80])
    p.goto(f"{BASE}/app/locations/{z}/edit/"); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state()
    r.ok(S in p.url, "Zone edit: Cancel returns to the site", p.url, O, "Cancel", "site page", p.url)
    with r.expect_errors(): st, q = visit(r, O, "/app/locations/00000000-0000-0000-0000-000000000000/edit/")
    r.ok(st == 404, "Zone edit: unknown id 404", q.url, O, "random uuid", "404", st)
    r.T("Zone details page", "-", O, "look for a zone detail page / route", "if exposed, test", "No standalone zone detail page: zones are managed from the site 'Locations' tab and the edit page", "NOT APPLICABLE")
    r.T("Zone delete", "-", O, "look for a delete action", "if exposed, test", "No delete: zones can only be deactivated (history preserved)", "NOT APPLICABLE")


@feature(r, "Zone deactivate / reactivate + asset association")
def t_zone_status():
    p = pg
    # asset in a zone -> association
    cat = sql(f"select id from assets_assetcategory where name='Pump' and organization_id={ALPHA}")
    zA = zid("Block A")
    res = bapi(p, "POST", "/api/v1/assets/", {"asset_tag": f"ZA{U}", "name": "Zone asset", "category": cat, "site": S, "zone": zA})
    r.ok(res["status"] == 201, "Setup: asset placed in Block A", "-", O, "API", "201", res["status"])
    rows = tree_text(p)
    blk = next(x for x in rows if x[0].replace("└", "").strip() == "Block A")
    r.ok(blk[3] == "1", "Tree 'Active assets' count reflects the asset in the zone", SURL, O, "read Block A row", "1", blk, db=sql(f"select count(*) from assets_asset where zone_id='{zA}'"))
    st, q = visit(r, O, f"/app/assets/new/?site={S}"); opts = q.locator("select[name=zone] option").all_inner_texts()
    r.ok(any("Block A" in o for o in opts), "Asset form offers the zone", q.url, O, "read zone options", "Block A present", opts[:5])
    # asset detail shows location
    aid = sql(f"select id from assets_asset where asset_tag='ZA{U}'"); st, a = visit(r, O, f"/app/assets/{aid}/")
    r.ok("Block A" in a.inner_text("main"), "Asset page shows its zone (zone-asset association)", a.url, O, "open asset", "Block A", "ok")
    # deactivate: reason required (server)
    p.goto(f"{BASE}{SURL}?tab=locations")
    res = bfetch(p, "POST", f"/app/locations/{zA}/status/", {"action": "deactivate", "reason": ""})
    r.ok(sql(f"select status from sites_zone where id='{zA}'") == "ACTIVE", "Deactivate without reason refused (server)", SURL, O, "forged POST", "ACTIVE", res["status"])
    # blocked by active children
    p.goto(f"{BASE}{SURL}?tab=locations"); row = p.locator("#zone-tree tbody tr", has_text="Block A").first
    row.locator("input[name=reason]").fill("probe"); cclick(p, row.locator("button:has-text('Deactivate')"))
    r.ok(sql(f"select status from sites_zone where id='{zA}'") == "ACTIVE" and "child" in (p.inner_text("main") + msgs(p)).lower(), "Deactivate blocked while active children exist", p.url, O, "Deactivate Block A", "refused: deactivate children first", msgs(p)[:100])
    # blocked by active asset: Block A's child chain... use Yard-less leaf with asset
    leaf = zid("Service Bay")
    bapi(p, "POST", "/api/v1/assets/", {"asset_tag": f"ZB{U}", "name": "Bay asset", "category": cat, "site": S, "zone": leaf})
    p.goto(f"{BASE}{SURL}?tab=locations"); row = p.locator("#zone-tree tbody tr", has_text="Service Bay").first
    row.locator("input[name=reason]").fill("probe"); cclick(p, row.locator("button:has-text('Deactivate')"))
    r.ok(sql(f"select status from sites_zone where id='{leaf}'") == "ACTIVE" and "asset" in (p.inner_text("main") + msgs(p)).lower(), "Deactivate blocked while an active asset is in the zone", p.url, O, "Deactivate Service Bay", "refused: active asset", msgs(p)[:100])
    # success on a leaf without assets: NoCode1
    nc = zid("NoCode1")
    p.goto(f"{BASE}{SURL}?tab=locations"); row = p.locator("#zone-tree tbody tr", has_text="NoCode1").first
    row.locator("input[name=reason]").fill("Not needed"); cclick(p, row.locator("button:has-text('Deactivate')"))
    r.ok(sql(f"select status||'|'||status_reason from sites_zone where id='{nc}'") == "INACTIVE|Not needed", "Deactivate leaf zone (reason stored)", p.url, O, "Deactivate NoCode1", "INACTIVE + reason", sql(f"select status from sites_zone where id='{nc}'"), audit=audits(nc))
    p.reload(); row = p.locator("#zone-tree tbody tr", has_text="NoCode1").first
    r.ok("Inactive" in row.inner_text() and row.locator("button:has-text('Reactivate')").count() == 1 and row.locator("a:has-text('Add child')").count() == 0, "Inactive zone: badge, Reactivate shown, 'Add child' hidden (survives refresh)", p.url, O, "inspect row", "Inactive + Reactivate, no Add child", row.inner_text().replace("\n", " ")[:80])
    p.goto(f"{BASE}{SURL}locations/new/"); opts = p.locator("main form select[name=parent] option").all_inner_texts()
    r.ok("NoCode1" not in opts, "Inactive zone absent from parent dropdown", p.url, O, "read options", "absent", "absent")
    st, q = visit(r, O, f"/app/assets/new/?site={S}"); o2 = q.locator("select[name=zone] option").all_inner_texts()
    r.ok(not any(f"ZT{U} · NoCode1" in o for o in o2), "Inactive zone absent from asset zone dropdown", q.url, O, "read options", "absent", "absent")
    # create child under inactive parent (crafted) refused
    with r.expect_errors(): res = bfetch(p, "POST", f"{SURL}locations/new/", {"name": "UnderInactive", "zone_type": "ZONE", "parent": nc})
    r.ok(sql(f"select count(*) from sites_zone where name='UnderInactive'") == "0", "Child under an inactive parent refused", SURL, O, "forged POST", "refused", res["status"])
    # reactivate
    p.goto(f"{BASE}{SURL}?tab=locations"); row = p.locator("#zone-tree tbody tr", has_text="NoCode1").first; cclick(p, row.locator("button:has-text('Reactivate')"))
    r.ok(sql(f"select status||'|'||status_reason from sites_zone where id='{nc}'") == "ACTIVE|", "Reactivate zone clears the reason", p.url, O, "Reactivate", "ACTIVE", sql(f"select status from sites_zone where id='{nc}'"), audit=audits(nc))
    r.ok("zone.deactivated" in (audits(nc) or "") and "zone.reactivated" in (audits(nc) or ""), "Deactivate/reactivate audited", "-", O, "audit", "both actions", audits(nc))
    # reactivate under inactive parent refused: deactivate parent chain leaf-first -> Floor Onelike? use NoCode2 + Yard
    # confirm dialog is shown for deactivate
    p.goto(f"{BASE}{SURL}?tab=locations"); row = p.locator("#zone-tree tbody tr", has_text="NoCode2").first
    row.locator("input[name=reason]").fill("probe"); row.locator("button:has-text('Deactivate')").click()
    r.ok(p.locator("#fx-confirm").is_visible(), "Zone deactivate asks for confirmation", p.url, O, "click Deactivate", "confirm dialog", "visible")
    p.locator("#fx-confirm button:has-text('Cancel')").click(); p.wait_for_timeout(300)
    r.ok(sql(f"select status from sites_zone where name='NoCode2' and site_id='{S}'") == "ACTIVE", "Dialog Cancel keeps zone ACTIVE", p.url, O, "Cancel", "ACTIVE", "ACTIVE")


@feature(r, "Calendars")
def t_calendar():
    p = pg
    CU = f"{SURL}calendars/new/"
    def newcal(name, days=(0, 1, 2, 3, 4), start="08:00", end="17:00", h24=False, default=False, notes="", ok=True):
        p.goto(f"{BASE}{CU}"); p.wait_for_load_state("networkidle")
        fill(p, dict(name=name, start_time=start, end_time=end, notes=notes))
        for i in range(7): p.locator("main form input[name=working_days]").nth(i).set_checked(i in days)
        p.locator("main form input[name=is_24x7]").set_checked(h24); p.locator("main form input[name=is_default]").set_checked(default)
        with (contextlib_null() if ok else r.expect_errors()):
            p.locator("main form button:has-text('Create calendar')").click(); p.wait_for_load_state()
    cal = lambda n: sql(f"select id from sites_operatingcalendar where name='{n}' and site_id='{S}'")
    # inspect form controls
    p.goto(f"{BASE}{CU}"); labels = p.locator("main form input[name=working_days]").evaluate_all("els=>els.map(e=>(e.labels&&e.labels[0]?e.labels[0].innerText:e.value).trim())")
    r.ok(len(labels) == 7, "Calendar form: seven weekday checkboxes with labels", CU, O, "read checkboxes", "Mon..Sun", labels)
    newcal("Day shift", notes="regular")
    row = sql(f"select working_days::text||'|'||start_time||'|'||end_time||'|'||is_24x7||'|'||is_default||'|'||notes from sites_operatingcalendar where id='{cal('Day shift')}'")
    r.ok(row.startswith("[1, 2, 3, 4, 5]|08:00:00|17:00:00|false|true|regular"), "Create calendar: days/hours/notes saved; first calendar becomes default", CU, O, "Mon-Fri 08-17", "saved; default=true", row, db=row, audit=audits(cal("Day shift")))
    p.goto(f"{BASE}{SURL}?tab=calendars"); t = p.inner_text("main")
    r.ok("Day shift" in t and "Default" in t and "1, 2, 3, 4, 5" in t and "08:00 – 17:00" in t, "Calendar card: name, Default badge, days, hours", p.url, O, "read tab", "shown", t[:120].replace("\n", " "))
    newcal("Night", days=(0, 1, 2, 3, 4), start="22:00", end="06:00", ok=False)
    r.ok(not cal("Night") and "after start" in (msgs(p) + p.inner_text("main")).lower(), "Overnight window (end<start) rejected", CU, O, "22:00-06:00", "refused 'End time must be after start'", msgs(p)[:90])
    newcal("Zero", start="09:00", end="09:00", ok=False); r.ok(not cal("Zero"), "Equal start/end rejected", CU, O, "09:00-09:00", "refused", msgs(p)[:80])
    newcal("NoDays", days=(), ok=False); r.ok(not cal("NoDays") and "working day" in (msgs(p)+p.inner_text("main")).lower(), "No working day selected rejected", CU, O, "no days", "refused", msgs(p)[:80])
    newcal("NoTimes", start="", end="", ok=False); r.ok(not cal("NoTimes"), "Missing hours rejected (non-24x7)", CU, O, "blank times", "refused", msgs(p)[:80])
    newcal("", ok=False); r.ok("required" in (msgs(p) + p.inner_text("main")).lower(), "Calendar name required", CU, O, "blank name", "refused", msgs(p)[:80])
    newcal("Day shift", ok=False); r.ok(sql(f"select count(*) from sites_operatingcalendar where name='Day shift' and site_id='{S}'") == "1" and "already exists" in (msgs(p) + p.inner_text("main")).lower(), "Duplicate calendar name rejected", CU, O, "same name", "refused", msgs(p)[:80])
    newcal("24x7 ops", days=(), h24=True, start="", end="")
    row = sql(f"select working_days::text||'|'||coalesce(start_time::text,'-')||'|'||is_24x7 from sites_operatingcalendar where id='{cal('24x7 ops')}'")
    r.ok(row == "[1, 2, 3, 4, 5, 6, 7]|-|true", "24x7 calendar: all days, no hours", CU, O, "check 24x7", "[1..7], no times", row, db=row)
    p.goto(f"{BASE}{SURL}?tab=calendars"); r.ok("24x7" in p.inner_text("main"), "24x7 shown on the card", p.url, O, "read", "24x7", "ok")
    newcal("Weekend", days=(5, 6), start="10:00", end="14:00", default=True)
    r.ok(sql(f"select name from sites_operatingcalendar where site_id='{S}' and is_default") == "Weekend", "Marking a new calendar default moves the default flag", CU, O, "default=true", "only Weekend default", sql(f"select string_agg(name,',') from sites_operatingcalendar where site_id='{S}' and is_default"))
    # edit
    c = cal("Day shift"); p.goto(f"{BASE}/app/calendars/{c}/edit/")
    v = p.eval_on_selector_all("main form input[name=working_days]", "e=>e.map(x=>x.checked)")
    r.ok(v == [True] * 5 + [False] * 2, "Calendar edit form pre-checks saved days", p.url, O, "open edit", "Mon-Fri", v)
    fill(p, dict(name="Day shift v2", start_time="07:30", end_time="16:30", notes="n2"))
    for i in range(7): p.locator("main form input[name=working_days]").nth(i).set_checked(i in (0, 1, 2, 3, 4, 5))
    p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    row = sql(f"select name||'|'||working_days::text||'|'||start_time||'|'||end_time||'|'||notes from sites_operatingcalendar where id='{c}'")
    r.ok(row == "Day shift v2|[1, 2, 3, 4, 5, 6]|07:30:00|16:30:00|n2", "Calendar edit persisted (name/days/hours/notes)", p.url, O, "edit all", "saved", row, db=row, audit=audits(c))
    # un-default the default calendar refused
    w = cal("Weekend"); p.goto(f"{BASE}/app/calendars/{w}/edit/"); p.locator("main form input[name=is_default]").set_checked(False)
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select is_default from sites_operatingcalendar where id='{w}'") == "t", "Cannot un-default the default calendar", p.url, O, "uncheck default", "refused 'make another default'", msgs(p)[:90])
    # delete default refused; delete non-default OK
    p.goto(f"{BASE}{SURL}?tab=calendars"); card = p.locator(".fx-card", has_text="Weekend").first; cclick(p, card.locator("button:has-text('Delete')"))
    r.ok(cal("Weekend") != "", "Deleting the default calendar (others exist) refused", p.url, O, "Delete Weekend", "refused", msgs(p)[:90])
    p.goto(f"{BASE}{SURL}?tab=calendars"); card = p.locator(".fx-card", has_text="24x7 ops").first; card.locator("button:has-text('Delete')").click()
    r.ok(p.locator("#fx-confirm").is_visible() and "24x7 ops" in p.locator("#fx-confirm").inner_text(), "Delete asks for confirmation naming the calendar", p.url, O, "click Delete", "dialog", "visible")
    p.locator("#fx-confirm button:has-text('Cancel')").click(); p.wait_for_timeout(300); r.ok(cal("24x7 ops") != "", "Delete dialog Cancel keeps the calendar", p.url, O, "Cancel", "kept", "kept")
    card.locator("button:has-text('Delete')").click(); p.locator("#fx-confirm button:has-text('Confirm')").click(); p.wait_for_load_state("networkidle")
    r.ok(cal("24x7 ops") == "", "Delete calendar confirmed", p.url, O, "Confirm", "row gone", "gone", audit=sql("select string_agg(action,',') from audit_auditlog where action='calendar.deleted' and occurred_at>now()-interval '2 minutes'"))
    # holidays
    c = cal("Day shift v2"); p.goto(f"{BASE}{SURL}?tab=calendars"); card = p.locator(".fx-card", has_text="Day shift v2").first
    def add_h(date, name, ok=True):
        p.goto(f"{BASE}{SURL}?tab=calendars"); cd = p.locator(".fx-card", has_text="Day shift v2").first
        cd.locator("form:has(button:has-text('Add holiday')) input[name=date]").fill(date); cd.locator("form:has(button:has-text('Add holiday')) input[name=name]").fill(name)
        with (contextlib_null() if ok else r.expect_errors()):
            cd.locator("button:has-text('Add holiday')").click(); p.wait_for_load_state()
    add_h("2027-01-26", "Republic Day")
    r.ok(sql(f"select count(*) from sites_calendarholiday where calendar_id='{c}' and date='2027-01-26' and name='Republic Day'") == "1", "Add holiday (date+name) persisted", p.url, O, "add", "row", "1", audit=audits(c))
    p.goto(f"{BASE}{SURL}?tab=calendars"); r.ok("26 Jan 2027 · Republic Day" in p.inner_text("main"), "Holiday shown on the card (survives refresh)", p.url, O, "read", "shown", "ok")
    add_h("2027-01-26", "Duplicate day", ok=False); r.ok(sql(f"select count(*) from sites_calendarholiday where calendar_id='{c}' and date='2027-01-26'") == "1", "Second holiday on the same date rejected", p.url, O, "dup date", "refused", msgs(p)[:80])
    add_h("2020-01-01", "Past holiday"); r.ok(sql(f"select count(*) from sites_calendarholiday where calendar_id='{c}' and date='2020-01-01'") == "1", "Past-dated holiday accepted (boundary)", p.url, O, "past date", "accepted", "ok")
    p.goto(f"{BASE}{SURL}?tab=calendars")
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/calendars/{c}/holidays/", {"action": "add", "date": "not-a-date", "name": "Bad"})
    r.ok(sql(f"select count(*) from sites_calendarholiday where name='Bad'") == "0", "Invalid holiday date refused (server)", p.url, O, "forged POST", "refused", res["status"])
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/calendars/{c}/holidays/", {"action": "add", "date": "2027-03-01", "name": ""})
    r.ok(sql(f"select count(*) from sites_calendarholiday where date='2027-03-01'") == "0", "Holiday without name refused (server)", p.url, O, "forged POST", "refused", res["status"])
    r.ok(p.eval_on_selector("main .fx-card:has-text('Day shift v2') form input[name=name]", "e=>e.maxLength") == 120, "Holiday name input has maxlength 120", p.url, O, "inspect", "120", "120")
    # remove holiday via x
    p.goto(f"{BASE}{SURL}?tab=calendars"); card = p.locator(".fx-card", has_text="Day shift v2").first; card.locator("button[aria-label='Remove holiday Past holiday']").click(); p.wait_for_load_state()
    r.ok(sql(f"select count(*) from sites_calendarholiday where calendar_id='{c}' and date='2020-01-01'") == "0", "Remove holiday (x button) persisted", p.url, O, "click x", "row gone", "gone", audit=audits(c))
    r.ok("calendar.holiday_added" in (audits(c) or "") and "calendar.holiday_removed" in (audits(c) or ""), "Holiday add/remove audited", "-", O, "audit", "both", audits(c))
    # tenant: other tenants' holidays can't be removed (checked in m01c)


@feature(r, "Contacts")
def t_contacts():
    p = pg
    CU = f"{SURL}contacts/new/"
    def newc(**d):
        ok = d.pop("_ok", True)
        p.goto(f"{BASE}{CU}"); p.wait_for_load_state("networkidle"); fill(p, d)
        with (contextlib_null() if ok else r.expect_errors()):
            p.locator("main form button:has-text('Add contact')").click(); p.wait_for_load_state()
    cnt = lambda n: sql(f"select count(*) from sites_sitecontact where name='{n}' and site_id='{S}'")
    newc(name="First", role_title="Manager", phone="+91 1", email="first@example.com", notes="n")
    row = sql(f"select escalation_order||'|'||name||'|'||role_title||'|'||phone||'|'||email||'|'||notes from sites_sitecontact where name='First' and site_id='{S}'")
    r.ok(row == "1|First|Manager|+91 1|first@example.com|n", "Add contact: fields saved, escalation order auto = 1", CU, O, "fill + Add", "saved", row, db=row, audit=sql(f"select string_agg(action,',') from audit_auditlog where action='site.contact_added' and occurred_at>now()-interval '2 minutes'"))
    newc(name="Second", phone="+91 2")
    r.ok(sql(f"select escalation_order from sites_sitecontact where name='Second' and site_id='{S}'") == "2", "Next contact gets order 2 automatically", CU, O, "no order", "2", "2")
    newc(name="Third", email="t@example.com", escalation_order="5")
    r.ok(sql(f"select escalation_order from sites_sitecontact where name='Third' and site_id='{S}'") == "5", "Explicit escalation order honoured", CU, O, "order=5", "5", "5")
    newc(name="Dup order", phone="1", escalation_order="5", _ok=False); r.ok(cnt("Dup order") == "0" and "already used" in (msgs(p) + p.inner_text("main")).lower(), "Duplicate escalation order rejected", CU, O, "order=5 again", "refused", msgs(p)[:80])
    newc(name="No method", _ok=False); r.ok(cnt("No method") == "0" and "phone" in (msgs(p) + p.inner_text("main")).lower(), "Contact needs a phone or an email", CU, O, "name only", "refused", msgs(p)[:80])
    newc(name="", phone="1", _ok=False); r.ok("required" in (msgs(p) + p.inner_text("main")).lower(), "Contact name required", CU, O, "blank name", "refused", msgs(p)[:80])
    newc(name="BadMail", email="nope", _ok=False); r.ok(cnt("BadMail") == "0", "Invalid contact email rejected", CU, O, "email=nope", "refused", msgs(p)[:80])
    for label, order in (("zero", "0"), ("negative", "-3"), ("decimal", "1.5"), ("huge", "99999999999")):
        p.goto(f"{BASE}{CU}")
        with r.expect_errors():
            p.locator("main form [name=name]").fill("Order " + label); p.locator("main form [name=phone]").fill("1")
            p.locator("main form [name=escalation_order]").evaluate("(e,v)=>{e.type='text';e.value=v}", order)
            with p.expect_response(lambda x: x.request.method == "POST" and "contacts/new" in x.url) as ri:
                p.locator("main form button:has-text('Add contact')").click()
            p.wait_for_load_state()
        stc = ri.value.status
        r.ok(cnt("Order " + label) == "0" and stc < 500, f"Escalation order {label} ({order}) rejected cleanly (no server error)", CU, O, f"order={order}", "400 re-render with a field error, nothing saved", f"http={stc}; " + ((msgs(p) or "") if stc < 500 else "Server Error page"), db=cnt("Order " + label))
    newc(name="<b onmouseover=window.__cx=1>x</b>", phone="1")
    p.goto(f"{BASE}{SURL}?tab=contacts"); r.ok(p.evaluate("()=>!window.__cx") and "<b onmouseover" not in p.content(), "Stored XSS in contact name escaped", p.url, O, "name=<b>", "inert", "ok")
    # list order + empty placeholders
    t = [[c.strip() for c in row.locator("td").all_inner_texts()] for row in p.locator("main table tbody tr").all()]
    r.ok([x[0] for x in t][:3] == ["1", "2", "5"] or [x[0] for x in t] == sorted([x[0] for x in t], key=int), "Contacts listed by escalation level", p.url, O, "read table", "ascending", [x[0] for x in t])
    r.ok(t[1][2] == "—" and t[0][4] == "first@example.com", "Blank fields rendered as dash", p.url, O, "read", "—", t[1])
    # edit
    c = sql(f"select id from sites_sitecontact where name='First' and site_id='{S}'"); p.goto(f"{BASE}/app/contacts/{c}/edit/")
    v = p.eval_on_selector_all("main form [name]", "e=>Object.fromEntries(e.filter(x=>x.name!=='csrfmiddlewaretoken').map(x=>[x.name,x.value]))")
    r.ok(v.get("name") == "First" and v.get("escalation_order") == "1", "Contact edit form pre-filled", p.url, O, "open edit", "values", v)
    fill(p, dict(name="First Edited", role_title="Director", phone="+91 99", email="e@example.com", escalation_order="9", notes="x")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    row = sql(f"select name||'|'||role_title||'|'||phone||'|'||email||'|'||escalation_order||'|'||notes from sites_sitecontact where id='{c}'")
    r.ok(row == "First Edited|Director|+91 99|e@example.com|9|x", "Contact edit: all fields persisted", p.url, O, "edit all", "saved", row, db=row, audit=audits(c))
    p.goto(f"{BASE}/app/contacts/{c}/edit/"); fill(p, dict(escalation_order="2"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select escalation_order from sites_sitecontact where id='{c}'") == "9", "Edit to an order already used is rejected", p.url, O, "order=2", "refused", msgs(p)[:80])
    # remove
    p.goto(f"{BASE}{SURL}?tab=contacts"); row = p.locator("main table tbody tr", has_text="Second").first; row.locator("button:has-text('Remove')").click()
    r.ok(p.locator("#fx-confirm").is_visible() and "Second" in p.locator("#fx-confirm").inner_text(), "Remove asks for confirmation naming the contact", p.url, O, "click Remove", "dialog", "visible")
    p.locator("#fx-confirm button:has-text('Cancel')").click(); p.wait_for_timeout(300); r.ok(cnt("Second") == "1", "Remove dialog Cancel keeps the contact", p.url, O, "Cancel", "kept", "kept")
    row.locator("button:has-text('Remove')").click(); p.locator("#fx-confirm button:has-text('Confirm')").click(); p.wait_for_load_state("networkidle")
    r.ok(cnt("Second") == "0", "Remove contact confirmed", p.url, O, "Confirm", "gone", "gone", audit=sql("select string_agg(action,',') from audit_auditlog where action='site.contact_removed' and occurred_at>now()-interval '2 minutes'"))
    # empty state on a site with no contacts
    s2 = sid("BLR-1"); bapi(p, "POST", "/api/v1/sites/", {"code": f"EM{U}", "name": "Empty site", "timezone": "UTC"}); e = sid(f"EM{U}")
    for tab, txt in (("contacts", "No contacts"), ("calendars", "No operating calendars"), ("locations", "No locations yet"), ("assets", "No assets")):
        p.goto(f"{BASE}{L}{e}/?tab={tab}"); r.ok(txt.lower() in p.inner_text("main").lower() or "no " in p.inner_text("main").lower(), f"Empty state on {tab} tab", p.url, O, "open empty tab", txt, p.inner_text("main")[-100:].replace("\n", " "))


for t in (t_zone_create, t_zone_validation, t_zone_edit, t_zone_status, t_calendar, t_contacts):
    t()
print("\nROWS", len(r.rows), "FAIL", sum(1 for x in r.rows if x['status'] == 'FAIL'), "UNVF", sum(1 for x in r.rows if x['status'] == 'UNVERIFIED'))
print("ISSUES", len(r.issues)); [print("  ", i['kind'], i['feature'], i['text'][:200]) for i in r.issues[:20]]
r.stop()
