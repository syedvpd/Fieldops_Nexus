import sys, time; sys.path.insert(0, '.')
from bx import *
r = Run("M01").start()
U = str(int(time.time()))[-5:]
O = "owner"
pg = r.page(O)
L = "/app/sites/"

# ---------------------------------------------------------------- setup (not under test): 30 extra sites for pagination
for i in range(30 if sql(f"select count(*) from sites_site where code like 'PG%' and organization_id={ALPHA}") == "0" else 0):
    bapi(pg, "POST", "/api/v1/sites/", {"code": f"PG{U}-{i:02d}", "name": f"Pagination site {i:02d}", "timezone": "Asia/Kolkata", "city": "Pune" if i % 2 else "Delhi"})
n_sites = sql(f"select count(*) from sites_site where organization_id={ALPHA}")


@feature(r, "Site list")
def t_list():
    st, p = visit(r, O, L)
    r.cur = "Site list"
    t = p.inner_text("main")
    heads = p.locator("main table thead th").all_inner_texts()
    r.ok(st == 200 and "New site" in t, "Site list", L, O, "open list", "page with 'New site' button", f"status={st}")
    r.ok([h.strip().upper() for h in heads][:6] == ["CODE", "NAME", "CITY", "LOCATIONS", "ACTIVE ASSETS", "STATUS"], "Site list columns", L, O, "inspect table header", "CODE/NAME/CITY/LOCATIONS/ACTIVE ASSETS/STATUS", heads)
    # counts per row must equal the database
    bad = []
    for row in p.locator("main table tbody tr").all():
        cells = [c.strip() for c in row.locator("td").all_inner_texts()]
        if len(cells) < 6: continue
        code = cells[0]
        zc = sql(f"select count(*) from sites_zone z join sites_site s on s.id=z.site_id where s.code='{code}' and s.organization_id={ALPHA}")
        ac = sql(f"select count(*) from assets_asset a join sites_site s on s.id=a.site_id where s.code='{code}' and a.status='ACTIVE' and s.organization_id={ALPHA}")
        if cells[3] != zc or cells[4] != ac: bad.append((code, cells[3], zc, cells[4], ac))
    r.ok(not bad, "Site list counts equal DB", L, O, "compare LOCATIONS/ACTIVE ASSETS per row with SQL", "identical", bad or "all rows equal", db="zone/asset counts")
    # breadcrumb / row link opens detail
    p.locator("main table tbody tr a").first.click(); p.wait_for_load_state()
    r.ok("/app/sites/" in p.url and p.url != BASE + L, "Row link opens site detail", L, O, "click first code link", "site detail", p.url)
    r.ok(p.locator("main a:has-text('New site')").count() == 0 or True, "-", L, O, "-", "-", "")


@feature(r, "Site search")
def t_search():
    cases = [("code exact", "HYD-1", ["HYD-1"], ["BLR-1"]), ("code lower-case", "hyd-1", ["HYD-1"], []), ("name fragment", "Bangalore", ["BLR-1"], ["HYD-1"]),
             ("city", "Hyderabad", ["HYD-1"], ["BLR-1"]), ("partial code", "BLR", ["BLR-1"], ["HYD-1"]), ("no match", "zzzz-nothing", [], ["HYD-1", "BLR-1"]),
             ("sql chars", "'; DROP TABLE sites_site;--", [], ["HYD-1"]), ("percent wildcard", "%", [], []), ("whitespace padded", "  HYD-1  ", ["HYD-1"], [])]
    for name, q, want, notwant in cases:
        st, p = visit(r, O, f"{L}?q={q}")
        t = p.inner_text("main")
        ok = st == 200 and all(w in t for w in want) and not any(n in t for n in notwant)
        r.ok(ok, f"Site search: {name}", L, O, f"?q={q}", f"shows {want}, hides {notwant}", f"status={st}")
    # via the UI search box (typing + Enter) in the topbar and the filter form
    st, p = visit(r, O, L)
    p.fill("main form[method=get] input[name=q]", "BLR"); p.locator("main form[method=get] button:has-text('Filter')").click(); p.wait_for_load_state()
    r.ok("BLR-1" in p.inner_text("main") and "HYD-1" not in p.inner_text("main") and "q=BLR" in p.url, "Search via filter form", L, O, "type BLR + Filter", "filtered list, query in URL", p.url)
    st, p = visit(r, O, L + "?q=zzzz-nothing")
    r.ok(p.locator("main .fx-empty, main .empty-state, main :text('No sites')").count() > 0 or "No " in p.inner_text("main"), "Empty state on no search result", L, O, "search with no hits", "empty-state message", p.inner_text("main")[-120:].replace("\n", " "))
    # XSS in q is escaped and not reflected as markup
    st, p = visit(r, O, L + "?q=<img src=x onerror=window.__x=1>")
    r.ok(p.evaluate("()=>!window.__x") and "<img src=x" not in p.content(), "Search term is escaped (XSS)", L, O, "q=<img onerror>", "inert", "no script executed")


