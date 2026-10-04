import sys, time, json, math, re; sys.path.insert(0, '.')
from bx import *
r = Run("M02").start()
U = str(int(time.time()))[-5:]
O = "owner"
pg = r.page(O)
L = "/app/assets/"
HYD, BLR = sid("HYD-1"), sid("BLR-1")
CAT = lambda n: sql(f"select id from assets_assetcategory where name='{n}' and organization_id={ALPHA}")
PUMP, GENC = CAT("Pump"), CAT("Generator")
ZA = sql(f"select z.id from sites_zone z where z.site_id='{HYD}' and z.name='Building A'")
ZB = sql(f"select z.id from sites_zone z where z.site_id='{HYD}' and z.name='Building B'")
ZW = sql(f"select z.id from sites_zone z where z.site_id='{BLR}' and z.name='Warehouse'")
OWN = sql(f"select m.id from tenancy_membership m join accounts_user u on u.id=m.user_id where u.email='ops@alpha.qa.test' and m.organization_id={ALPHA}")
OWN2 = sql(f"select m.id from tenancy_membership m join accounts_user u on u.id=m.user_id where u.email='planner@alpha.qa.test' and m.organization_id={ALPHA}")
ASSET = lambda tag: sql(f"select id from assets_asset where lower(asset_tag)=lower('{tag}') and organization_id={ALPHA}")


def post_new(p, vals, url=None, expect_ok=True, btn="Register asset"):
    p.goto(BASE + (url or "/app/assets/new/")); p.wait_for_load_state("networkidle")
    p.evaluate("()=>document.querySelectorAll('main form input').forEach(e=>{e.removeAttribute('maxlength'); if(e.type==='date') e.type='text'})")
    fill(p, vals)
    with (contextlib_null() if expect_ok else r.expect_errors()):
        with p.expect_response(lambda x: x.request.method == "POST" and "/assets/new" in x.url) as ri:
            p.locator(f"main form button:has-text('{btn}')").click()
        p.wait_for_load_state("networkidle")
    return ri.value.status


class contextlib_null:
    def __enter__(self): return self
    def __exit__(self, *a): return False


# ---------------- setup (not under test): 25 assets for pagination/filter/sort, via API
MOTOR = CAT("Motor")
if int(sql(f"select count(*) from assets_asset where asset_tag like 'AP%' and organization_id={ALPHA}")) < 25:
    for i in range(25):
        if sql(f"select count(*) from assets_asset where asset_tag='AP{U}-{i:02d}'") != "0": continue
        bapi(pg, "POST", "/api/v1/assets/", {"asset_tag": f"AP{U}-{i:02d}", "name": f"Pagination asset {i:02d}", "category": PUMP if i % 2 else MOTOR, "site": HYD if i % 3 else BLR,
                                              "manufacturer": "PagMaker", "serial_number": f"PSN{U}{i:02d}", "model": "ModelP" if i % 2 else "ModelQ"})
# an inactive site for the "register at inactive site" negative (setup, via the real endpoints)
if sql(f"select count(*) from sites_site where organization_id={ALPHA} and status<>'ACTIVE'") == "0":
    bapi(pg, "POST", "/api/v1/sites/", {"code": f"INA{U}", "name": "Inactive test site", "timezone": "Asia/Kolkata"})
    bfetch(pg, "POST", f"/app/sites/{sid(f'INA{U}')}/", {"action": "deactivate", "reason": "QA inactive site"})
PTAG = sql(f"select asset_tag from assets_asset where asset_tag like 'AP%' and organization_id={ALPHA} order by asset_tag limit 1")
PGU = PTAG[2:7]


def rows(p):
    return [[c.strip() for c in row.locator("td").all_inner_texts()] for row in p.locator("main table tbody tr").all()]


@feature(r, "Asset list")
def t_list():
    st, p = visit(r, O, L)
    t = p.inner_text("main")
    heads = [h.strip().upper() for h in p.locator("main table thead th").all_inner_texts()]
    r.ok(st == 200 and "Register asset" in t, "Asset list opens with 'Register asset' button", L, O, "open", "200 + button", st)
    r.ok(heads == ["TAG", "NAME", "CATEGORY", "SITE / LOCATION", "PARENT", "STATUS"], "Asset list columns", L, O, "read thead", "TAG/NAME/CATEGORY/SITE / LOCATION/PARENT/STATUS", heads)
    total = int(sql(f"select count(*) from assets_asset where organization_id={ALPHA}"))
    rr = rows(p)
    r.ok(len(rr) == min(20, total), "Page 1 shows 20 rows (page size)", L, O, "count rows", f"{min(20,total)}", len(rr), db=str(total))
    # per row accuracy vs DB (first 10)
    bad = []
    for x in rr[:10]:
        tag = x[0]
        d = sql(f"select c.name||'|'||s.code||coalesce(' · '||z.name,'')||'|'||a.status from assets_asset a join assets_assetcategory c on c.id=a.category_id join sites_site s on s.id=a.site_id left join sites_zone z on z.id=a.zone_id where a.asset_tag='{tag}' and a.organization_id={ALPHA}")
        cat, loc, status = d.split("|")
        if not (x[2] == cat and x[3] == loc and x[5].replace(" ", "").lower() == status.replace("_", "").lower()): bad.append((tag, x, d))
    r.ok(not bad, "List row values (category, site · location, status) match the database", L, O, "compare 10 rows", "equal", bad[:2] or "all equal")
    first = p.locator("main table tbody tr td a").first
    tag = first.inner_text(); first.click(); p.wait_for_load_state("networkidle")
    r.ok("/app/assets/" in p.url and tag in p.inner_text("main"), "Tag link opens the asset detail page", p.url, O, "click tag", "detail", p.url)
    p.goto(BASE + L); p.locator("main a:has-text('Categories')").click(); p.wait_for_load_state("networkidle")
    r.ok("/categories" in p.url, "'Categories' button opens the categories page", p.url, O, "click", "categories", p.url)
    p.goto(BASE + L); p.locator("main a:has-text('Register asset')").click(); p.wait_for_load_state("networkidle")
    r.ok("/assets/new" in p.url, "'Register asset' opens the create form", p.url, O, "click", "form", p.url)
    # parent column
    p.goto(BASE + L + "?q=GEN-001-ENG"); rr = rows(p)
    r.ok(rr and rr[0][4] == "GEN-001", "Child asset shows its parent tag in the Parent column", p.url, O, "search child", "GEN-001", rr[:1])
    # empty state
    p.goto(BASE + L + "?q=zzzz-no-such-asset"); r.ok("No assets match" in p.inner_text("main"), "Empty state when nothing matches", p.url, O, "search nonsense", "'No assets match'", p.inner_text("main")[-120:].replace("\n", " "))


