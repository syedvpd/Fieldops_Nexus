import sys, time; sys.path.insert(0, '.')
from bx import *
HYD = sid("HYD-1"); U = str(int(time.time()))[-5:]
ids = json.load(open('batch1/ids.json'))
PAGES = {
 "M01": [("/app/sites/", None), ("/app/sites/new/", None), (f"/app/sites/{ids['site']}/", None), (f"/app/sites/{ids['site']}/edit/", None), (f"/app/sites/{ids['site']}/locations/new/", None), (f"/app/locations/{ids['zone']}/edit/", None), (f"/app/calendars/{ids['cal']}/edit/", None), (f"/app/contacts/{ids['contact']}/edit/", None)],
 "M02": [("/app/assets/", None), ("/app/assets/new/", None), ("/app/assets/categories/", None), (f"/app/assets/{ids['asset']}/", None), (f"/app/assets/{ids['asset']}/?tab=documents", None), (f"/app/assets/{ids['asset']}/edit/", None)],
 "M03": [(f"/app/assets/{ids['asset']}/?tab=hierarchy", None), (f"/app/assets/{ids['asset']}/tree/", None), (f"/app/assets/new/?parent={ids['asset']}", None)],
 "M04": [("/app/maintenance/plans/", None), ("/app/maintenance/plans/new/", None), (f"/app/maintenance/plans/{ids['plan']}/", None), (f"/app/maintenance/plans/{ids['plan']}/edit/", None), (f"/app/maintenance/schedules/{ids['sch']}/", None), ("/app/maintenance/due/", None), ("/app/maintenance/history/", None)],
}
POSTS = {
 "M01": [("/app/sites/new/", {"code": f"ANON{U}", "name": "anon", "timezone": "Asia/Kolkata"}, f"select count(*) from sites_site where code='ANON{U}'"), (f"/app/sites/{ids['site']}/", {"action": "deactivate", "reason": "anon"}, f"select status from sites_site where id='{ids['site']}'"), (f"/app/locations/{ids['zone']}/status/", {"action": "deactivate", "reason": "anon"}, f"select status from sites_zone where id='{ids['zone']}'"), (f"/app/calendars/{ids['cal']}/delete/", {}, f"select count(*) from sites_operatingcalendar where id='{ids['cal']}'")],
 "M02": [(f"/app/assets/{ids['asset']}/transition/start_maintenance/", {"reason": "anon test"}, f"select status from assets_asset where id='{ids['asset']}'"), (f"/app/assets/{ids['asset']}/meters/new/", {"name": "anon", "unit": "h"}, f"select count(*) from assets_assetmeter where asset_id='{ids['asset']}'"), ("/app/assets/categories/", {"name": f"ANON {U}", "description": ""}, f"select count(*) from assets_assetcategory where name='ANON {U}'")],
 "M03": [(f"/app/assets/{ids['asset']}/components/add/", {"child": ids['eng'], "relationship_type": "COMPONENT", "quantity": "1"}, "select count(*) from assets_assetcomponent"), (f"/app/components/{ids['link']}/remove/", {}, "select count(*) from assets_assetcomponent")],
 "M04": [("/app/maintenance/plans/new/", {"asset": ids['asset'], "name": f"ANON {U}"}, f"select count(*) from maintenance_maintenanceplan where name='ANON {U}'"), (f"/app/maintenance/schedules/{ids['sch']}/generate/", {}, "select count(*) from maintenance_maintenancecycle"), (f"/app/maintenance/plans/{ids['plan']}/active/", {"active": "0"}, f"select is_active from maintenance_maintenanceplan where id='{ids['plan']}'")],
}
for mod in ("M01", "M02", "M03", "M04"):
    r = Run(mod).start(); O = "anonymous"
    anon = r.browser.new_context(); r._wire(anon, "anonymous"); p = anon.new_page(); p.goto(BASE + "/accounts/login/")
    for path, _ in PAGES[mod]:
        with r.expect_errors(): resp = p.goto(BASE + path); p.wait_for_load_state("networkidle")
        r.ok("/accounts/login" in p.url and "next=" in p.url, f"Anonymous GET {norm(path)} redirects to login with ?next=", path, O, "open URL while logged out", "redirect to /accounts/login/?next=", p.url[-60:])
    for path, data, probe in POSTS[mod]:
        before = sql(probe)
        with r.expect_errors(): res = bfetch(p, "POST", path, data)
        r.ok(res["status"] in (200, 302, 403) and sql(probe) == before and ("/accounts/login" in res["url"] or res["status"] == 403), f"Anonymous POST {norm(path)} is refused (login redirect / 403) and changes nothing", path, O, "forged POST without a session", "refused, DB unchanged", f"http={res['status']} -> {res['url'][-40:]}", db=f"{before} -> {sql(probe)}")
    # expired session: logged-in context whose session cookie is removed mid-way
    ctx = r.browser.new_context(); r._wire(ctx, "owner"); pp = ctx.new_page(); pp.goto(BASE + "/accounts/login/"); pp.fill("input[name=username]", ROLES["owner"]); pp.fill("input[name=password]", CREDS[ROLES["owner"]]); pp.click("form button.btn-primary"); pp.wait_for_load_state("networkidle")
    path = PAGES[mod][0][0]; pp.goto(BASE + path); ctx.clear_cookies(["sessionid"] if False else None) if False else None
    ctx.clear_cookies(); 
    with r.expect_errors(): pp.reload(); pp.wait_for_load_state("networkidle")
    r.ok("/accounts/login" in pp.url, f"Session expiry on {norm(path)}: reload returns to the login page", path, "owner", "delete the session cookie then reload", "login page", pp.url[-50:])
    if mod == "M02":
        # a document download needs an authenticated asset viewer of the same tenant
        att = sql(f"select a.attachment_id from assets_assetdocument a where a.is_active and a.organization_id={ALPHA} limit 1")
        if att:
            for role in ("auditor", "client", "tech"):
                pr = r.page(role); has = perm(role, "asset.view")
                with (r.expect_errors() if not has else __import__("contextlib").nullcontext()): rs = pr.context.request.get(BASE + f"/app/files/{att}/download/")
                r.ok((rs.status == 200) == has and (has or rs.status in (403, 404)), f"Document download by {role}: 200 iff asset.view ({has})", f"/app/files/{{id}}/download/", role, "GET download URL", f"200 iff asset.view={has}", rs.status)
    for x in r.rows: 
        if x["status"] != "PASS": print(x["status"], x["feature"], x["actual"])
    print(mod, len(r.rows), "rows", len(r.issues), "issues")
    r.stop()