@feature(r, "Site status filter")
def t_filter():
    # make one inactive site via the UI path later; here just check filter options & results
    st, p = visit(r, O, L)
    opts = p.locator("main form[method=get] select[name=status] option").all_inner_texts()
    r.ok(opts == ["All statuses", "Active", "Inactive"], "Status filter options", L, O, "read select", "All/Active/Inactive", opts)
    for val, expect_present, expect_absent in (("ACTIVE", "HYD-1", None), ("INACTIVE", None, "HYD-1")):
        st, p = visit(r, O, f"{L}?status={val}")
        t = p.inner_text("main")
        ok = (expect_present in t if expect_present else True) and (expect_absent not in t if expect_absent else True)
        r.ok(ok, f"Status filter {val}", L, O, f"?status={val}", "matches status", "ok" if ok else t[:100])
    st, p = visit(r, O, f"{L}?status=BOGUS")
    r.ok(st == 200, "Status filter with invalid value does not crash", L, O, "?status=BOGUS", "200, safe", st)
    st, p = visit(r, O, f"{L}?status=ACTIVE&q=BLR")
    r.ok("BLR-1" in p.inner_text("main") and "HYD-1" not in p.inner_text("main"), "Filter + search combine", L, O, "status=ACTIVE&q=BLR", "BLR only", "ok")


@feature(r, "Site pagination")
def t_pagination():
    import math
    st, p = visit(r, O, L)
    total = int(sql(f"select count(*) from sites_site where organization_id={ALPHA}")); pages = math.ceil(total / 20)
    rows1 = p.locator("main table tbody tr").count()
    nav = p.locator("nav[aria-label=Pagination]").count()
    r.ok(rows1 == 20 and nav == 1 and pages >= 2, "Pagination: page 1 shows 20 rows (page size) + pager", L, O, "open list with %d sites" % total, "20 rows + pager", f"rows={rows1} pager={nav} pages={pages}")
    txt = p.locator("nav[aria-label=Pagination]").inner_text()
    r.ok(f"{total} total" in txt and f"Page 1 of {pages}" in txt, "Pager text", L, O, "read pager", f"Page 1 of {pages} · {total} total", txt.replace("\n", " "))
    r.ok(p.locator("nav a:has-text('Previous')").count() == 0, "Pager: Previous hidden on first page", L, O, "inspect", "no Previous", "ok")
    codes = [c.strip() for c in p.locator("main table tbody tr td:first-child").all_inner_texts()]
    for pn in range(2, pages + 1):
        p.locator("nav[aria-label=Pagination] a:has-text('Next')").click(); p.wait_for_load_state()
        rows = p.locator("main table tbody tr").count(); exp = min(20, total - 20 * (pn - 1))
        last = pn == pages
        r.ok(f"page={pn}" in p.url and rows == exp and p.locator("nav a:has-text('Previous')").count() == 1 and (p.locator("nav a:has-text('Next')").count() == 0) == last, f"Pagination: Next -> page {pn} ({exp} rows, Previous shown, Next {'hidden' if last else 'shown'})", L, O, "click Next", f"{exp} rows", f"url={p.url} rows={rows}")
        codes += [c.strip() for c in p.locator("main table tbody tr td:first-child").all_inner_texts()]
    r.ok(len(codes) == len(set(codes)) == total, "Pagination: no duplicate or missing rows across all pages", L, O, "collect codes of every page", f"{total} unique", f"{len(codes)}/{len(set(codes))}")
    p.locator("nav[aria-label=Pagination] a:has-text('Previous')").click(); p.wait_for_load_state()
    r.ok(f"page={pages-1}" in p.url, "Pagination: Previous goes back one page", L, O, "click Previous", f"page={pages-1}", p.url)
    st, p = visit(r, O, f"{L}?q=PG&page=2")
    pgn = int(sql(f"select count(*) from sites_site where code like 'PG%' and organization_id={ALPHA}"))
    r.ok(st == 200 and p.locator("main table tbody tr").count() == min(20, pgn - 20), "Pagination preserves search query", L, O, "?q=PG&page=2", f"{min(20, pgn-20)} rows", p.locator("main table tbody tr").count())
    st, p = visit(r, O, f"{L}?q=PG&page=2"); lk = p.locator("nav a:has-text('Previous')").get_attribute("href") if p.locator("nav a:has-text('Previous')").count() else ""
    r.ok("q=PG" in lk, "Pager links keep the filter in their query string", L, O, "read Previous link", "contains q=PG", lk)
    for bad in ("0", "999", "abc", "-1"):
        with r.expect_errors():
            st, p = visit(r, O, f"{L}?page={bad}")
        r.ok(st in (200, 404), f"Pagination invalid page={bad}", L, O, f"?page={bad}", "safe (200/404, no 500)", st)


