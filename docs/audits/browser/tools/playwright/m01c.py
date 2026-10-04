import sys, time, json; sys.path.insert(0, '.')
from bx import *
r = Run("M01").start()
U = str(int(time.time()))[-5:]
O = "owner"
pg = r.page(O)
ROLE_LIST = ["owner", "admin", "ops", "supervisor", "assets", "planner", "tech", "tech2", "stores", "service", "auditor", "client"]
LAB = {"owner": "Organization Owner", "admin": "Organization Admin", "ops": "Operations Manager", "supervisor": "Maintenance Supervisor", "assets": "Asset Manager",
       "planner": "Maintenance Planner", "tech": "Technician", "tech2": "Technician (2)", "stores": "Stores Manager", "service": "Service Manager", "auditor": "Auditor", "client": "Client / Requester"}

# ------------------------------------------------------------------ setup (owner, not under test): dedicated RBAC site with zone/calendars/contact per role
def form_post(p, path, data):
    return bfetch(p, "POST", path, data)

res = bapi(pg, "POST", "/api/v1/sites/", {"code": f"RB{U}", "name": f"RBAC site {U}", "timezone": "Asia/Kolkata"})
S = sid(f"RB{U}")
SURL = f"/app/sites/{S}/"
form_post(pg, f"{SURL}locations/new/", {"name": "RB zone", "zone_type": "ZONE", "parent": "", "code": "", "description": ""})
Z = sql(f"select id from sites_zone where site_id='{S}' and name='RB zone'")
form_post(pg, f"{SURL}calendars/new/", {"name": "RB base", "working_days": ["1", "2", "3"], "start_time": "08:00", "end_time": "17:00", "is_default": "on", "notes": ""})
for ro in ROLE_LIST:
    form_post(pg, f"{SURL}calendars/new/", {"name": f"Del-{ro}", "working_days": ["1"], "start_time": "08:00", "end_time": "17:00", "notes": ""})
C = sql(f"select id from sites_operatingcalendar where site_id='{S}' and name='RB base'")
form_post(pg, f"{SURL}contacts/new/", {"name": "RB contact", "phone": "1", "role_title": "", "email": "", "notes": ""})
K = sql(f"select id from sites_sitecontact where site_id='{S}' and name='RB contact'")
print("setup", S, Z, C, K)
HYD = sid("HYD-1")


def ok_status(st): return st in (200, 302)


def attempt(role, code, label, method, path, data, probe_sql, expect_change_fn=None, restore=None):
    """real browser request as `role`; expected outcome from DB permission config"""
    p = r.page(role)
    allowed = perm(role, code)
    before = sql(probe_sql)
    with (contextlib_null() if allowed else r.expect_errors()):
        res = bfetch(p, method, path, data)
    after = sql(probe_sql)
    changed = before != after
    if allowed:
        good = ok_status(res["status"]) and changed
        exp = "allowed: request succeeds and DB changes"
    else:
        good = res["status"] in (403, 404) and not changed
        exp = "denied: 403/404 and DB unchanged"
    r.ok(good, f"RBAC {label}", path, role, f"{method} (forged/real browser request)", exp, f"http={res['status']} changed={changed} perm({code})={allowed}", db=f"{before} -> {after}")
    if restore and allowed and changed:
        restore()
    return res


class contextlib_null:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def restore_site_active():
    bfetch(pg, "POST", SURL, {"action": "reactivate"})


def restore_zone_active():
    bfetch(pg, "POST", f"/app/locations/{Z}/status/", {"action": "reactivate"})