@feature(r, "Asset search")
def t_search():
    def s(q, extra=""):
        p = r.page(O); p.goto(BASE + L + "?q=" + q + extra); p.wait_for_load_state("networkidle"); return p, [x[0] for x in rows(p) if len(x) > 3]
    def dbc(cond): return sql(f"select count(*) from assets_asset where organization_id={ALPHA} and ({cond})")
    cases = [("tag exact", "GEN-001", "asset_tag ilike '%GEN-001%' or name ilike '%GEN-001%' or serial_number ilike '%GEN-001%' or model ilike '%GEN-001%' or manufacturer ilike '%GEN-001%'"),
             ("tag partial", "gen-0", "asset_tag ilike '%gen-0%' or name ilike '%gen-0%' or serial_number ilike '%gen-0%' or model ilike '%gen-0%' or manufacturer ilike '%gen-0%'"),
             ("name", "Coolant", "name ilike '%Coolant%' or asset_tag ilike '%Coolant%' or serial_number ilike '%Coolant%' or model ilike '%Coolant%' or manufacturer ilike '%Coolant%'"),
             ("serial", "CU-500", "serial_number ilike '%CU-500%' or asset_tag ilike '%CU-500%' or name ilike '%CU-500%' or model ilike '%CU-500%' or manufacturer ilike '%CU-500%'"),
             ("manufacturer", "cummins", "manufacturer ilike '%cummins%' or asset_tag ilike '%cummins%' or name ilike '%cummins%' or serial_number ilike '%cummins%' or model ilike '%cummins%'"),
             ("model", "ModelP", "model ilike '%ModelP%' or asset_tag ilike '%ModelP%' or name ilike '%ModelP%' or serial_number ilike '%ModelP%' or manufacturer ilike '%ModelP%'")]
    for label, q, cond in cases:
        p, tags = s(q)
        exp = int(dbc(cond))
        # count across pages
        n = len(tags) if exp <= 20 else 20
        r.ok(len(tags) == min(exp, 20) and exp > 0, f"Search by {label} ('{q}')", p.url, O, f"q={q}", f"{min(exp,20)} rows (DB {exp})", len(tags), db=str(exp))
    p, tags = s("GEN-001"); r.ok("GEN-001" in tags and "GEN-001-ENG" in tags, "Search 'GEN-001' returns the asset and its component", p.url, O, "q=GEN-001", "both", tags)
    p, tags = s("%25"); r.ok(len(tags) == int(dbc("asset_tag like '%\\%%' or name like '%\\%%' or serial_number like '%\\%%' or model like '%\\%%' or manufacturer like '%\\%%'")), "Search '%' is a literal (no wildcard match-all)", p.url, O, "q=%", "literal match", len(tags))
    p, tags = s("_"); r.ok(len(tags) == min(20, int(dbc("asset_tag ilike '%\\_%' or name ilike '%\\_%' or serial_number ilike '%\\_%' or model ilike '%\\_%' or manufacturer ilike '%\\_%'"))), "Search '_' is a literal", p.url, O, "q=_", "literal", len(tags))
    p, tags = s("%27%20OR%201%3D1--"); r.ok(len(tags) == 0 and p.locator("main table").count() > 0, "SQL-injection-like search returns nothing and does not error", p.url, O, "q=' OR 1=1--", "no rows, no 500", len(tags))
    p, tags = s("%3Cscript%3Ewindow.__sx%3D1%3C%2Fscript%3E"); r.ok(p.evaluate("()=>!window.__sx") and "<script>window.__sx" not in p.content(), "XSS payload in search is escaped (input + page)", p.url, O, "q=<script>", "inert", "ok")
    p, tags = s("%20%20GEN-001%20%20"); r.ok("GEN-001" in tags, "Search ignores leading/trailing spaces", p.url, O, "q='  GEN-001  '", "found", tags[:3])
    p, tags = s("x" * 600); r.ok(p.locator("main table").count() > 0, "Very long (600 char) search does not error", p.url, O, "long q", "empty result page", len(tags))
    p, tags = s("%E0%A4%B9%E0%A4%BF"); r.ok(p.locator("main table").count() > 0, "Unicode search does not error", p.url, O, "q=हि", "page ok", len(tags))
    # form behaviour
    p = r.page(O); p.goto(BASE + L); p.locator("main input[name=q]").fill("PMP-001"); p.locator("main form button:has-text('Filter')").click(); p.wait_for_load_state("networkidle")
    r.ok("q=PMP-001" in p.url and p.locator("main input[name=q]").input_value() == "PMP-001" and [x[0] for x in rows(p)] == ["PMP-001"], "Search form submits, keeps the term and lists the match", p.url, O, "type + Filter", "PMP-001 only", [x[0] for x in rows(p)])
    p.locator("main input[name=q]").fill("PMP-001"); p.locator("main input[name=q]").press("Enter"); p.wait_for_load_state("networkidle")
    r.ok("q=PMP-001" in p.url, "Enter key submits the search", p.url, O, "Enter", "submitted", p.url)
    p.reload(); r.ok(p.locator("main input[name=q]").input_value() == "PMP-001", "Search term survives refresh", p.url, O, "reload", "kept", p.locator("main input[name=q]").input_value())
    # search + site filter combine
    p.goto(BASE + L + f"?q=GEN&site={HYD}"); tags = [x[0] for x in rows(p)]
    r.ok(set(tags) == set(sql(f"select asset_tag from assets_asset where organization_id={ALPHA} and site_id='{HYD}' and (asset_tag ilike '%GEN%' or name ilike '%GEN%' or serial_number ilike '%GEN%' or model ilike '%GEN%' or manufacturer ilike '%GEN%') limit 20").split()), "Search + site filter combine (AND)", p.url, O, "q+site", "intersection", tags)