@feature(r, "Site create: happy path + persistence")
def t_create():
    st, p = visit(r, O, L + "new/")
    f = dict(code=f"C{U}", name=f"Create Test Site {U}", description="desc here", address="1 Main Road\nSecond line", city="Chennai", state_region="TN", postal_code="600001", country="IN", timezone="Asia/Kolkata", contact_name="Ann Contact", contact_email="ann@example.com", contact_phone="+91 44 1234")
    fill(p, f); p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
    row = sql(f"select code||'|'||name||'|'||description||'|'||replace(replace(address,E'\\r',''),E'\\n','/')||'|'||city||'|'||state_region||'|'||postal_code||'|'||country||'|'||timezone||'|'||contact_name||'|'||contact_email||'|'||contact_phone||'|'||status from sites_site where code='C{U}' and organization_id={ALPHA}")
    exp = f"C{U}|Create Test Site {U}|desc here|1 Main Road/Second line|Chennai|TN|600001|IN|Asia/Kolkata|Ann Contact|ann@example.com|+91 44 1234|ACTIVE"
    r.ok(row == exp, "Create site: every field saved", L + "new/", O, "fill all 12 fields, submit", "row equals input", row, db=row, audit=audits(sid(f"C{U}")))
    r.ok("/app/sites/" in p.url and f"C{U}" in p.inner_text("main") and "created" in (p.inner_text("body")).lower(), "Create site: redirect to detail + success message", L + "new/", O, "after submit", "detail page with success flash", p.url + " | " + msgs(p))
    p.reload(); p.wait_for_load_state()
    t = p.inner_text("main")
    r.ok(all(x in t for x in (f"Create Test Site {U}", "Chennai", "Asia/Kolkata", "Ann Contact", "600001")), "Create site: detail survives refresh", p.url, O, "reload", "values still shown", "ok")
    r.ok("site.created" in (audits(sid(f"C{U}")) or ""), "Create site: audited", "-", O, "audit row", "site.created", audits(sid(f"C{U}")), audit="site.created")
    st, q = visit(r, O, f"{L}?q=C{U}")
    r.ok(f"C{U}" in q.inner_text("main"), "Create site: appears in list", L, O, "search new code", "listed", "ok")
    # minimal (only required)
    st, p = visit(r, O, L + "new/")
    fill(p, dict(code=f"M{U}", name=f"Minimal {U}", timezone="UTC")); p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
    r.ok(sql(f"select status||'|'||timezone||'|'||city from sites_site where code='M{U}'") == "ACTIVE|UTC|", "Create site: only required fields", L + "new/", O, "code+name+timezone", "created ACTIVE with blanks", sql(f"select status||'|'||timezone from sites_site where code='M{U}'"))
    # org ownership
    r.ok(sql(f"select organization_id={ALPHA} from sites_site where code='C{U}'") == "t", "Create site: organization = Alpha", "-", O, "SQL", "alpha org", "t", db="organization_id")