@feature(r, "RBAC: view + visible controls per role")
def t_rbac_view():
    for ro in ROLE_LIST:
        p = r.page(ro)
        has = lambda c: perm(ro, c)
        # nav item
        p.goto(BASE + "/app/"); p.wait_for_load_state("networkidle")
        nav = p.locator("nav a[href='/app/sites/'], aside a[href='/app/sites/'], a[href='/app/sites/']").count() > 0
        r.ok(nav == has("site.view"), "RBAC nav 'Sites & Locations' shown iff site.view", "/app/", ro, "read sidebar", f"visible={has('site.view')}", f"visible={nav}")
        # list
        with (contextlib_null() if has("site.view") else r.expect_errors()):
            resp = p.goto(BASE + "/app/sites/"); p.wait_for_load_state("networkidle")
        st = resp.status
        r.ok((st == 200) == has("site.view") and (has("site.view") or st in (403, 404)), "RBAC site list access", "/app/sites/", ro, "open list", "200 iff site.view else 403/404", st)
        if has("site.view"):
            btn = p.locator("main a:has-text('New site')").count() > 0
            r.ok(btn == has("site.create"), "RBAC 'New site' button iff site.create", "/app/sites/", ro, "inspect list", f"{has('site.create')}", btn)
            # detail
            resp = p.goto(BASE + SURL); p.wait_for_load_state("networkidle")
            r.ok(resp.status == 200, "RBAC site detail opens", SURL, ro, "open detail", "200", resp.status)
            edit = p.locator("main a[href$='/edit/']:has-text('Edit')").count() > 0
            r.ok(edit == has("site.update"), "RBAC site 'Edit' iff site.update", SURL, ro, "inspect header", f"{has('site.update')}", edit)
            deact = p.locator("main button:has-text('Deactivate'), main button:has-text('Reactivate')").count() > 0
            # row-level buttons exist on locations tab; header deactivate only counts the first button here
            hdr = p.locator("main form[method=post]:not([action]) button:has-text('Deactivate')").count() > 0 or p.locator("main form[method=post]:not([action]) button:has-text('Reactivate')").count() > 0
            r.ok(hdr == has("site.deactivate"), "RBAC site 'Deactivate' iff site.deactivate", SURL, ro, "inspect header", f"{has('site.deactivate')}", hdr)
            # tabs
            for tab, needs in (("locations", "zone.view"), ("calendars", "calendar.view"), ("contacts", None)):
                resp = p.goto(BASE + SURL + f"?tab={tab}"); p.wait_for_load_state("networkidle")
                body = p.inner_text("main")
                if tab == "locations":
                    add = p.locator("main a:has-text('Add location'), main a:has-text('New location'), main a:has-text('Add root')").count() > 0
                    edz = p.locator(f"main a[href*='/app/locations/{Z}/edit/']").count() > 0
                    dz = p.locator("main form[action*='/status/'] button:has-text('Deactivate')").count() > 0
                    r.ok(add == has("zone.create"), "RBAC 'Add location' iff zone.create", SURL, ro, "locations tab", f"{has('zone.create')}", add)
                    r.ok(edz == has("zone.update"), "RBAC zone 'Edit' iff zone.update", SURL, ro, "locations tab", f"{has('zone.update')}", edz)
                    r.ok(dz == has("zone.deactivate"), "RBAC zone 'Deactivate' iff zone.deactivate", SURL, ro, "locations tab", f"{has('zone.deactivate')}", dz)
                elif tab == "calendars":
                    add = p.locator("main a[href$='/calendars/new/']").count() > 0
                    ed = p.locator(f"main a[href*='/app/calendars/{C}/edit/']").count() > 0
                    de = p.locator("main form[action*='/delete/'] button").count() > 0
                    r.ok(add == has("calendar.create"), "RBAC 'Add calendar' iff calendar.create", SURL, ro, "calendars tab", f"{has('calendar.create')}", add)
                    r.ok(ed == has("calendar.update"), "RBAC calendar 'Edit' iff calendar.update", SURL, ro, "calendars tab", f"{has('calendar.update')}", ed)
                    r.ok(de == has("calendar.delete"), "RBAC calendar 'Delete' iff calendar.delete", SURL, ro, "calendars tab", f"{has('calendar.delete')}", de)
                else:
                    add = p.locator("main a[href$='/contacts/new/'], main form[action$='/contacts/new/']").count() > 0
                    ed = p.locator(f"main a[href*='/app/contacts/{K}/edit/']").count() > 0
                    r.ok(add == has("site.contact.manage") and ed == has("site.contact.manage"), "RBAC contact add/edit iff site.contact.manage", SURL, ro, "contacts tab", f"{has('site.contact.manage')}", f"add={add} edit={ed}")
        # direct GET of write pages
        for label, path, code in (("site create form", "/app/sites/new/", "site.create"), ("site edit form", SURL + "edit/", "site.update"), ("zone create form", SURL + "locations/new/", "zone.create"),
                                  ("zone edit form", f"/app/locations/{Z}/edit/", "zone.update"), ("calendar create form", SURL + "calendars/new/", "calendar.create"),
                                  ("calendar edit form", f"/app/calendars/{C}/edit/", "calendar.update"), ("contact create form", SURL + "contacts/new/", "site.contact.manage"),
                                  ("contact edit form", f"/app/contacts/{K}/edit/", "site.contact.manage")):
            a = has(code)
            with (contextlib_null() if a else r.expect_errors()):
                resp = p.goto(BASE + path); p.wait_for_load_state("networkidle")
            r.ok((resp.status == 200) == a and (a or resp.status in (403, 404)), f"RBAC direct URL: {label}", path, ro, "type URL in browser", "200 iff " + code + " else 403/404", resp.status)