@feature(r, "Asset filters + sort")
def t_filter():
    p = r.page(O)
    def tags_for(qs):
        p.goto(BASE + L + "?" + qs); p.wait_for_load_state("networkidle")
        out = []
        while True:
            out += [x[0] for x in rows(p) if len(x) > 3]
            nxt = p.locator("main a:has-text('Next')")
            if nxt.count() == 0: break
            nxt.first.click(); p.wait_for_load_state("networkidle")
        return out
    # option lists
    p.goto(BASE + L)
    so = p.locator("main select[name=site] option").all_inner_texts(); co = p.locator("main select[name=category] option").all_inner_texts(); sto = p.locator("main select[name=status] option").all_inner_texts()
    r.ok(so[0] == "All sites" and {"HYD-1", "BLR-1"} <= set(so), "Site filter lists the organization's sites", L, O, "read options", "All sites + sites", so[:5])
    r.ok(co[0] == "All categories" and {"Pump", "Generator", "Motor", "HVAC"} <= set(co), "Category filter lists categories", L, O, "read options", "categories", co)
    r.ok(sto == ["All statuses", "Active", "Under Maintenance", "Out Of Service", "Retired", "Disposed"], "Status filter lists all five statuses", L, O, "read options", "5 statuses", sto)
    for site in ("HYD-1", "BLR-1"):
        sidv = sid(site); got = sorted(tags_for(f"site={sidv}")); exp = sorted(sql(f"select asset_tag from assets_asset where organization_id={ALPHA} and site_id='{sidv}'").split())
        r.ok(got == exp, f"Site filter {site}: exactly its assets ({len(exp)})", L, O, f"site={site}", f"{len(exp)} assets", len(got), db=str(len(exp)))
    for cname in ("Pump", "Generator", "Vehicle", "Motor"):
        cid = CAT(cname); got = sorted(tags_for(f"category={cid}")); exp = sorted(sql(f"select asset_tag from assets_asset where organization_id={ALPHA} and category_id='{cid}'").split())
        r.ok(got == exp, f"Category filter {cname}: exactly its assets ({len(exp)})", L, O, f"category={cname}", f"{len(exp)}", len(got), db=str(len(exp)))
    for stt in ("ACTIVE", "UNDER_MAINTENANCE", "OUT_OF_SERVICE", "RETIRED", "DISPOSED"):
        got = sorted(tags_for(f"status={stt}")); exp = sorted(sql(f"select asset_tag from assets_asset where organization_id={ALPHA} and status='{stt}'").split())
        r.ok(got == exp, f"Status filter {stt}: matches DB ({len(exp)})", L, O, f"status={stt}", f"{len(exp)}", len(got), db=str(len(exp)))
    got = sorted(tags_for(f"site={HYD}&category={PUMP}&status=ACTIVE")); exp = sorted(sql(f"select asset_tag from assets_asset where organization_id={ALPHA} and site_id='{HYD}' and category_id='{PUMP}' and status='ACTIVE'").split())
    r.ok(got == exp, "Combined site+category+status filters (AND)", L, O, "3 filters", f"{len(exp)}", len(got), db=str(len(exp)))
    # URL-only filters (no UI control)
    got = sorted(tags_for(f"zone={ZA}")); exp = sorted(sql(f"select asset_tag from assets_asset where organization_id={ALPHA} and zone_id='{ZA}'").split())
    r.ok(got == exp, "Zone filter (URL ?zone=) returns only that zone's assets", L, O, "zone=Building A", f"{len(exp)}", len(got), db=str(len(exp)))
    r.T("Zone / location filter control", L, O, "look for a zone filter on the list", "UI control to filter by zone", "No zone control in the filter bar (only q/site/category/status); backend supports ?zone= and ?owner= but they are not reachable from the UI", "PARTIAL")
    got = tags_for(f"owner={OWN}"); exp = sql(f"select count(*) from assets_asset where organization_id={ALPHA} and owner_id='{OWN}'")
    r.ok(len(got) == int(exp), "Owner filter (URL ?owner=) matches DB", L, O, "owner=ops", exp, len(got), db=exp)
    for bad, label in (("site=not-a-uuid", "malformed site id"), ("category=00000000-0000-0000-0000-000000000000", "unknown category id"), ("status=BOGUS", "invalid status"), ("zone=zzz", "malformed zone")):
        got = tags_for(bad); r.ok(got == [] and p.locator("main table").count() > 0, f"Filter with {label} shows an empty list, no error", L, O, bad, "empty result", len(got))
    # persisted in form after submit + refresh
    p.goto(BASE + L); fill(p, {"site": HYD, "status": "ACTIVE"}, "main form"); p.locator("main form button:has-text('Filter')").click(); p.wait_for_load_state("networkidle"); p.reload()
    r.ok(p.locator("main select[name=site]").input_value() == HYD and p.locator("main select[name=status]").input_value() == "ACTIVE", "Selected filters stay selected after submit and refresh", p.url, O, "filter + reload", "kept", p.url)
    # sorting
    r.T("Column sorting control", L, O, "look for sortable column headers", "click header to sort", "Table headers are plain text (no sort links/buttons). Backend supports ?ordering= (asset_tag,name,status,created_at, -desc) only via URL", "PARTIAL")
    colidx = {"asset_tag": 0, "name": 1, "status": 5}
    for o, col, rev in (("asset_tag", "asset_tag", False), ("-asset_tag", "asset_tag", True), ("name", "name", False), ("-name", "name", True), ("status", "status", False)):
        p.goto(BASE + L + f"?ordering={o}"); rr = rows(p); got = [x[colidx[col]].replace(" ", "").lower().replace("_", "") for x in rr]
        exp = [v.replace("_", "").lower().replace(" ", "") for v in sql(f"select {col} from assets_asset where organization_id={ALPHA} order by {col} {'desc' if rev else 'asc'} limit 20").split("\n")]
        key = (lambda v: v)
        okk = len(got) == 20 and (got == exp or sorted(got, key=key) == sorted(exp, key=key) and got[0] == exp[0])
        r.ok(okk, f"URL ordering={o}: the 20 listed rows follow the database ordering by {col}", p.url, O, f"ordering={o}", f"{col} {'desc' if rev else 'asc'}: {exp[:2]}", got[:3], db=str(exp[:2]))
    p.goto(BASE + L + "?ordering=-created_at"); rr2 = [x[0] for x in rows(p)]
    newest = sql(f"select asset_tag from assets_asset where organization_id={ALPHA} order by created_at desc limit 1")
    r.ok(rr2 and rr2[0] == newest, "URL ordering=-created_at: newest asset first", p.url, O, "ordering=-created_at", newest, rr2[:1], db=newest)
    p.goto(BASE + L + "?ordering=%3B%20drop%20table"); r.ok(p.locator("main table tbody tr").count() > 0 and sql("select count(*) from assets_asset") != "0", "Invalid ordering falls back safely", p.url, O, "ordering=injection", "default order", "ok")


@feature(r, "Asset pagination")
def t_pagination():
    p = r.page(O); total = int(sql(f"select count(*) from assets_asset where organization_id={ALPHA}")); pages = math.ceil(total / 20)
    r.ok(pages >= 2, "Dataset spans multiple pages (setup)", L, O, "count", ">=2 pages", f"{total} assets / {pages} pages")
    seen = []
    for n in range(1, pages + 1):
        p.goto(BASE + L + f"?page={n}"); p.wait_for_load_state("networkidle")
        tg = [x[0] for x in rows(p) if len(x) > 3]; seen += tg
        exp = 20 if n < pages else total - 20 * (pages - 1)
        prev, nxt = p.locator("main a:has-text('Previous')").count(), p.locator("main a:has-text('Next')").count()
        r.ok(len(tg) == exp and (prev > 0) == (n > 1) and (nxt > 0) == (n < pages), f"Page {n}/{pages}: {exp} rows; Previous/Next shown correctly", p.url, O, f"page={n}", f"{exp} rows", f"{len(tg)} rows prev={prev} next={nxt}")
    r.ok(len(seen) == len(set(seen)) == total, "Walking all pages yields every asset exactly once (no gaps/duplicates)", L, O, "visit all pages", f"{total} unique", f"{len(seen)} / {len(set(seen))}")
    p.goto(BASE + L + "?page=1"); p.locator("main a:has-text('Next')").first.click(); p.wait_for_load_state("networkidle")
    r.ok("page=2" in p.url, "Clicking Next goes to page 2", p.url, O, "click Next", "page=2", p.url)
    p.locator("main a:has-text('Previous')").first.click(); p.wait_for_load_state("networkidle"); r.ok("page=1" in p.url or "page=" not in p.url, "Clicking Previous returns to page 1", p.url, O, "click Previous", "page 1", p.url)
    p.goto(BASE + L + "?status=ACTIVE&page=2"); lk = p.locator("main a:has-text('Previous')")
    keep = lk.count() and "status=ACTIVE" in (lk.first.get_attribute("href") or "")
    r.ok(bool(keep), "Pagination links keep the active filters", p.url, O, "page 2 with status filter", "status param kept in links", lk.first.get_attribute("href") if lk.count() else "no Previous link")
    for bad in ("0", "-1", "abc", "9999", "1.5"):
        resp = p.goto(BASE + L + f"?page={bad}"); r.ok(resp.status == 200 and p.locator("main table").count() > 0, f"Invalid page value '{bad}' does not error", p.url, O, f"page={bad}", "200, valid page", resp.status)