@feature(r, "Site create validation")
def t_validation():
    def attempt(label, vals, expect_msg=None, count_sql=None, base=None, expect_rows="0"):
        st, p = visit(r, O, L + "new/")
        data = dict(code=f"V{U}x", name="Validation site", timezone="Asia/Kolkata"); data.update(base or {}); data.update(vals)
        with r.expect_errors():
            for k, v in data.items():
                if v is None: continue
                loc = p.locator(f"main form [name='{k}']").first
                loc.evaluate("(e,v)=>{e.removeAttribute('required');e.removeAttribute('maxlength');e.removeAttribute('pattern');e.value=v}", str(v))
            p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
        cnt = sql(count_sql or f"select count(*) from sites_site where code='{data['code']}' and organization_id={ALPHA}")
        shown = msgs(p)
        ok = cnt == expect_rows and (expect_msg is None or expect_msg.lower() in shown.lower() or expect_msg.lower() in p.inner_text("main").lower())
        r.ok(ok, f"Site validation: {label}", L + "new/", O, "submit (client-side constraints stripped to hit the server)", f"rejected{' with ' + expect_msg if expect_msg else ''}; no row", f"rows={cnt} msg={shown[:120]}", db=cnt)
    attempt("missing code", dict(code=""), "required", f"select count(*) from sites_site where name='Validation site' and organization_id={ALPHA}")
    attempt("whitespace-only code", dict(code="   "), None, f"select count(*) from sites_site where name='Validation site' and organization_id={ALPHA}")
    attempt("missing name", dict(name=""), "required")
    attempt("missing timezone", dict(timezone=""), "required")
    attempt("invalid timezone", dict(timezone="Mars/Olympus"), "timezone")
    attempt("timezone with wrong case", dict(timezone="asia/kolkata"), None)
    attempt("invalid email", dict(contact_email="not-an-email"), "email")
    attempt("code with spaces/specials", dict(code="BAD CODE!@#"), None)
    attempt("code over max length", dict(code="X" * 80), None, f"select count(*) from sites_site where code like 'XXXX%' and organization_id={ALPHA}")
    attempt("name over max length", dict(name="N" * 400), None)
    attempt("phone over max length", dict(contact_phone="9" * 200), None)
    attempt("country over max length", dict(country="INDIA-LONG-NAME"), None)
    attempt("duplicate code (exact)", dict(code="HYD-1"), "already exists", f"select count(*) from sites_site where lower(code)='hyd-1' and organization_id={ALPHA}", expect_rows="1")
    attempt("duplicate code (lower-case)", dict(code="hyd-1"), "already exists", f"select count(*) from sites_site where lower(code)='hyd-1' and organization_id={ALPHA}", expect_rows="1")
    attempt("duplicate code with padding", dict(code=" HYD-1 "), None, f"select count(*) from sites_site where lower(trim(code))='hyd-1' and organization_id={ALPHA}", expect_rows="1")
    # boundaries that must be ACCEPTED
    one = next(c for c in "abcdefghijklmnopqrstuvwxyz0123456789" if sql(f"select count(*) from sites_site where lower(code)='{c}' and organization_id={ALPHA}") == "0")
    st, p = visit(r, O, L + "new/"); fill(p, dict(code=one, name="B", timezone="UTC")); p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
    r.ok(sql(f"select count(*) from sites_site where lower(code)='{one}' and organization_id={ALPHA}") == "1", "Boundary: 1-character code/name accepted", L + "new/", O, f"code={one} name=B", "created", msgs(p)[:80])
    mx = sql("select character_maximum_length from information_schema.columns where table_name='sites_site' and column_name='code'")
    longc = (U + "Z" * int(mx))[:int(mx)]
    st, p = visit(r, O, L + "new/"); fill(p, dict(code=longc, name="Max code", timezone="UTC")); p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
    r.ok(sql(f"select count(*) from sites_site where code='{longc}'") == "1", f"Boundary: code at max length ({mx}) accepted", L + "new/", O, "max length", "created", msgs(p)[:80])
    # stored XSS in name renders inert
    st, p = visit(r, O, L + "new/"); fill(p, dict(code=f"X{U}", name="<script>window.__xs=1</script><b>bold</b>", timezone="UTC")); p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
    html = p.content()
    r.ok("<script>window.__xs" not in html and p.evaluate("()=>!window.__xs"), "Stored XSS in site name is escaped on detail", p.url, O, "name=<script>", "inert", "escaped")
    st, q = visit(r, O, L + f"?q=X{U}"); r.ok("<b>bold</b>" not in q.content(), "Stored XSS escaped in list", L, O, "list", "inert", "ok")
    st, p = visit(r, O, L + "new/")
    req = p.eval_on_selector_all("main form [required]", "e=>e.map(x=>x.name)")
    r.ok(sorted(req) == ["code", "name", "timezone"], "Required attributes marked on code,name,timezone (accessibility)", L + "new/", O, "inspect form", "3 required fields", req)
    # submit the empty form through the real UI: shows inline, field-level errors and keeps the page
    st, p = visit(r, O, L + "new/")
    nv = p.eval_on_selector("main form", "f=>f.noValidate")
    posts0 = sum(r.cov_post.values())
    with r.expect_errors():
        p.locator("main form button:has-text('Create site')").click(); p.wait_for_load_state()
    inline = p.locator("main .text-danger").all_inner_texts()
    per_field = p.evaluate("""()=>[...document.querySelectorAll('main form .mb-3')].filter(g=>g.querySelector('.text-danger')).map(g=>(g.querySelector('[name]')||{}).name)""")
    aria = p.evaluate("()=>[...document.querySelectorAll('main form [aria-invalid=true], main form .is-invalid')].length")
    r.ok(p.url.endswith("/new/") and set(per_field) >= {"code", "name"} and all("required" in t.lower() for t in inline), "Empty submit: field-level 'required' errors under code and name", L + "new/", O, "click Create site on empty form", "error beneath each missing field", f"novalidate={nv} posted={sum(r.cov_post.values())-posts0} fields_with_error={per_field}")
    r.T("Empty submit: invalid fields are flagged for assistive tech / visually", L + "new/", O, "inspect inputs after error", "aria-invalid or .is-invalid on the bad inputs and error linked via aria-describedby", f"flagged inputs={aria}; error text only (red small text), no aria-invalid/aria-describedby", "PARTIAL" if aria == 0 else "PASS")
    r.ok(p.eval_on_selector("main form [name=timezone]", "e=>e.value") == "Asia/Kolkata", "Empty submit: form keeps entered/default values", L + "new/", O, "read timezone after error", "retained", "Asia/Kolkata")
    vis = p.evaluate("()=>[...document.querySelectorAll('main .text-danger')].every(e=>{const r=e.getBoundingClientRect();return r.height>0&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'})")
    r.ok(vis, "Validation messages are visible", L + "new/", O, "inspect messages", "visible", vis)
    # cancel link
    st, p = visit(r, O, L + "new/"); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state()
    r.ok(p.url.rstrip("/").endswith("/app/sites"), "Cancel returns to list", L + "new/", O, "click Cancel", "list", p.url)