@feature(r, "RBAC: mutations per role")
def t_rbac_mut():
    for ro in ROLE_LIST:
        sitecode = f"X{ro[:5]}{U}".upper()[:30]
        attempt(ro, "site.create", "create site", "POST", "/app/sites/new/", {"code": sitecode, "name": f"RB created by {ro}", "timezone": "Asia/Kolkata"},
                f"select count(*) from sites_site where code='{sitecode}' and organization_id={ALPHA}")
        attempt(ro, "site.update", "edit site", "POST", SURL + "edit/", {"code": f"RB{U}", "name": f"RBAC site {U} by {ro}", "timezone": "Asia/Kolkata"},
                f"select name from sites_site where id='{S}'")
        attempt(ro, "site.deactivate", "deactivate site", "POST", SURL, {"action": "deactivate", "reason": f"rbac {ro}"}, f"select status from sites_site where id='{S}'", restore=restore_site_active)
        attempt(ro, "zone.create", "create zone", "POST", SURL + "locations/new/", {"name": f"Z-{ro}", "zone_type": "ZONE", "parent": "", "code": "", "description": ""},
                f"select count(*) from sites_zone where site_id='{S}' and name='Z-{ro}'")
        attempt(ro, "zone.update", "edit zone", "POST", f"/app/locations/{Z}/edit/", {"name": f"RB zone {ro}", "zone_type": "ZONE", "parent": "", "code": "", "description": ""},
                f"select name from sites_zone where id='{Z}'")
        attempt(ro, "zone.deactivate", "deactivate zone", "POST", f"/app/locations/{Z}/status/", {"action": "deactivate", "reason": f"rbac {ro}"}, f"select status from sites_zone where id='{Z}'", restore=restore_zone_active)
        attempt(ro, "calendar.create", "create calendar", "POST", SURL + "calendars/new/", {"name": f"Cal-{ro}", "working_days": ["1"], "start_time": "08:00", "end_time": "17:00", "notes": ""},
                f"select count(*) from sites_operatingcalendar where site_id='{S}' and name='Cal-{ro}'")
        attempt(ro, "calendar.update", "edit calendar", "POST", f"/app/calendars/{C}/edit/", {"name": f"RB base {ro}", "working_days": ["1", "2", "3"], "start_time": "08:00", "end_time": "17:00", "is_default": "on", "notes": ""},
                f"select name from sites_operatingcalendar where id='{C}'")
        attempt(ro, "calendar.update", "add holiday", "POST", f"/app/calendars/{C}/holidays/", {"action": "add", "date": f"2030-01-{ROLE_LIST.index(ro)+1:02d}", "name": f"H-{ro}"},
                f"select count(*) from sites_calendarholiday where calendar_id='{C}'")
        dcal = sql(f"select id from sites_operatingcalendar where site_id='{S}' and name='Del-{ro}'")
        attempt(ro, "calendar.delete", "delete calendar", "POST", f"/app/calendars/{dcal}/delete/", {}, f"select count(*) from sites_operatingcalendar where id='{dcal}'")
        attempt(ro, "site.contact.manage", "add contact", "POST", SURL + "contacts/new/", {"name": f"K-{ro}", "phone": "1", "role_title": "", "email": "", "notes": ""},
                f"select count(*) from sites_sitecontact where site_id='{S}' and name='K-{ro}'")
        attempt(ro, "site.contact.manage", "edit contact", "POST", f"/app/contacts/{K}/edit/", {"name": f"RB contact {ro}", "phone": "1", "role_title": "", "email": "", "notes": "", "escalation_order": "1"},
                f"select name from sites_sitecontact where id='{K}'")
    # nothing leaked: every role's created records are in Alpha only
    r.ok(sql(f"select count(*) from sites_site where code like 'X%{U}' and organization_id<>{ALPHA}") == "0", "RBAC created sites all belong to the actor's tenant", "-", "all", "query DB", "0 outside Alpha", "0")