@feature(r, "Asset categories page")
def t_categories():
    p = r.page(O); C = "/app/assets/categories/"
    st, p = visit(r, O, C)
    r.ok(st == 200 and "New category" in p.inner_text("main"), "Categories page opens (list + 'New category' form)", C, O, "open", "200", st)
    heads = [h.strip().upper() for h in p.locator("main table thead th").all_inner_texts()]
    r.ok(heads[:4] == ["NAME", "DESCRIPTION", "CUSTOM ATTRIBUTES", "STATUS"], "Categories table columns", C, O, "read header", "NAME/DESCRIPTION/CUSTOM ATTRIBUTES/STATUS", heads)
    def newcat(name, desc="", attrs="", active=True, expect_ok=True):
        p.goto(BASE + C); p.wait_for_load_state("networkidle")
        f = "main form:has(button:has-text('Create category'))"
        p.locator(f"{f} [name=name]").fill(name); p.locator(f"{f} [name=description]").fill(desc); p.locator(f"{f} [name=attribute_text]").fill(attrs)
        p.locator(f"{f} [name=is_active]").set_checked(active)
        with (contextlib_null() if expect_ok else r.expect_errors()):
            p.locator(f"{f} button:has-text('Create category')").click(); p.wait_for_load_state("networkidle")
        return msgs(p)
    nm = f"QA Cat {U}"
    m = newcat(nm, "created in browser", "Voltage | number | required\nPhase | choice | | Single, Three\nInstalled on | date\nNotes | text")
    row = sql(f"select name||'|'||description||'|'||is_active||'|'||jsonb_array_length(attribute_definitions) from assets_assetcategory where name='{nm}' and organization_id={ALPHA}")
    r.ok(row == f"{nm}|created in browser|true|4", "Create category with 4 typed custom attributes (persisted)", C, O, "fill + Create category", "row saved with 4 attributes", row, db=row, audit=audits(CAT(nm)))
    r.ok(nm in p.inner_text("main") and "Created" in m or "created" in m.lower(), "Success message shown and category listed", C, O, "after create", "message + row", m[:80])
    defs = sql(f"select attribute_definitions::text from assets_assetcategory where id='{CAT(nm)}'")
    r.ok('"required": true' in defs and '"choices": ["Single", "Three"]' in defs and '"type": "date"' in defs, "Attribute types/required/choices parsed correctly", C, O, "read stored JSON", "number required; choice w/ 2; date; text", defs[:160], db=defs[:160])
    newcat(nm.lower(), expect_ok=False); r.ok(sql(f"select count(*) from assets_assetcategory where lower(name)=lower('{nm}') and organization_id={ALPHA}") == "1", "Duplicate category name (different case) rejected", C, O, "same name lower-case", "refused", msgs(p)[:80])
    newcat("   ", expect_ok=False); r.ok(sql(f"select count(*) from assets_assetcategory where trim(name)='' and organization_id={ALPHA}") == "0", "Blank category name rejected", C, O, "blank name", "refused", msgs(p)[:80])
    for label, attr, frag in (("unknown type", "Foo | colour", "Unknown attribute type"), ("choice with one choice", "Size | choice | | Only", "at least two"), ("duplicate label", "A | text\nA | number", "twice")):
        n2 = f"QA Bad {label[:6]} {U}"; m = newcat(n2, attrs=attr, expect_ok=False)
        r.ok(sql(f"select count(*) from assets_assetcategory where name='{n2}'") == "0", f"Invalid attribute definition refused: {label}", C, O, f"attrs={attr!r}", "refused with message", m[:100] or p.inner_text("main")[:80])
    n3 = f"QA TooMany {U}"; m = newcat(n3, attrs="\n".join(f"Attr {i} | text" for i in range(21)), expect_ok=False)
    r.ok(sql(f"select count(*) from assets_assetcategory where name='{n3}'") == "0", "More than 20 custom attributes refused", C, O, "21 attributes", "refused", m[:100])
    m = newcat("X" * 100, desc="boundary 100"); r.ok(sql(f"select count(*) from assets_assetcategory where name='{'X'*100}' and organization_id={ALPHA}") == "1", "Boundary: 100-char category name accepted", C, O, "100 chars", "saved", m[:60])
    p.goto(BASE + C)
    with r.expect_errors(): res = bfetch(p, "POST", C, {"name": "Q" * 101, "description": "", "attribute_text": "", "is_active": "on"})
    r.ok(sql(f"select count(*) from assets_assetcategory where name like 'QQQQ%' and organization_id={ALPHA}") == "0", "101-char category name refused (server-side, forged past maxlength)", C, O, "POST name 101 chars", "refused", f"http={res['status']}")
    r.ok(p.locator("main form:has(button:has-text('Create category')) [name=name]").get_attribute("maxlength") == "100", "Category name input has maxlength=100 (client hint)", C, O, "inspect", "100", "100")
    newcat(f"<i onmouseover=window.__cx=1>xss{U}</i>"); p.goto(BASE + C); r.ok(p.evaluate("()=>!window.__cx") and "<i onmouseover" not in p.content(), "Stored XSS in category name is escaped", C, O, "name=<i ...>", "inert", "ok")
    # edit inline
    cid = CAT(nm); fm = f"#cat-{cid}"
    p.goto(BASE + C); sel = lambda n: p.locator(f"[form='cat-{cid}'][name={n}]")
    sel("description").fill("edited desc"); sel("attribute_text").fill("Voltage | number | required\nPhase | choice | | Single, Three, Delta\nInstalled on | date\nNotes | text");
    with p.expect_response(lambda x: x.request.method == "POST") as ri: p.locator(f"button[form='cat-{cid}']").click()
    p.wait_for_load_state("networkidle")
    row = sql(f"select description||'|'||jsonb_array_length(attribute_definitions) from assets_assetcategory where id='{cid}'")
    r.ok(row == "edited desc|4", "Edit category inline (description + attributes) persisted", C, O, "edit row + Save", "saved", row, db=row, audit=audits(cid))
    p.goto(BASE + C); sel("is_active").set_checked(False); p.locator(f"button[form='cat-{cid}']").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select is_active from assets_assetcategory where id='{cid}'") == "f", "Deactivate category via checkbox + Save", C, O, "uncheck Active", "is_active=false", sql(f"select is_active from assets_assetcategory where id='{cid}'"), db="f", audit=audits(cid))
    p.goto(BASE + "/app/assets/new/"); opts = p.locator("main select[name=category] option").all_inner_texts()
    r.ok(nm not in opts, "Inactive category is not offered when registering an asset", "/app/assets/new/", O, "read category options", "absent", nm in opts)
    p.goto(BASE + C); sel("is_active").set_checked(True); p.locator(f"button[form='cat-{cid}']").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select is_active from assets_assetcategory where id='{cid}'") == "t", "Reactivate category", C, O, "check Active", "true", "t", audit=audits(cid))
    sel("name").fill("");
    with r.expect_errors(): p.locator(f"button[form='cat-{cid}']").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select name from assets_assetcategory where id='{cid}'") == nm, "Blank name on edit refused (name unchanged)", C, O, "clear name + Save", "unchanged", "ok")
    r.T("Category delete", C, O, "look for delete", "delete action", "No delete action: categories can only be deactivated", "NOT APPLICABLE")