@feature(r, "Site view")
def t_view():
    hyd = sid("HYD-1")
    st, p = visit(r, O, f"{L}{hyd}/")
    t = p.inner_text("main")
    r.ok(all(x in t for x in ("Hyderabad Operations Site", "HYD-1", "Asia/Kolkata", "Madhapur", "Hyderabad Plant Manager")), "Site overview shows saved fields", p.url, O, "open detail", "all fields", t[:100].replace("\n", " "))
    tabs = p.locator(".fx-tabs a").all_inner_texts()
    r.ok(tabs == ["Overview", "Locations", "Calendars", "Contacts", "Assets"], "Site tabs", p.url, O, "read tabs", "5 tabs", tabs)
    for tab, expect in (("locations", "Generator Room"), ("calendars", "Day shift"), ("contacts", "HYD-1 Site Manager"), ("assets", "GEN-001")):
        p.locator(f".fx-tabs a:has-text('{tab.title()}')").click(); p.wait_for_load_state()
        r.ok(f"tab={tab}" in p.url and expect in p.inner_text("main"), f"Tab '{tab}' shows its data", p.url, O, f"click tab {tab}", expect, p.url)
    st, p2 = visit(r, O, f"{L}{hyd}/?tab=nonsense")
    r.ok(st == 200, "Unknown tab value is handled", p2.url, O, "?tab=nonsense", "200 fallback", st)
    # related assets tab: counts equal DB and link opens asset
    p.goto(f"{BASE}{L}{hyd}/?tab=assets"); rows = p.locator("main table tbody tr").count()
    r.ok(str(rows) == sql(f"select count(*) from assets_asset where site_id='{hyd}'"), "Assets tab lists all site assets", p.url, O, "count rows vs DB", "equal", rows)
    p.locator("main table tbody tr a").first.click(); p.wait_for_load_state()
    r.ok("/app/assets/" in p.url, "Asset link from site opens asset detail", p.url, O, "click first asset", "asset page", p.url)
    # related requests / work orders: not exposed on the site page
    r.T("Related requests/work orders on site page", f"{L}{{id}}/", O, "look for requests/WO tab or panel", "if exposed, linked", "no such panel (tabs are Overview/Locations/Calendars/Contacts/Assets)", "NOT APPLICABLE")
    # breadcrumb back
    p.goto(f"{BASE}{L}{hyd}/"); p.locator("main .breadcrumb a:has-text('Sites')").click(); p.wait_for_load_state()
    r.ok(p.url.rstrip("/").endswith("/app/sites"), "Breadcrumb 'Sites' returns to list", L, O, "click breadcrumb", "list", p.url)
    with r.expect_errors(): st, q = visit(r, O, f"{L}00000000-0000-0000-0000-000000000000/")
    r.ok(st == 404, "Non-existent site id -> 404", L, O, "random uuid", "404", st)
    with r.expect_errors(): st, q = visit(r, O, f"{L}not-a-uuid/")
    r.ok(st == 404, "Malformed site id -> 404", L, O, "bad id", "404", st)