@feature(r, "Tenant isolation (both directions)")
def t_tenant():
    bo = r.page("betaowner")
    # Beta fixtures (created by Beta owner through the UI)
    BS = sql("select id from sites_site where code='PUN-1'")
    bfetch(bo, "POST", f"/app/sites/{BS}/locations/new/", {"name": f"Beta zone {U}", "zone_type": "ZONE", "parent": "", "code": "", "description": ""})
    BZ = sql(f"select id from sites_zone where site_id='{BS}' and name='Beta zone {U}'")
    bfetch(bo, "POST", f"/app/sites/{BS}/calendars/new/", {"name": f"Beta cal {U}", "working_days": ["1"], "start_time": "08:00", "end_time": "17:00", "is_default": "on", "notes": ""})
    BC = sql(f"select id from sites_operatingcalendar where site_id='{BS}' and name='Beta cal {U}'")
    bfetch(bo, "POST", f"/app/sites/{BS}/contacts/new/", {"name": f"Beta contact {U}", "phone": "1", "role_title": "", "email": "", "notes": ""})
    BK = sql(f"select id from sites_sitecontact where site_id='{BS}' and name='Beta contact {U}'")
    r.ok(all([BS, BZ, BC, BK]), "Setup: Beta site/zone/calendar/contact exist", "-", "betaowner", "create fixtures", "rows exist", [BS[:8], BZ[:8], BC[:8], BK[:8]])

    def cross(label, who, method, path, data, probe, role_label):
        p = r.page(who)
        before = sql(probe)
        with r.expect_errors():
            res = bfetch(p, method, path, data)
        after = sql(probe)
        r.ok(res["status"] in (403, 404) and before == after, f"Tenant: {label}", path, who, f"{method} other tenant's object", "403/404, DB unchanged", f"http={res['status']}", db=f"{before} -> {after}")

    # Beta owner -> Alpha
    for label, m, path, data, probe in (
        ("Beta cannot open Alpha site detail", "GET", SURL, None, "select 1"),
        ("Beta cannot open Alpha site edit form", "GET", SURL + "edit/", None, "select 1"),
        ("Beta cannot edit Alpha site (POST)", "POST", SURL + "edit/", {"code": f"RB{U}", "name": "HIJACK", "timezone": "Asia/Kolkata"}, f"select name from sites_site where id='{S}'"),
        ("Beta cannot deactivate Alpha site", "POST", SURL, {"action": "deactivate", "reason": "x"}, f"select status from sites_site where id='{S}'"),
        ("Beta cannot create a zone in an Alpha site", "POST", SURL + "locations/new/", {"name": "HIJACKZ", "zone_type": "ZONE", "parent": ""}, f"select count(*) from sites_zone where site_id='{S}'"),
        ("Beta cannot edit an Alpha zone", "POST", f"/app/locations/{Z}/edit/", {"name": "HIJACK", "zone_type": "ZONE", "parent": ""}, f"select name from sites_zone where id='{Z}'"),
        ("Beta cannot open an Alpha zone edit form", "GET", f"/app/locations/{Z}/edit/", None, "select 1"),
        ("Beta cannot deactivate an Alpha zone", "POST", f"/app/locations/{Z}/status/", {"action": "deactivate", "reason": "x"}, f"select status from sites_zone where id='{Z}'"),
        ("Beta cannot create an Alpha calendar", "POST", SURL + "calendars/new/", {"name": "HIJACKC", "working_days": ["1"], "start_time": "08:00", "end_time": "17:00"}, f"select count(*) from sites_operatingcalendar where site_id='{S}'"),
        ("Beta cannot edit an Alpha calendar", "POST", f"/app/calendars/{C}/edit/", {"name": "HIJACK", "working_days": ["1"], "start_time": "08:00", "end_time": "17:00"}, f"select name from sites_operatingcalendar where id='{C}'"),
        ("Beta cannot delete an Alpha calendar", "POST", f"/app/calendars/{C}/delete/", {}, f"select count(*) from sites_operatingcalendar where id='{C}'"),
        ("Beta cannot add an Alpha holiday", "POST", f"/app/calendars/{C}/holidays/", {"action": "add", "date": "2031-05-05", "name": "HIJACK"}, f"select count(*) from sites_calendarholiday where calendar_id='{C}'"),
        ("Beta cannot add an Alpha contact", "POST", SURL + "contacts/new/", {"name": "HIJACK", "phone": "1"}, f"select count(*) from sites_sitecontact where site_id='{S}'"),
        ("Beta cannot edit an Alpha contact", "POST", f"/app/contacts/{K}/edit/", {"name": "HIJACK", "phone": "1", "escalation_order": "1"}, f"select name from sites_sitecontact where id='{K}'"),
    ):
        cross(label, "betaowner", m, path, data, probe, "")
    # Alpha owner -> Beta
    for label, m, path, data, probe in (
        ("Alpha cannot open Beta site detail", "GET", f"/app/sites/{BS}/", None, "select 1"),
        ("Alpha cannot edit Beta site (POST)", "POST", f"/app/sites/{BS}/edit/", {"code": "PUN-1", "name": "HIJACK", "timezone": "Asia/Kolkata"}, f"select name from sites_site where id='{BS}'"),
        ("Alpha cannot deactivate Beta site", "POST", f"/app/sites/{BS}/", {"action": "deactivate", "reason": "x"}, f"select status from sites_site where id='{BS}'"),
        ("Alpha cannot create a zone in a Beta site", "POST", f"/app/sites/{BS}/locations/new/", {"name": "HIJACKZ", "zone_type": "ZONE", "parent": ""}, f"select count(*) from sites_zone where site_id='{BS}'"),
        ("Alpha cannot edit a Beta zone", "POST", f"/app/locations/{BZ}/edit/", {"name": "HIJACK", "zone_type": "ZONE", "parent": ""}, f"select name from sites_zone where id='{BZ}'"),
        ("Alpha cannot open a Beta zone edit form", "GET", f"/app/locations/{BZ}/edit/", None, "select 1"),
        ("Alpha cannot deactivate a Beta zone", "POST", f"/app/locations/{BZ}/status/", {"action": "deactivate", "reason": "x"}, f"select status from sites_zone where id='{BZ}'"),
        ("Alpha cannot edit a Beta calendar", "POST", f"/app/calendars/{BC}/edit/", {"name": "HIJACK", "working_days": ["1"], "start_time": "08:00", "end_time": "17:00", "is_default": "on"}, f"select name from sites_operatingcalendar where id='{BC}'"),
        ("Alpha cannot delete a Beta calendar", "POST", f"/app/calendars/{BC}/delete/", {}, f"select count(*) from sites_operatingcalendar where id='{BC}'"),
        ("Alpha cannot add a Beta holiday", "POST", f"/app/calendars/{BC}/holidays/", {"action": "add", "date": "2031-05-05", "name": "HIJACK"}, f"select count(*) from sites_calendarholiday where calendar_id='{BC}'"),
        ("Alpha cannot edit a Beta contact", "POST", f"/app/contacts/{BK}/edit/", {"name": "HIJACK", "phone": "1", "escalation_order": "1"}, f"select name from sites_sitecontact where id='{BK}'"),
        ("Alpha cannot add a Beta contact", "POST", f"/app/sites/{BS}/contacts/new/", {"name": "HIJACK", "phone": "1"}, f"select count(*) from sites_sitecontact where site_id='{BS}'"),
    ):
        cross(label, "owner", m, path, data, probe, "")
    # Lists / search never leak
    p = r.page(O); p.goto(BASE + "/app/sites/?q=PUN"); p.wait_for_load_state("networkidle")
    r.ok("PUN-1" not in p.inner_text("main"), "Alpha site list/search never shows Beta sites", "/app/sites/?q=PUN", O, "search Beta code", "no result", "not listed")
    p.goto(BASE + "/app/sites/"); r.ok("PUN-1" not in p.inner_text("main"), "Alpha list has no Beta sites", "/app/sites/", O, "open list", "not listed", "ok")
    p2 = r.page("betaowner"); p2.goto(BASE + "/app/sites/?q=HYD"); p2.wait_for_load_state("networkidle")
    r.ok("HYD-1" not in p2.inner_text("main") and f"RB{U}" not in p2.inner_text("main"), "Beta site list/search never shows Alpha sites", "/app/sites/?q=HYD", "betaowner", "search Alpha code", "no result", "ok")
    # Asset form zone dropdown contains only own-tenant zones
    p2.goto(BASE + "/app/assets/new/"); p2.wait_for_load_state("networkidle")
    zopts = p2.locator("select[name=zone] option").all_inner_texts() + p2.locator("select[name=site] option").all_inner_texts()
    r.ok(not any(("HYD" in o or "BLR" in o or "RB" + U in o) for o in zopts), "Beta asset form offers no Alpha sites/zones", "/app/assets/new/", "betaowner", "read dropdowns", "none", zopts[:6])
    # API
    a = bapi(r.page("betaowner"), "GET", f"/api/v1/sites/{S}/")
    r.ok(a["status"] == 404, "API: Beta GET Alpha site -> 404", f"/api/v1/sites/{S}/", "betaowner", "browser fetch", "404", a["status"])
    lst = bapi(r.page("betaowner"), "GET", "/api/v1/sites/")
    codes = [x.get("code") for x in (lst["json"].get("results", lst["json"]) if isinstance(lst["json"], dict) else lst["json"] or [])]
    r.ok(not any(c and (c.startswith("HYD") or c.startswith("RB")) for c in codes), "API: Beta site list has no Alpha sites", "/api/v1/sites/", "betaowner", "browser fetch", "none", codes[:6])
    # header spoof: Alpha session asking for Beta org must not select it
    beta_org = sql("select id from tenancy_organization where slug<>'alpha-field-services' and slug like 'beta%' limit 1")
    js = """async ([path,org])=>{const r=await fetch(path,{headers:{'X-Organization':org},credentials:'same-origin'});let j=null;try{j=await r.json()}catch(e){};return {status:r.status,j:j}}"""
    with r.expect_errors():
        h = r.page(O).evaluate(js, ["/api/v1/sites/", beta_org])
    names = json.dumps(h["j"])[:2000]
    r.ok(h["status"] in (400, 403, 404) or "PUN-1" not in names, "X-Organization header naming a foreign org does not expose its data", "/api/v1/sites/", O, "spoof header", "refused or Alpha-only data", f"http={h['status']}")