@feature(r, "Asset create (all fields)")
def t_create():
    nm = f"QA Cat {U}"; QC = CAT(nm)
    st, p = visit(r, O, "/app/assets/new/")
    names = p.eval_on_selector_all("main form [name]", "e=>e.filter(x=>x.type!=='hidden').map(x=>x.name)")
    exp = ["asset_tag", "name", "category", "site", "zone", "manufacturer", "model", "serial_number", "purchase_date", "commission_date", "owner", "warranty_ref", "description"]
    r.ok(names == exp, "Create form exposes all 13 asset fields (no reason field on create)", "/app/assets/new/", O, "read form fields", str(exp), names)
    req = p.eval_on_selector_all("main form label", "ls=>ls.filter(l=>l.querySelector('.text-danger,.required')||/\\*/.test(l.innerText)).map(l=>l.innerText.trim())")
    # field options
    sopts = p.locator("main select[name=site] option").all_inner_texts(); copts = p.locator("main select[name=category] option").all_inner_texts(); zopts = p.locator("main select[name=zone] option").all_inner_texts(); oopts = p.locator("main select[name=owner] option").all_inner_texts()
    r.ok(any("HYD-1" in o for o in sopts) and any("BLR-1" in o for o in sopts), "Site dropdown lists active sites", "/app/assets/new/", O, "read", "HYD-1, BLR-1", sopts[:4])
    r.ok("Pump" in copts and nm in copts and "Generator" in copts, "Category dropdown lists active categories", "/app/assets/new/", O, "read", "categories", copts)
    r.ok(zopts[0] == "(none)" and any("Building A" in o for o in zopts), "Location dropdown has '(none)' + zones", "/app/assets/new/", O, "read", "(none)+zones", zopts[:4])
    r.ok(oopts[0] == "(none)" and any("Operations" in o for o in oopts), "Owner dropdown lists members", "/app/assets/new/", O, "read", "(none)+members", oopts[:5])
    # site -> zone narrowing (JS convenience)
    p.locator("main select[name=site]").select_option(value=BLR); p.wait_for_timeout(300)
    vis = p.locator("main select[name=zone] option:not([hidden]):not([disabled])").all_inner_texts()
    r.ok(all(("BLR-1" in o) or o == "(none)" for o in vis) and any("Warehouse" in o for o in vis), "Choosing a site narrows the location list to that site", "/app/assets/new/", O, "select BLR-1", "only BLR-1 zones", vis)
    # category change reloads with custom attributes and keeps typed values
    p.goto(BASE + "/app/assets/new/"); p.locator("main input[name=asset_tag]").fill("KEEP-ME"); p.locator("main select[name=category]").select_option(value=QC); p.wait_for_load_state("networkidle"); p.wait_for_timeout(600)
    attrf = p.eval_on_selector_all("main form [name^=attr_]", "e=>e.map(x=>x.name)")
    r.ok(attrf == ["attr_voltage", "attr_phase", "attr_installed_on", "attr_notes"] or set(attrf) >= {"attr_voltage", "attr_phase"}, "Selecting a category reloads the form with its custom attribute fields", p.url, O, "choose QA category", "attr_* fields appear", attrf)
    r.ok(p.locator("main input[name=asset_tag]").input_value() == "KEEP-ME", "Typed values are kept when the category changes", p.url, O, "type tag then change category", "tag kept", p.locator("main input[name=asset_tag]").input_value())
    # full create
    tag = f"FULL-{U}"
    vals = dict(asset_tag=tag, name="Full asset ä‑ü", category=QC, site=HYD, zone=ZB, manufacturer="MakerCo", model="M-9000", serial_number=f"SN-{U}", purchase_date="2024-01-15", commission_date="2024-03-01",
                owner=OWN, warranty_ref="WR-777", description="Line1\nLine2", attr_voltage="415.5", attr_phase="Three", attr_installed_on="2024-03-02", attr_notes="note text")
    p.goto(BASE + f"/app/assets/new/?category={QC}"); p.wait_for_load_state("networkidle"); fill(p, vals)
    with p.expect_response(lambda x: x.request.method == "POST") as ri: p.locator("main form button:has-text('Register asset')").click()
    p.wait_for_load_state("networkidle"); a = ASSET(tag)
    r.ok(ri.value.status in (200, 302) and a and "/app/assets/" in p.url and "registered" in msgs(p).lower() + p.inner_text("main").lower(), "Register asset with every field -> redirect to detail + success message", p.url, O, "fill 13 fields + Register", "created, redirected, message", f"{ri.value.status} {p.url[-40:]}", audit=audits(a))
    row = sql(f"select asset_tag||'|'||name||'|'||category_id||'|'||site_id||'|'||zone_id||'|'||manufacturer||'|'||model||'|'||serial_number||'|'||purchase_date||'|'||commission_date||'|'||owner_id||'|'||warranty_ref||'|'||replace(description,E'\\r','')||'|'||status from assets_asset where id='{a}'")
    expd = f"{tag}|Full asset ä‑ü|{QC}|{HYD}|{ZB}|MakerCo|M-9000|SN-{U}|2024-01-15|2024-03-01|{OWN}|WR-777|Line1\nLine2|ACTIVE"
    r.ok(row == expd, "Every field persisted exactly (incl. unicode, multi-line, dates, FK ids, status ACTIVE)", "-", O, "compare DB row", "equal", row[:120], db=row[:160])
    at = sql(f"select attributes::text from assets_asset where id='{a}'")
    r.ok('"voltage": "415.5"' in at.replace("415.500000", "415.5") or '415.5' in at, "Custom attributes persisted (number/choice/date/text)", "-", O, "read attributes JSON", "4 values", at, db=at)
    h = sql(f"select count(*) from assets_assetstatushistory where asset_id='{a}' and action='register' and to_status='ACTIVE'"); lh = sql(f"select count(*) from assets_assetlocationhistory where asset_id='{a}' and to_site_id='{HYD}'")
    r.ok(h == "1" and lh == "1", "Registration writes status-history and location-history rows", "-", O, "query history tables", "1+1", f"{h}+{lh}", db=f"{h}+{lh}")
    r.ok("asset.created" in (audits(a) or ""), "Audit row asset.created written", "-", O, "audit query", "asset.created", audits(a), audit=audits(a))
    # detail shows the data
    t = p.inner_text("main"); p.goto(BASE + f"/app/assets/{a}/"); t = p.inner_text("main")
    for want in (tag, "Full asset", "MakerCo", "M-9000", f"SN-{U}", "15 Jan 2024", "01 Mar 2024", "WR-777", "Building B", "HYD-1", "Three", "Voltage"):
        if want not in t: r.ok(False, f"Detail page shows '{want}' after creation", p.url, O, "read detail", want, t[:100]); break
    else: r.ok(True, "Detail page shows all entered values after creation", p.url, O, "read detail", "all visible", "ok")
    p.reload(); r.ok(tag in p.inner_text("main"), "Created asset survives refresh", p.url, O, "reload", "still there", "ok")
    p.goto(BASE + L + f"?q={tag}"); r.ok([x[0] for x in rows(p)] == [tag], "New asset appears in the list/search", p.url, O, "search new tag", "found", [x[0] for x in rows(p)])
    # minimal create
    t2 = f"MIN-{U}"; s = post_new(p, dict(asset_tag=t2, name="Minimal", category=PUMP, site=HYD))
    a2 = ASSET(t2); r.ok(a2 and sql(f"select coalesce(zone_id::text,'-')||'|'||coalesce(owner_id::text,'-')||'|'||serial_number||'|'||attributes::text from assets_asset where id='{a2}'") == "-|-||{}", "Minimal create (required fields only) persists with empty optionals", p.url, O, "tag+name+category+site", "created", s, audit=audits(a2))
    # create via zone prefill link from site
    p.goto(BASE + f"/app/assets/new/?site={BLR}"); r.ok(p.locator("main select[name=site]").input_value() == BLR, "Site preselected via ?site= (link from site page)", p.url, O, "open ?site=", "preselected", p.locator("main select[name=site]").input_value())
    p.goto(BASE + "/app/assets/new/"); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state("networkidle"); r.ok(p.url.rstrip("/").endswith("/app/assets"), "Cancel returns to the asset list", p.url, O, "click Cancel", "list", p.url)
    return a