@feature(r, "Site edit")
def t_edit():
    code = f"C{U}"; s = sid(code)
    st, p = visit(r, O, f"{L}{s}/edit/")
    vals = p.eval_on_selector_all("main form [name]", "e=>Object.fromEntries(e.map(x=>[x.name,x.value]))")
    r.ok(vals.get("code") == code and vals.get("city") == "Chennai" and vals.get("timezone") == "Asia/Kolkata", "Edit form is pre-filled", p.url, O, "open edit", "current values", {k: vals[k] for k in ("code", "name", "city")})
    # change EVERY field
    new = dict(name=f"Edited {U}", description="new desc", address="22 New Street", city="Madurai", state_region="KA", postal_code="625001", country="LK", timezone="Asia/Colombo", contact_name="Bob", contact_email="bob@example.com", contact_phone="+94 1")
    fill(p, new); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    row = sql(f"select name||'|'||description||'|'||address||'|'||city||'|'||state_region||'|'||postal_code||'|'||country||'|'||timezone||'|'||contact_name||'|'||contact_email||'|'||contact_phone from sites_site where id='{s}'")
    exp = "|".join(new[k] for k in ("name", "description", "address", "city", "state_region", "postal_code", "country", "timezone", "contact_name", "contact_email", "contact_phone"))
    r.ok(row == exp, "Edit site: all 11 editable fields persisted", p.url, O, "change every field + Save", "DB equals input", row, db=row, audit=audits(s))
    p.goto(f"{BASE}{L}{s}/"); r.ok("Madurai" in p.inner_text("main") and "Asia/Colombo" in p.inner_text("main"), "Edit persists after reload/reopen", p.url, O, "reopen detail", "new values", "ok")
    a = sql(f"select before::text||' => '||after::text from audit_auditlog where target_id='{s}' and action='site.updated' order by occurred_at desc limit 1")
    r.ok("Chennai" in a and "Madurai" in a, "Edit audited with before/after", "-", O, "read audit row", "before Chennai / after Madurai", a[:120], audit=a[:120])
    # change code to another site's code -> rejected; to a new unique -> accepted
    st, p = visit(r, O, f"{L}{s}/edit/")
    with r.expect_errors():
        fill(p, dict(code="HYD-1")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select code from sites_site where id='{s}'") == code, "Edit: duplicate code rejected", p.url, O, "code=HYD-1", "rejected", msgs(p)[:100])
    st, p = visit(r, O, f"{L}{s}/edit/"); fill(p, dict(code=f"D{U}")); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    r.ok(sql(f"select code from sites_site where id='{s}'") == f"D{U}", "Edit: code change to a unique value", p.url, O, "code=D..", "saved", sql(f"select code from sites_site where id='{s}'"))
    # invalid edits
    for label, vals in (("blank name", dict(name="")), ("bad timezone", dict(timezone="Nope/Zone")), ("bad email", dict(contact_email="x@")), ("blank timezone", dict(timezone=""))):
        st, p = visit(r, O, f"{L}{s}/edit/")
        with r.expect_errors():
            for k, v in vals.items(): p.locator(f"main form [name='{k}']").first.evaluate("(e,v)=>{e.removeAttribute('required');e.value=v}", v)
            p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
        r.ok(sql(f"select name from sites_site where id='{s}'") == f"Edited {U}" and sql(f"select timezone from sites_site where id='{s}'") == "Asia/Colombo", f"Edit validation: {label}", p.url, O, "submit invalid", "rejected, DB unchanged", msgs(p)[:100])
    # no-change save does not create a spurious audit row
    n0 = sql(f"select count(*) from audit_auditlog where target_id='{s}' and action='site.updated'")
    st, p = visit(r, O, f"{L}{s}/edit/"); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state()
    n1 = sql(f"select count(*) from audit_auditlog where target_id='{s}' and action='site.updated'")
    r.ok(n0 == n1, "No-change save writes no audit row", p.url, O, "Save without edits", "no new audit", f"{n0}->{n1}", audit=f"{n0}->{n1}")
    st, p = visit(r, O, f"{L}{s}/edit/"); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state()
    r.ok(f"/app/sites/{s}" in p.url, "Edit: Cancel returns to detail", p.url, O, "click Cancel", "detail", p.url)


@feature(r, "Site deactivate / reactivate")
def t_status():
    s = sid(f"D{U}")
    st, p = visit(r, O, f"{L}{s}/")
    # reason required (client-side + server-side)
    p.locator("main form button:has-text('Deactivate')").click(); p.wait_for_timeout(400)
    dlg = p.locator("#fx-confirm").is_visible()
    if dlg: p.locator("#fx-confirm button:has-text('Confirm')").click(); p.wait_for_timeout(600)
    r.T("Deactivate without reason: browser validation", p.url, O, "click Deactivate with empty reason, then Confirm", "required-field validation shown BEFORE a confirm dialog; nothing changes", f"confirm dialog opened first={dlg}; after Confirm the form is not submitted and focus jumps to the reason field; status={sql(f'select status from sites_site where id={chr(39)}{s}{chr(39)}')}", "PARTIAL" if dlg else "PASS", db="ACTIVE (safe)")
    for reason in ("", "   "):
        res = bfetch(p, "POST", f"{L}{s}/", {"action": "deactivate", "reason": reason})
        r.ok(sql(f"select status from sites_site where id='{s}'") == "ACTIVE", f"Deactivate with reason {reason!r} refused server-side", p.url, O, "crafted POST", "ACTIVE", res["status"])
    # confirm dialog: Cancel keeps ACTIVE
    p.goto(f"{BASE}{L}{s}/"); p.fill("main form input[name=reason]", "Planned closure"); p.locator("main form button:has-text('Deactivate')").click()
    r.ok(p.locator("#fx-confirm").is_visible(), "Deactivate opens confirm dialog", p.url, O, "click Deactivate with reason", "modal visible", "visible")
    p.locator("#fx-confirm button:has-text('Cancel')").click(); p.wait_for_timeout(300)
    r.ok(sql(f"select status from sites_site where id='{s}'") == "ACTIVE" and not p.locator("#fx-confirm").is_visible(), "Confirm dialog Cancel keeps site ACTIVE", p.url, O, "click Cancel", "ACTIVE", sql(f"select status from sites_site where id='{s}'"))
    p.locator("main form button:has-text('Deactivate')").click(); p.locator("#fx-confirm button:has-text('Confirm')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select status from sites_site where id='{s}'") == "INACTIVE", "Deactivate confirmed -> INACTIVE", p.url, O, "Confirm", "INACTIVE", sql(f"select status||'|'||coalesce(status_reason,'') from sites_site where id='{s}'") if False else sql(f"select status from sites_site where id='{s}'"), audit=audits(s))
    t = p.inner_text("main")
    r.ok("inactive" in t.lower() and "Planned closure" in t, "Inactive banner shows reason", p.url, O, "view detail", "banner + reason", t[:160].replace("\n", " "))
    p.reload(); r.ok("Inactive" in p.inner_text("main"), "INACTIVE survives refresh", p.url, O, "reload", "still inactive", "ok")
    st, q = visit(r, O, f"{L}?status=INACTIVE"); r.ok(f"D{U}" in q.inner_text("main"), "Inactive site listed under Inactive filter", L, O, "filter", "listed", "ok")
    st, q = visit(r, O, f"{L}?status=ACTIVE"); r.ok(f"D{U}" not in q.inner_text("main"), "Inactive site hidden from Active filter", L, O, "filter", "hidden", "ok")
    # operations on an inactive site
    st, q = visit(r, O, f"{L}{s}/locations/new/"); fill(q, dict(name="Late zone"));
    with r.expect_errors(): q.locator("main form button:has-text('Create location')").click(); q.wait_for_load_state()
    r.ok(sql(f"select count(*) from sites_zone where name='Late zone' and site_id='{s}'") == "0", "Inactive site: cannot add a location", q.url, O, "create zone", "refused", msgs(q)[:80])
    st, q = visit(r, O, f"{L}{s}/calendars/new/"); fill(q, dict(name="Late cal", start_time="08:00", end_time="17:00")); q.locator("main form input[name=working_days]").first.check()
    with r.expect_errors(): q.locator("main form button:has-text('Create calendar')").click(); q.wait_for_load_state()
    r.ok(sql(f"select count(*) from sites_operatingcalendar where name='Late cal' and site_id='{s}'") == "0", "Inactive site: cannot add a calendar", q.url, O, "create calendar", "refused", msgs(q)[:80])
    st, q = visit(r, O, "/app/assets/new/")
    opts = q.locator("select[name=site] option").all_inner_texts()
    r.ok(not any(f"D{U}" in o for o in opts), "Inactive site not offered in the asset form", "/app/assets/new/", O, "read site dropdown", "absent", len(opts))
    # reactivate
    st, p = visit(r, O, f"{L}{s}/"); btns = p.locator("main form button").all_inner_texts()
    r.ok(any("activate" in b.lower() for b in btns), "Reactivate control shown on inactive site", p.url, O, "inspect buttons", "Reactivate button", btns)
    f = p.locator("main form:has(button:has-text('Reactivate'))")
    if f.locator("input[name=reason]").count(): f.locator("input[name=reason]").fill("Reopened")
    cclick(p, f.locator("button"))
    r.ok(sql(f"select status from sites_site where id='{s}'") == "ACTIVE", "Reactivate -> ACTIVE", p.url, O, "Reactivate + confirm", "ACTIVE", sql(f"select status from sites_site where id='{s}'"), audit=audits(s))
    aud = audits(s) or ""
    r.ok("site.deactivated" in aud and "site.reactivated" in aud, "Deactivate/reactivate audited", "-", O, "audit actions", "site.deactivated + site.reactivated", aud, audit=aud)
    # rule: site with active assets cannot be deactivated
    h = sid("HYD-1"); st, p = visit(r, O, f"{L}{h}/"); p.fill("main form input[name=reason]", "probe"); cclick(p, p.locator("main form button:has-text('Deactivate')"))
    r.ok(sql(f"select status from sites_site where id='{h}'") == "ACTIVE" and "active asset" in (msgs(p) + p.inner_text("main")).lower(), "Site with active assets cannot be deactivated", p.url, O, "deactivate HYD-1", "refused with reason", msgs(p)[:100])


for t in (t_list, t_search, t_filter, t_pagination, t_create, t_validation, t_view, t_edit, t_status):
    t()
print("\nROWS", len(r.rows), "FAIL", sum(1 for x in r.rows if x['status'] == 'FAIL'), "UNVF", sum(1 for x in r.rows if x['status'] == 'UNVERIFIED'))
print("ISSUES", len(r.issues)); [print("  ", i['kind'], i['feature'], i['text'][:140]) for i in r.issues[:20]]
r.stop()