@feature(r, "Audit trail visibility")
def t_audit_ui():
    p = r.page(O)
    p.goto(BASE + "/app/audit/?q=" + f"RB{U}"); p.wait_for_load_state("networkidle")
    body = p.inner_text("main")
    inv = inventory(p)
    r.ok("site.created" in body or "Site created" in body or "created" in body.lower(), "Audit trail lists M01 events for the site (owner)", "/app/audit/", O, "search site code", "created/updated entries", body[:120].replace("\n", " "), audit=audits(S))
    r.T("Site detail 'History' tab", "-", O, "look for history on site/zone pages", "history/audit view of the site", "No history tab on site detail (tabs: Overview/Locations/Calendars/Contacts/Assets); site history is only visible in the global Audit Trail page", "PARTIAL")
    pa = r.page("auditor"); pa.goto(BASE + "/app/audit/?q=" + f"RB{U}"); pa.wait_for_load_state("networkidle")
    r.ok("created" in pa.inner_text("main").lower(), "Auditor can read the same M01 audit entries", "/app/audit/", "auditor", "search site code", "entries visible", pa.inner_text("main")[:100].replace("\n", " "))
    pt = r.page("tech")
    with (contextlib_null() if perm("tech", "audit.view") else r.expect_errors()):
        rs = pt.goto(BASE + "/app/audit/")
    r.ok((rs.status == 200) == perm("tech", "audit.view"), "Technician access to the audit trail follows audit.view", "/app/audit/", "tech", "open", f"200 iff audit.view={perm('tech','audit.view')}", rs.status)
    # audit rows really exist per action for the RBAC site
    acts = sql(f"select string_agg(distinct action, ',') from audit_auditlog where target_id in ('{S}','{Z}','{C}','{K}')")
    r.ok("site.updated" in (acts or "") and "zone.updated" in (acts or ""), "Audit rows exist for edits made through the browser", "-", O, "query audit table", "site.updated, zone.updated …", acts, audit=acts)