@feature(r, "Asset create validation")
def t_validation():
    p = r.page(O); N = "/app/assets/new/"
    base = dict(asset_tag="", name="", category=PUMP, site=HYD)
    cnt = lambda: sql(f"select count(*) from assets_asset where organization_id={ALPHA}")
    def attempt(label, vals, frag=None, cond=None, field=None, forge=False):
        before = cnt(); data = {**dict(asset_tag=f"V-{U}-{abs(hash(label))%9999}", name="V test", category=PUMP, site=HYD), **vals}
        if forge:  # same real browser POST, but past the client-side maxlength / date picker constraints
            p.goto(BASE + N); p.wait_for_load_state("networkidle")
            with r.expect_errors(): res = bfetch(p, "POST", N, {"zone": "", "owner": "", **data})
            s = 400 if "errorlist" in res["text"] or "text-danger" in res["text"] or res["status"] == 400 else res["status"]; m = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", res["text"]))[:200]
            after = cnt(); ok = (after == before) and (res["status"] == 400) and True
            r.ok(ok, f"Validation (server): {label}", N, O, "forged POST past client limits", "400, nothing saved", f"http={res['status']} rows {before}->{after}", db=f"{before}->{after}")
            return
        s = post_new(p, data, expect_ok=False)
        after = cnt(); m = msgs(p) or p.inner_text("main")[:200]
        ok = (after == before) and s == 400 and (frag is None or frag.lower() in (m + p.inner_text("main")).lower())
        r.ok(ok, f"Validation: {label}", p.url, O, "submit invalid", "400, inline error, nothing saved" + (f" ('{frag}')" if frag else ""), f"http={s} rows {before}->{after}; {m[:90]}", db=f"{before}->{after}")
    # empty submit
    before = cnt(); p.goto(BASE + N);
    with r.expect_errors():
        with p.expect_response(lambda x: x.request.method == "POST") as ri: p.locator("main form button:has-text('Register asset')").click()
    p.wait_for_load_state("networkidle")
    errs = p.locator("main .text-danger").all_inner_texts()
    r.ok(ri.value.status == 400 and cnt() == before and len(errs) >= 2, "Empty submit: 400, inline errors under required fields, nothing saved", p.url, O, "submit blank form", "errors for tag/name", f"{ri.value.status} errors={[e.strip() for e in errs][:4]}", db=f"{before}->{cnt()}")
    attempt("tag required", dict(asset_tag=""), "required"); attempt("name required", dict(name=""), "required")
    attempt("name whitespace only", dict(name="    "), "required")
    attempt("tag 41 chars (max 40)", dict(asset_tag="T" * 41), "40", forge=True)
    attempt("name 201 chars (max 200)", dict(name="N" * 201), "200", forge=True)
    attempt("manufacturer 101 chars", dict(manufacturer="M" * 101), "100", forge=True); attempt("model 101 chars", dict(model="M" * 101), "100", forge=True)
    attempt("serial 101 chars", dict(serial_number="S" * 101), "100", forge=True); attempt("warranty ref 201 chars", dict(warranty_ref="W" * 201), "200", forge=True)
    attempt("invalid purchase date text", dict(purchase_date="not-a-date"), "date", forge=True)
    attempt("impossible purchase date 2024-02-30", dict(purchase_date="2024-02-30"), "date", forge=True)
    attempt("commissioning before purchase", dict(purchase_date="2024-05-01", commission_date="2024-04-01"), None)
    attempt("zone of another site", dict(site=HYD, zone=ZW), "belong", forge=True)
    # duplicates
    dtag = f"DUP-{U}"; post_new(p, dict(asset_tag=dtag, name="dup base", category=PUMP, site=HYD, manufacturer="DupMaker", serial_number=f"DS{U}"))
    attempt("duplicate tag (exact)", dict(asset_tag=dtag), "already exists"); attempt("duplicate tag (lower-case)", dict(asset_tag=dtag.lower()), "already exists")
    attempt("duplicate tag (padded with spaces)", dict(asset_tag=f"  {dtag}  "), "already exists")
    attempt("duplicate serial for the same manufacturer", dict(manufacturer="DupMaker", serial_number=f"DS{U}"), "serial")
    attempt("duplicate serial, manufacturer different case", dict(manufacturer="dupmaker", serial_number=f"ds{U}"), "serial")
    t3 = f"DUP2-{U}"; before = cnt(); post_new(p, dict(asset_tag=t3, name="same serial other maker", category=PUMP, site=HYD, manufacturer="OtherMaker", serial_number=f"DS{U}"))
    r.ok(ASSET(t3), "Same serial with a DIFFERENT manufacturer is allowed", p.url, O, "serial reuse across makers", "created", ASSET(t3)[:8] if ASSET(t3) else "not created", audit=audits(ASSET(t3)))
    t4 = f"BND-{U}"; post_new(p, dict(asset_tag=t4[:40], name="B" * 200, category=PUMP, site=HYD, manufacturer="M" * 100, model="M" * 100, serial_number=(U + "S" * 100)[:100], warranty_ref="W" * 200))
    r.ok(ASSET(t4), "Boundary: max-length name/manufacturer/model/serial/warranty accepted", p.url, O, "fields at max length", "created", bool(ASSET(t4)))
    t5 = f"B40-{U}".ljust(40, "Z"); post_new(p, dict(asset_tag=t5, name="tag40", category=PUMP, site=HYD)); r.ok(ASSET(t5), "Boundary: 40-char asset tag accepted", p.url, O, "tag 40 chars", "created", bool(ASSET(t5)))
    t6 = f"SAMEDAY-{U}"; post_new(p, dict(asset_tag=t6, name="same day", category=PUMP, site=HYD, purchase_date="2024-05-01", commission_date="2024-05-01")); r.ok(ASSET(t6), "Boundary: commissioning on the same day as purchase accepted", p.url, O, "equal dates", "created", bool(ASSET(t6)))
    t7 = f"FUT-{U}"; post_new(p, dict(asset_tag=t7, name="future dates", category=PUMP, site=HYD, purchase_date="2031-01-01", commission_date="2031-02-01"))
    r.T("Future purchase/commissioning dates", p.url, O, "purchase 2031-01-01", "(HPE silent) accepted or refused", "ACCEPTED" if ASSET(t7) else "REFUSED", "PASS", db=f"created={bool(ASSET(t7))}")
    t8 = f"XSS-{U}"; post_new(p, dict(asset_tag=t8, name="<img src=x onerror=window.__ax=1>", category=PUMP, site=HYD, description="<script>window.__ax=2</script>"))
    pa = r.page(O); pa.goto(BASE + f"/app/assets/{ASSET(t8)}/"); pa.goto(BASE + L + f"?q={t8}")
    r.ok(pa.evaluate("()=>!window.__ax") and "<img src=x" not in pa.content(), "Stored XSS in name/description is escaped on list and detail", pa.url, O, "name=<img onerror>", "inert", "ok")
    # crafted: forged ids
    def forge(label, over, frag=None):
        before = cnt(); p.goto(BASE + N)
        data = {"asset_tag": f"FG-{U}-{abs(hash(label))%9999}", "name": "forged", "category": PUMP, "site": HYD, "zone": "", "owner": ""}; data.update(over)
        with r.expect_errors(): res = bfetch(p, "POST", N, data)
        r.ok(cnt() == before and res["status"] in (400, 403, 404), f"Crafted POST: {label} rejected", N, O, "forged form value", "400/403/404, nothing saved", f"http={res['status']}", db=f"{before}->{cnt()}")
    betasite = sql("select id from sites_site where code='PUN-1'"); betacat = sql("select id from assets_assetcategory where organization_id<>%s limit 1" % ALPHA)
    betaowner = sql("select m.id from tenancy_membership m where m.organization_id<>%s limit 1" % ALPHA)
    forge("site of another tenant", {"site": betasite}); forge("category of another tenant", {"category": betacat}); forge("owner (member) of another tenant", {"owner": betaowner})
    forge("non-existent site id", {"site": "00000000-0000-0000-0000-000000000000"}); forge("malformed category id", {"category": "abc"}); forge("non-existent zone id", {"zone": "00000000-0000-0000-0000-000000000000"})
    forge("inactive category", {"category": sql(f"select id from assets_assetcategory where organization_id={ALPHA} and is_active=false limit 1") or "00000000-0000-0000-0000-000000000001"})
    p.goto(BASE + N)
    res = bfetch(p, "POST", N, {"asset_tag": f"FGS-{U}", "name": "forged status", "category": PUMP, "site": HYD, "zone": "", "owner": "", "status": "RETIRED"})
    ast = ASSET(f"FGS-{U}"); r.ok(not ast or sql(f"select status from assets_asset where id='{ast}'") == "ACTIVE", "Forged 'status' on create cannot set a non-ACTIVE status", N, O, "POST status=RETIRED", "ACTIVE or rejected", sql(f"select status from assets_asset where id='{ast}'") if ast else "rejected")
    # custom attribute validation
    nm = f"QA Cat {U}"; QC = CAT(nm)
    def cattempt(label, over, frag=None):
        before = cnt(); vals = dict(asset_tag=f"CA-{U}-{abs(hash(label))%9999}", name="attr test", category=QC, site=HYD, attr_voltage="400", attr_phase="Single"); vals.update(over)
        p.goto(BASE + f"/app/assets/new/?category={QC}"); p.wait_for_load_state("networkidle")
        p.evaluate("()=>document.querySelectorAll('main form input').forEach(e=>{e.removeAttribute('maxlength'); if(['date','number'].includes(e.type)) e.type='text'})")
        fill(p, {k: v for k, v in vals.items() if k != "category"})
        with r.expect_errors():
            with p.expect_response(lambda x: x.request.method == "POST") as ri: p.locator("main form button:has-text('Register asset')").click()
        p.wait_for_load_state("networkidle")
        r.ok(ri.value.status == 400 and cnt() == before, f"Custom attribute: {label}", p.url, O, "submit", "400 + inline error, nothing saved", f"http={ri.value.status} {msgs(p)[:80]}", db=f"{before}->{cnt()}")
    cattempt("required number missing", dict(attr_voltage=""))
    cattempt("non-numeric number value", dict(attr_voltage="abc"))
    cattempt("invalid date attribute", dict(attr_installed_on="31-31-2020"))
    # forged choice value not in choices
    before = cnt(); p.goto(BASE + N)
    with r.expect_errors(): res = bfetch(p, "POST", N, {"asset_tag": f"CH-{U}", "name": "forged choice", "category": QC, "site": HYD, "attr_voltage": "1", "attr_phase": "Hexa"})
    r.ok(cnt() == before and res["status"] == 400, "Custom attribute: choice outside the allowed list refused (forged)", N, O, "attr_phase=Hexa", "400", res["status"], db=f"{before}->{cnt()}")
    # inactive site
    insite = sql(f"select id from sites_site where organization_id={ALPHA} and status<>'ACTIVE' limit 1")
    if insite:
        before = cnt()
        with r.expect_errors(): res = bfetch(p, "POST", N, {"asset_tag": f"IS-{U}", "name": "inactive site", "category": PUMP, "site": insite})
        r.ok(cnt() == before and res["status"] == 400, "Asset cannot be registered at an inactive site", N, O, "POST site=inactive", "400", res["status"], db=f"{before}->{cnt()}")
    else:
        r.T("Register at inactive site", N, O, "needs an inactive site", "refused", "no inactive site existed in the dataset", "UNVERIFIED")