@feature(r, "Broken links")
def t_links():
    p = r.page(O)
    pages = ["/app/sites/", "/app/sites/new/", SURL, SURL + "?tab=locations", SURL + "?tab=calendars", SURL + "?tab=contacts", SURL + "?tab=assets", SURL + "edit/",
             SURL + "locations/new/", SURL + "calendars/new/", SURL + "contacts/new/", f"/app/locations/{Z}/edit/", f"/app/calendars/{C}/edit/", f"/app/contacts/{K}/edit/", f"/app/sites/{HYD}/"]
    seen = {}
    for u in pages:
        p.goto(BASE + u); p.wait_for_load_state("networkidle")
        for l in p.evaluate("()=>[...document.querySelectorAll('a[href]')].map(a=>[a.getAttribute('href'),a.innerText.trim().slice(0,30)])"):
            h = l[0]
            if h.startswith("#") or h.startswith("mailto:") or h.startswith("tel:") or h.startswith("javascript") or "logout" in h: continue
            seen.setdefault(h, (u, l[1]))
    bad = []
    for h, (src, t) in sorted(seen.items()):
        if h.startswith("http") and not h.startswith(BASE): continue
        res = p.evaluate("async h=>{const r=await fetch(h,{credentials:'same-origin'});return r.status}", h)
        if res >= 400: bad.append((h, res, src, t))
    r.ok(not bad, f"All {len(seen)} distinct links on M01 pages resolve (no 404/500)", "M01 pages", O, "GET every link", "none broken", bad[:5] or "all ok")