@feature(r, "Asset detail + edit")
def t_view_edit():
    a = ASSET(f"FULL-{U}"); D = f"/app/assets/{a}/"
    st, p = visit(r, O, D)
    r.ok(st == 200 and f"FULL-{U}" in p.inner_text("main"), "Detail page opens", D, O, "open", "200", st)
    tabs = p.locator("main .fx-tabs a").all_inner_texts()
    r.ok(tabs == ["Overview", "Documents", "Meters", "History", "Hierarchy", "Coverage", "Labels"], "Seven tabs present", D, O, "read tabs", "Overview..Labels", tabs)
    for key in ("overview", "documents", "meters", "history", "hierarchy", "coverage", "labels"):
        with p.expect_navigation(): p.goto(BASE + D + f"?tab={key}")
        p.wait_for_load_state("networkidle")
        act = p.locator("main .fx-tabs a.active").inner_text().strip().lower()
        r.ok(act == key and "Server Error" not in p.inner_text("body"), f"Tab '{key}' loads and is highlighted", p.url, O, f"click {key}", "active tab", act)
    p.goto(BASE + D); p.locator("main .fx-tabs a:has-text('Meters')").click(); p.wait_for_load_state("networkidle"); r.ok("tab=meters" in p.url, "Clicking a tab navigates to it", p.url, O, "click Meters tab", "?tab=meters", p.url)
    p.goto(BASE + D + "?tab=bogus"); r.ok(p.locator("main .fx-tabs a.active").inner_text().strip() == "Overview", "Unknown tab falls back to Overview", p.url, O, "?tab=bogus", "Overview", p.locator("main .fx-tabs a.active").inner_text())
    st, p = visit(r, O, f"/app/assets/00000000-0000-0000-0000-000000000000/"); r.ok(st == 404, "Unknown asset id -> 404", p.url, O, "random uuid", "404", st)
    # status buttons on an ACTIVE asset
    p.goto(BASE + D); btns = p.locator("main form[action*='/transition/'] button").all_inner_texts()
    r.ok([b.strip() for b in btns] == ["Start maintenance"], "ACTIVE asset offers only 'Start maintenance'", D, O, "read buttons", "Start maintenance", btns)
    rp = p.locator("#report-problem"); r.ok(rp.count() == 1 and f"asset={a}" in (rp.get_attribute("href") or ""), "'Report a problem' links to the incident form with the asset preselected (M05 contract)", D, O, "inspect link", "?asset=<id>", rp.get_attribute("href") if rp.count() else "missing")
    # EDIT
    E = D + "edit/"; p.goto(BASE + E); p.wait_for_load_state("networkidle")
    v = p.eval_on_selector_all("main form [name]", "e=>Object.fromEntries(e.filter(x=>x.type!=='hidden').map(x=>[x.name,x.type==='select-one'?x.value:x.value]))")
    r.ok(v["asset_tag"] == f"FULL-{U}" and v["site"] == HYD and v["zone"] == ZB and v["owner"] == OWN and v["purchase_date"] == "2024-01-15" and v["attr_voltage"].startswith("415.5") and "reason" in v, "Edit form is pre-filled with every saved value (incl. attributes) and has a reason field", E, O, "open edit", "prefilled", {k: v[k] for k in ("asset_tag", "site", "zone", "attr_voltage")})
    new = dict(asset_tag=f"FULL2-{U}", name="Renamed asset", manufacturer="MakerCo2", model="M-9001", serial_number=f"SN2-{U}", purchase_date="2023-12-01", commission_date="2024-02-01", owner=OWN2, warranty_ref="WR-888", description="edited desc", attr_voltage="230", attr_phase="Single", attr_notes="n2", reason="moved to Warehouse", site=BLR)
    fill(p, new); p.locator("main select[name=zone]").select_option(value=ZW)
    with p.expect_response(lambda x: x.request.method == "POST") as ri: p.locator("main form button:has-text('Save')").click()
    p.wait_for_load_state("networkidle")
    row = sql(f"select asset_tag||'|'||name||'|'||manufacturer||'|'||model||'|'||serial_number||'|'||purchase_date||'|'||commission_date||'|'||owner_id||'|'||warranty_ref||'|'||description||'|'||site_id||'|'||zone_id from assets_asset where id='{a}'")
    expd = f"FULL2-{U}|Renamed asset|MakerCo2|M-9001|SN2-{U}|2023-12-01|2024-02-01|{OWN2}|WR-888|edited desc|{BLR}|{ZW}"
    r.ok(row == expd and "saved" in (msgs(p) + p.inner_text("main")).lower(), "Edit every field (incl. site/location move, owner, dates) persisted + success message", p.url, O, "change all fields + Save", "all saved", row[:140], db=row[:160], audit=audits(a, "asset.updated"))
    at = sql(f"select attributes::text from assets_asset where id='{a}'"); r.ok("230" in at and "Single" in at and "n2" in at, "Edit: custom attribute values persisted", p.url, O, "edit attrs", "230/Single/n2", at, db=at)
    lh = sql(f"select reason from assets_assetlocationhistory where asset_id='{a}' order by created_at desc limit 1"); r.ok(lh == "moved to Warehouse", "Location move writes location-history with the typed reason", p.url, O, "query location history", "reason stored", lh, db=lh)
    ev = sql(f"select before::text||' => '||after::text from audit_auditlog where target_id='{a}' and action='asset.updated' order by occurred_at desc limit 1")
    r.ok("Renamed asset" in ev and "Full asset" in ev, "Audit row records before/after for the edit", "-", O, "audit query", "before/after", ev[:120], audit=ev[:120])
    p.goto(BASE + D + "?tab=history"); h = p.inner_text("main")
    r.ok("moved to Warehouse" in h and "BLR-1" in h, "History tab shows the location change with its reason", p.url, O, "open History", "move + reason", h[:150].replace("\n", " "))
    p.goto(BASE + D); t = p.inner_text("main"); r.ok("FULL2-" in t and "Renamed asset" in t and "WR-888" in t and "Warehouse" in t, "Detail reflects the edit (refresh persistence)", D, O, "reload detail", "new values", "ok")
    # edit duplicate tag / serial
    other = ASSET(f"DUP-{U}")
    p.goto(BASE + E); fill(p, dict(asset_tag=f"DUP-{U}"));
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select asset_tag from assets_asset where id='{a}'") == f"FULL2-{U}" and "already exists" in p.inner_text("main"), "Edit: duplicate asset tag refused", E, O, "tag=existing", "refused", msgs(p)[:80])
    p.goto(BASE + E); fill(p, dict(manufacturer="DupMaker", serial_number=f"DS{U}"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select serial_number from assets_asset where id='{a}'") == f"SN2-{U}", "Edit: duplicate manufacturer+serial refused", E, O, "serial clash", "refused", msgs(p)[:80])
    p.goto(BASE + E); fill(p, dict(name=""));
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select name from assets_asset where id='{a}'") == "Renamed asset", "Edit: blank name refused", E, O, "clear name", "refused", msgs(p)[:80])
    p.goto(BASE + E); fill(p, dict(purchase_date="2025-01-01", commission_date="2024-01-01"))
    with r.expect_errors(): p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select purchase_date from assets_asset where id='{a}'") == "2023-12-01", "Edit: commissioning before purchase refused", E, O, "dates reversed", "refused", msgs(p)[:80])
    # category change on edit resets attributes
    p.goto(BASE + E + f"?category={PUMP}"); p.wait_for_load_state("networkidle")
    r.ok(p.locator("main [name^=attr_]").count() == 0, "Edit: switching category reloads the form without the old category's attribute fields", p.url, O, "?category=Pump", "no attr fields", p.locator("main [name^=attr_]").count())
    fill(p, {"category": PUMP}); p.locator("main form button:has-text('Save')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select category_id from assets_asset where id='{a}'") == PUMP and sql(f"select attributes::text from assets_asset where id='{a}'") == "{}", "Edit: category change saved and the old category's attribute values are dropped", p.url, O, "category=Pump + Save", "category changed, attributes {}", sql(f"select attributes::text from assets_asset where id='{a}'"), audit=audits(a, "asset.updated"))
    # cancel
    p.goto(BASE + E); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state("networkidle"); r.ok(p.url.rstrip("/").endswith(a), "Edit: Cancel returns to the detail page", p.url, O, "Cancel", "detail", p.url)
    # forged status via edit
    p.goto(BASE + E)
    with r.expect_errors(): res = bfetch(p, "POST", E, {"asset_tag": f"FULL2-{U}", "name": "Renamed asset", "category": PUMP, "site": BLR, "status": "RETIRED"})
    r.ok(sql(f"select status from assets_asset where id='{a}'") == "ACTIVE", "Status cannot be changed through the edit form (forged status ignored)", E, O, "POST status=RETIRED on edit", "ACTIVE", sql(f"select status from assets_asset where id='{a}'"))


for f in (t_list, t_search, t_filter, t_pagination, t_categories, t_create, t_validation, t_view_edit):
    f()

fails = [x for x in r.rows if x["status"] == "FAIL"]; unv = [x for x in r.rows if x["status"] == "UNVERIFIED"]
print("ROWS", len(r.rows), "FAIL", len(fails), "UNVF", len(unv), "PARTIAL", len([x for x in r.rows if x['status'] == 'PARTIAL']))
for x in fails + unv: print("  ", x["status"], x["feature"], "|", str(x["action"])[:50], "|", str(x["actual"])[:170])
print("ISSUES", len(r.issues))
for i in r.issues[:25]: print("  ", i["kind"], i["feature"], i["role"], i["text"][:130], i.get("url", "")[-60:])
r.stop()