@feature(r, "Responsive + keyboard + modal + mobile menu")
def t_responsive():
    paths = [("Site list", "/app/sites/"), ("New site", "/app/sites/new/"), ("Site detail overview", SURL), ("Locations tab", SURL + "?tab=locations"), ("Calendars tab", SURL + "?tab=calendars"),
             ("Contacts tab", SURL + "?tab=contacts"), ("Assets tab", SURL + "?tab=assets"), ("Site edit", SURL + "edit/"), ("New location", SURL + "locations/new/"), ("Edit location", f"/app/locations/{Z}/edit/"),
             ("New calendar", SURL + "calendars/new/"), ("Edit calendar", f"/app/calendars/{C}/edit/"), ("New contact", SURL + "contacts/new/"), ("Edit contact", f"/app/contacts/{K}/edit/")]
    for vp in ("desktop", "laptop", "tablet", "mobile"):
        p = r.page(O, vp)
        for name, path in paths:
            p.goto(BASE + path); p.wait_for_load_state("networkidle")
            ov = overflow(p)
            fine = ov["sw"] <= ov["iw"] + 1 and not ov["wide"] and not ov["clipped"]
            ev = ""
            if not fine: ev = shot(p, f"M01_{vp}_{name.replace(' ', '_')}")
            r.ok(fine, f"Responsive {vp}: {name} (no horizontal overflow / clipped controls)", path, O, f"open at {VIEWPORTS[vp][0]}x{VIEWPORTS[vp][1]}", "no overflow", f"sw={ov['sw']} iw={ov['iw']} wide={ov['wide'][:2]} clipped={ov['clipped'][:2]}", ev=ev)
        shot(p, f"M01_{vp}_detail")
    # mobile menu
    p = r.page(O, "mobile"); p.goto(BASE + "/app/sites/"); p.wait_for_load_state("networkidle")
    tog = p.locator("button[aria-label*='enu' i], button.navbar-toggler, #fx-menu-toggle, button[data-sidebar-toggle], [data-bs-toggle='offcanvas'], button:has(svg.bi-list), .fx-menu-btn").first
    n = p.locator("button[aria-label*='enu' i], button.navbar-toggler, #fx-menu-toggle, button[data-sidebar-toggle], [data-bs-toggle='offcanvas'], .fx-menu-btn").count()
    sidebar_vis_before = p.locator("a[href='/app/sites/']").first.is_visible()
    if n:
        tog.click(); p.wait_for_timeout(600)
        link_vis = p.locator("a[href='/app/sites/']").first.is_visible()
        r.ok(link_vis, "Mobile menu opens and shows navigation", "/app/sites/", O, "tap menu button at 390x844", "nav visible", f"visible={link_vis} (before={sidebar_vis_before})", ev=shot(p, "M01_mobile_menu"))
        p.locator("a[href='/app/sites/']").first.click(); p.wait_for_load_state("networkidle")
        r.ok("/app/sites" in p.url, "Mobile menu link navigates", p.url, O, "tap Sites", "navigates", p.url)
    else:
        r.ok(sidebar_vis_before, "Mobile navigation reachable at 390px", "/app/sites/", O, "look for menu button / visible nav", "reachable", f"no toggle found; nav visible={sidebar_vis_before}", ev=shot(p, "M01_mobile_nomenu"))
    # keyboard: focus visible on first controls of the site form
    p = r.page(O, "laptop"); p.goto(BASE + "/app/sites/new/"); p.wait_for_load_state("networkidle")
    skip = p.locator("a[href='#main'], a.skip-link, a:has-text('Skip to')").count()
    r.ok(skip > 0, "Keyboard: 'skip to content' link present (sidebar has ~35 tab stops before the page content)", "/app/sites/new/", O, "inspect first focusable elements", "skip link available", f"skip links={skip}", partial=True)
    p.locator("main form [name=code]").evaluate("e=>{const p=document.querySelector('main h1')||document.querySelector('main');p.setAttribute('tabindex','-1');p.focus()}")
    seq = []
    for _ in range(14):
        p.keyboard.press("Tab")
        seq.append(p.evaluate("""()=>{const e=document.activeElement;if(!e||e===document.body)return null;const s=getComputedStyle(e);
          return {tag:e.tagName,name:e.name||e.textContent.trim().slice(0,20),vis:(s.outlineStyle!=='none'&&parseFloat(s.outlineWidth)>0)||s.boxShadow!=='none'||s.borderColor!==''}}"""))
    seq = [x for x in seq if x]
    names = [x["name"] for x in seq]
    r.ok("code" in names and "name" in names, "Keyboard: Tab reaches the site form fields in order", "/app/sites/new/", O, "press Tab x14", "code/name reached", names)
    novis = [x["name"] for x in seq if not x["vis"]]
    r.ok(not novis, "Keyboard: focused controls show a visible focus indicator", "/app/sites/new/", O, "press Tab", "outline or shadow on focus", novis or "all visible")
    # modal fit on mobile
    p = r.page(O, "mobile"); p.goto(BASE + f"/app/sites/{S}/?tab=locations"); p.wait_for_load_state("networkidle")
    btn = p.locator("main form[action*='/status/'] button:has-text('Deactivate')").first
    if btn.count():
        btn.click(); p.wait_for_timeout(500)
        box = p.locator("#fx-confirm").bounding_box()
        fit = box and box["x"] >= -1 and box["x"] + box["width"] <= 391 and box["y"] >= -1 and box["y"] + box["height"] <= 845
        r.ok(bool(fit), "Confirm modal fits the 390x844 viewport", "-", O, "open confirm on mobile", "within viewport", box, ev=shot(p, "M01_mobile_modal"))
        p.keyboard.press("Escape"); p.wait_for_timeout(300)
        closed = not p.locator("#fx-confirm").is_visible()
        r.ok(closed, "Confirm modal closes with Escape", "-", O, "press Esc", "closed", closed)
    # validation visible on mobile
    p.goto(BASE + "/app/sites/new/"); p.wait_for_load_state("networkidle")
    with r.expect_errors():
        p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
    err = p.locator("main .text-danger").first
    inview = err.count() and err.evaluate("e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0}")
    r.ok(bool(inview), "Mobile: inline validation errors are rendered and visible", "/app/sites/new/", O, "submit empty form at 390px", "errors visible", bool(inview), ev=shot(p, "M01_mobile_validation"))
    # success message visible on mobile
    p.goto(BASE + SURL + "edit/"); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    al = p.locator(".alert-success, .toast, [role=alert]").first
    r.ok(al.count() > 0 and al.is_visible(), "Mobile: success message visible after save", p.url, O, "save site at 390px", "message shown", al.count() > 0, ev=shot(p, "M01_mobile_success"))


for f in (t_rbac_view, t_rbac_mut, t_tenant, t_audit_ui, t_links, t_responsive):
    f()

fails = [x for x in r.rows if x["status"] == "FAIL"]
unv = [x for x in r.rows if x["status"] == "UNVERIFIED"]
print("ROWS", len(r.rows), "FAIL", len(fails), "UNVF", len(unv))
for x in fails + unv: print("  ", x["status"], x["feature"], "|", x["role"], "|", str(x["actual"])[:160])
print("ISSUES", len(r.issues))
for i in r.issues[:20]: print("  ", i["kind"], i["feature"], i["role"], i["text"][:120], i.get("url", "")[-60:])
r.stop()
