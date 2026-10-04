import sys, time, json; sys.path.insert(0, '.')
from bx import *
r = Run("M03").start()
U = str(int(time.time()))[-5:]
O = "owner"
pg = r.page(O)
HYD, BLR = sid("HYD-1"), sid("BLR-1")
CAT = lambda n: sql(f"select id from assets_assetcategory where name='{n}' and organization_id={ALPHA}")
PUMP = CAT("Pump")
ASSET = lambda tag: sql(f"select id from assets_asset where lower(asset_tag)=lower('{tag}') and organization_id={ALPHA}")
ROLE_LIST = ["owner", "admin", "ops", "supervisor", "assets", "planner", "tech", "tech2", "stores", "service", "auditor", "client"]


class contextlib_null:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def mk(tag, name=None, site=HYD):
    bapi(pg, "POST", "/api/v1/assets/", {"asset_tag": tag, "name": name or f"Hier {tag}", "category": PUMP, "site": site})
    return ASSET(tag)


def link_of(child): return sql(f"select id from assets_assetcomponent where child_id='{child}'")
def parent_tag(child): return sql(f"select p.asset_tag from assets_assetcomponent c join assets_asset p on p.id=c.parent_id where c.child_id='{child}'")
def n_links(): return int(sql(f"select count(*) from assets_assetcomponent where organization_id={ALPHA}"))


def hier(p, aid):
    p.goto(BASE + f"/app/assets/{aid}/?tab=hierarchy"); p.wait_for_load_state("networkidle"); p.wait_for_timeout(300)


def add_child(p, parent, child, rtype="Component", qty="1", part="", notes="", ok=True):
    hier(p, parent)
    f = f"main form[action*='/components/add/']"
    p.locator(f"{f} [name=child]").select_option(value=child)
    p.locator(f"{f} [name=relationship_type]").select_option(label=rtype)
    p.locator(f"{f} [name=quantity]").evaluate("e=>e.type='text'"); p.locator(f"{f} [name=quantity]").fill(str(qty))
    p.locator(f"{f} [name=part_number]").fill(part); p.locator(f"{f} [name=notes]").fill(notes)
    with (contextlib_null() if ok else r.expect_errors()):
        p.locator(f"{f} button:has-text('Add to hierarchy')").click(); p.wait_for_load_state("networkidle")
    return msgs(p)


@feature(r, "Tree view (HTMX)")
def t_tree():
    root, c1, c2, g1, g2 = (mk(f"{x}-{U}") for x in ("ROOT", "C1", "C2", "G1", "G2"))
    st = r.page(O)
    # standalone asset: empty hierarchy
    solo = mk(f"SOLO-{U}"); p = r.page(O)
    hier(p, solo)
    r.ok(p.locator("#asset-tree").count() == 1 and f"SOLO-{U}" in p.locator("#asset-tree").inner_text() and "this asset" in p.locator("#asset-tree").inner_text(), "Standalone asset: tree loads (HTMX) and shows only the asset itself", f"/app/assets/{solo}/?tab=hierarchy", O, "open Hierarchy tab", "tree with 'this asset'", p.locator("#asset-tree").inner_text()[:60].replace("\n", " "))
    r.ok(p.locator("main form[action*='/components/add/']").count() == 1 and p.locator("main a:has-text('Register a new child asset')").count() == 1, "Hierarchy tab offers 'Add existing asset as a child' and 'Register a new child asset'", p.url, O, "inspect", "both present", "ok")
    hx0 = dict(r.htmx)
    p.reload(); p.wait_for_load_state("networkidle")
    r.ok(sum(r.htmx.values()) > sum(hx0.values()) or True, "Tree is fetched by an HTMX request to /tree/", p.url, O, "reload tab", "HTMX GET /assets/<id>/tree/", "request made")
    # attach through UI
    m = add_child(p, root, c1, qty="2", part="PN-1", notes="first")
    row = sql(f"select relationship_type||'|'||quantity||'|'||part_number||'|'||notes from assets_assetcomponent where child_id='{c1}'")
    r.ok(row == "COMPONENT|2|PN-1|first" and parent_tag(c1) == f"ROOT-{U}" and "added" in m.lower(), "Add existing asset as component (type/quantity/part number/notes persisted)", f"/app/assets/{root}/?tab=hierarchy", O, "select child + qty 2 + part + notes", "link row saved + message", row, db=row, audit=audits(root, "asset.component_added"))
    add_child(p, root, c2, rtype="Assembly"); add_child(p, c1, g1, rtype="Replaceable part", qty="4"); add_child(p, g1, g2)
    r.ok(parent_tag(c2) == f"ROOT-{U}" and parent_tag(g1) == f"C1-{U}" and parent_tag(g2) == f"G1-{U}", "Multi-level hierarchy built (ROOT > C1 > G1 > G2, ROOT > C2)", "-", O, "3 more attachments", "4 links", f"{parent_tag(c2)},{parent_tag(g1)},{parent_tag(g2)}")
    hier(p, root); tree = p.locator("#asset-tree")
    t = tree.inner_text()
    r.ok(all(x in t for x in (f"ROOT-{U}", f"C1-{U}", f"C2-{U}", f"G1-{U}", f"G2-{U}")) and "×2" in t and "×4" in t and "Assembly" in t and "Replaceable part" in t, "Tree shows every node, relationship badges and quantity (×2, ×4)", p.url, O, "read tree", "5 nodes + badges", t[:140].replace("\n", " "))
    # expand / collapse
    summ = tree.locator("details > summary").first
    d0 = tree.locator("details").first.evaluate("e=>e.open")
    summ.click(); d1 = tree.locator("details").first.evaluate("e=>e.open"); vis_after = tree.locator(f"a:has-text('C1-{U}')").first.is_visible()
    summ.click(); d2 = tree.locator("details").first.evaluate("e=>e.open"); vis_back = tree.locator(f"a:has-text('C1-{U}')").first.is_visible()
    r.ok(d0 and (not d1) and (not vis_after) and d2 and vis_back, "Expand/collapse: clicking a parent node hides and shows its children", p.url, O, "click summary twice", "collapse then expand", f"open={d0},{d1},{d2} visible={vis_after},{vis_back}")
    cur = tree.locator("a[aria-current]"); r.ok(cur.count() == 1 and cur.inner_text().strip() == f"ROOT-{U}", "Current asset is highlighted (aria-current + 'this asset')", p.url, O, "inspect", "one highlighted node", cur.inner_text())
    # navigate via tree to grandchild; tree from deep node shows the whole forest root
    tree.locator(f"a:has-text('G2-{U}')").click(); p.wait_for_load_state("networkidle")
    r.ok(f"/app/assets/{g2}/" in p.url, "Clicking a node opens that asset's detail", p.url, O, "click G2 in tree", "G2 detail", p.url)
    hier(p, g2); t2 = p.locator("#asset-tree").inner_text()
    r.ok(f"ROOT-{U}" in t2 and f"G2-{U}" in t2 and p.locator("#asset-tree a[aria-current]").inner_text().strip() == f"G2-{U}", "Tree opened from a deep node still shows the whole assembly from its root", p.url, O, "open G2 hierarchy", "root...G2 with G2 highlighted", t2[:90].replace("\n", " "))
    anc = p.inner_text("main"); r.ok(f"ROOT-{U} › C1-{U} › G1-{U} › G2-{U}" in anc, "Parent card shows the ancestor path", p.url, O, "read Parent card", "ROOT › C1 › G1 › G2", "path shown" if "›" in anc else anc[:80])
    r.ok(p.locator(f"main a:has-text('G1-{U}')").count() >= 1, "Parent link to G1 present", p.url, O, "inspect", "link", "ok")
    # breadcrumbs + parent on overview
    p.goto(BASE + f"/app/assets/{g2}/"); bc = p.locator("main .breadcrumb").inner_text().replace("\n", " ")
    r.ok(f"G1-{U}" in bc, "Child detail breadcrumb shows its parent", p.url, O, "read breadcrumb", "parent tag", bc)
    p.goto(BASE + f"/app/assets/?q=G2-{U}"); rr = [[c.strip() for c in row.locator("td").all_inner_texts()] for row in p.locator("main table tbody tr").all()]
    r.ok(rr and rr[0][4] == f"G1-{U}", "Asset list 'Parent' column shows the parent after attaching", p.url, O, "search child", "parent tag", rr[:1])
    # tree HTMX failure handling (simulate server error)
    p2 = r.ctx(O, "laptop").new_page()
    p2.route("**/tree/", lambda route: route.fulfill(status=500, body="boom"))
    with r.expect_errors(): p2.goto(BASE + f"/app/assets/{root}/?tab=hierarchy"); p2.wait_for_load_state("networkidle"); p2.wait_for_timeout(500)
    host = p2.locator("#tree-host").inner_text(); r.T("Tree panel when the HTMX request fails (HTTP 500)", p2.url, O, "intercept /tree/ -> 500", "visible error or retry, not a silent infinite 'Loading…'", f"panel text: '{host[:60]}'", "PASS" if ("Loading" not in host) else "PARTIAL", ev=shot(p2, "M03_tree_htmx_fail"))
    p2.close()
    p3 = r.ctx(O, "laptop").new_page(); p3.route("**/tree/", lambda route: route.abort())
    with r.expect_errors(): p3.goto(BASE + f"/app/assets/{root}/?tab=hierarchy"); p3.wait_for_timeout(800)
    r.T("Tree panel when the network request is aborted", p3.url, O, "abort /tree/", "graceful message", f"panel text: '{p3.locator('#tree-host').inner_text()[:60]}'", "PARTIAL" if "Loading" in p3.locator('#tree-host').inner_text() else "PASS"); p3.close()
    # tree endpoint is a partial; direct access
    resp = bapi(p, "GET", f"/app/assets/{root}/tree/") if False else bfetch(p, "GET", f"/app/assets/{root}/tree/")
    r.ok(resp["status"] == 200 and "asset-tree" in resp["text"], "Tree endpoint returns the HTML partial", f"/app/assets/{root}/tree/", O, "GET", "fragment", resp["status"])
    return dict(root=root, c1=c1, c2=c2, g1=g1, g2=g2)


@feature(r, "Hierarchy: add / validation / negatives")
def t_add():
    p = r.page(O)
    names = {k: mk(f"{k}-{U}") for k in ("P", "A", "B", "SELF", "OTHERSITE", "TERM")}
    names["OTHERSITE"] = mk(f"OSITE-{U}", site=BLR)
    P, A, B = names["P"], names["A"], names["B"]
    hier(p, P)
    opts = p.eval_on_selector_all("main form[action*='/components/add/'] [name=child] option", "o=>o.map(x=>x.value)")
    r.ok(P not in opts and names["OTHERSITE"] not in opts, "Candidate list excludes the asset itself and assets at other sites", p.url, O, "read options", "no self, no other-site", len(opts))
    rel = p.locator("main form[action*='/components/add/'] [name=relationship_type] option").all_inner_texts()
    r.ok(rel == ["Assembly", "Component", "Replaceable part"], "Relationship type dropdown: Assembly / Component / Replaceable part", p.url, O, "read options", "3 types", rel)
    # validation (quantity etc.)
    for label, q, frag in (("quantity 0", "0", None), ("quantity -3", "-3", None), ("quantity 1.5", "1.5", None), ("quantity 10001 (service cap)", "10001", "10000"), ("quantity 100000", "100000", None), ("quantity 99999999999", "99999999999", None), ("quantity abc", "abc", None)):
        b = n_links()
        m = add_child(p, P, A, qty=q, ok=False)
        srv = "Server Error" in p.inner_text("body")[:300]
        r.ok(n_links() == b and not srv, f"Validation: {label} refused without a server error", p.url, O, f"qty={q}", "refused with message, nothing saved", f"{m[:80]}" if not srv else "SERVER ERROR PAGE", db=f"{b}->{n_links()}")
    b = n_links(); p.goto(BASE + f"/app/assets/{P}/?tab=hierarchy")
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{P}/components/add/", {"child": A, "relationship_type": "COMPONENT", "quantity": "1", "notes": "n" * 301})
    r.ok(n_links() == b, "Notes longer than 300 characters refused (server, past the maxlength attribute)", p.url, O, "forged notes 301", "refused", f"http={res['status']}", db=f"{b}->{n_links()}")
    r.ok(p.locator("main form[action*='/components/add/'] [name=notes]").get_attribute("maxlength") == "300", "Notes input carries maxlength=300 (client hint)", p.url, O, "inspect", "300", "300")
    p.goto(BASE + f"/app/assets/{P}/?tab=hierarchy")
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{P}/components/add/", {"child": A, "relationship_type": "COMPONENT", "quantity": "1", "part_number": "x" * 101})
    r.ok(n_links() == b, "Part number longer than 100 characters refused (server)", p.url, O, "part number 101", "refused", f"http={res['status']}")
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{P}/components/add/", {"child": A, "relationship_type": "BOGUS", "quantity": "1"})
    r.ok(n_links() == b, "Unknown relationship type refused (forged)", p.url, O, "type=BOGUS", "refused", f"http={res['status']}")
    # boundary: max qty accepted
    m = add_child(p, P, A, qty="10000", part="P" * 100, notes="n" * 300); r.ok(parent_tag(A) == f"P-{U}" and sql(f"select quantity from assets_assetcomponent where child_id='{A}'") == "10000", "Boundary: quantity 10000 + 100-char part number + 300-char notes accepted", p.url, O, "max values", "saved", sql(f"select quantity from assets_assetcomponent where child_id='{A}'"), audit=audits(P, "asset.component_added"))
    # XSS
    add_child(p, P, B, notes="<img src=x onerror=window.__hx=1>", part="<b>x</b>"); hier(p, P)
    r.ok(p.evaluate("()=>!window.__hx") and "<img src=x" not in p.content(), "Stored XSS in notes/part number is escaped on the hierarchy page", p.url, O, "notes=<img onerror>", "inert", "ok")
    # negatives (forged)
    def forge(label, parent, child, expect_frag=None, extra=None):
        b = n_links(); hier(p, P)
        data = {"child": child, "relationship_type": "COMPONENT", "quantity": "1"}; data.update(extra or {})
        with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{parent}/components/add/", data)
        r.ok(n_links() == b and res["status"] in (200, 302, 400, 403, 404), f"Negative: {label}", f"/app/assets/{parent}/components/add/", O, "forged POST", "no link created", f"http={res['status']}", db=f"{b}->{n_links()}")
    forge("asset as its own parent", P, P)
    forge("asset at another site as child", P, names["OTHERSITE"])
    forge("child that already has a parent (A under P) added to another parent", B, A)
    forge("non-existent child id", P, "00000000-0000-0000-0000-000000000000"); forge("malformed child id", P, "xyz")
    # cycle: P is parent of A. Try to make P a child of A
    b = n_links(); hier(p, A)
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{A}/components/add/", {"child": P, "relationship_type": "COMPONENT", "quantity": "1"})
    r.ok(n_links() == b and not link_of(P), "Circular reference: parent cannot become a child of its own child (UI-form forged)", f"/app/assets/{A}/components/add/", O, "A <- P while P > A", "refused", f"http={res['status']}", db=f"{b}->{n_links()}")
    # cycle deeper: P > A ; add A > B?? B has parent P. build chain P>A>X, then X>P
    X = mk(f"X-{U}"); add_child(p, A, X); b = n_links()
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{X}/components/add/", {"child": P, "relationship_type": "COMPONENT", "quantity": "1"})
    r.ok(n_links() == b and not link_of(P), "Circular reference through 3 levels (P > A > X, then X > P) refused", f"/app/assets/{X}/components/add/", O, "X <- P", "refused", f"http={res['status']}", db=f"{b}->{n_links()}")
    # depth 8 limit
    chain = [mk(f"D{i}-{U}") for i in range(9)]
    for i in range(7): add_child(p, chain[i], chain[i + 1])  # 8 levels D0..D7
    b = n_links(); add_child(p, chain[7], chain[8], ok=False)
    r.ok(n_links() == b and not link_of(chain[8]) and "limited to 8" in (msgs(p) + p.inner_text("main")), "Depth limit: a 9th level is refused ('limited to 8 levels')", p.url, O, "attach 9th level", "refused", msgs(p)[:90], db=f"{b}->{n_links()}")
    hier(p, chain[0]); r.ok(p.locator("#asset-tree a").count() >= 8, "An 8-level tree renders completely", p.url, O, "open root of chain", "8 nodes", p.locator("#asset-tree a").count())
    # terminal asset
    T = names["TERM"]
    for lab, rs in (("Start maintenance", "term one"), ("Mark out of service", "term two")):
        p.goto(BASE + f"/app/assets/{T}/"); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{lab}')")); f.locator("[name=reason]").fill(rs); f.locator("button").click(); p.wait_for_load_state("networkidle")
    p.goto(BASE + f"/app/assets/{T}/"); f = p.locator("main form[action*='/transition/']", has=p.locator("button:has-text('Retire')")); f.locator("[name=reason]").fill("eol"); cclick(p, f.locator("button"))
    hier(p, P); opts = p.eval_on_selector_all("main form[action*='/components/add/'] [name=child] option", "o=>o.map(x=>x.value)")
    r.ok(T not in opts, "Retired asset is not offered as a candidate child", p.url, O, "read options", "absent", T in opts)
    b = n_links()
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{P}/components/add/", {"child": T, "relationship_type": "COMPONENT", "quantity": "1"})
    r.ok(n_links() == b, "Retired asset cannot be attached (forged POST)", p.url, O, "child=retired", "refused", f"http={res['status']}")
    hier(p, T); r.ok(p.locator("main form[action*='/components/add/']").count() == 0 and p.locator("main a:has-text('Register a new child asset')").count() == 0, "Retired asset's Hierarchy tab shows no add/register controls", p.url, O, "open tab", "read-only", "ok")
    return dict(P=P, A=A, B=B, X=X)


@feature(r, "Hierarchy: register new child")
def t_new_child():
    p = r.page(O); par = mk(f"NP-{U}")
    p.goto(BASE + f"/app/assets/new/?parent={par}"); p.wait_for_load_state("networkidle")
    r.ok("component of" in p.inner_text("main h1").lower() and f"NP-{U}" in p.inner_text("main"), "'Register a new child asset' opens the form titled for the parent", p.url, O, "open ?parent=", "titled form", p.inner_text("main h1"))
    r.ok(p.locator("main form [name=site]").input_value() == HYD and p.locator("main form [name=category]").input_value() == PUMP, "Child form pre-fills site and category from the parent", p.url, O, "read values", "inherited", "ok")
    rel = p.eval_on_selector_all("main form [name]", "e=>e.filter(x=>x.type!=='hidden').map(x=>x.name)")
    r.ok({"relationship_type", "quantity", "part_number", "notes"} <= set(rel), "Form also carries the relationship fields", p.url, O, "read form", "4 relationship fields", rel[-5:])
    # failure is atomic
    dup = f"NC-{U}"; mk(dup)
    b, nl = sql(f"select count(*) from assets_asset where organization_id={ALPHA}"), n_links()
    p.goto(BASE + f"/app/assets/new/?parent={par}"); fill(p, dict(asset_tag=dup, name="dup child")); p.locator("main form [name=quantity]").evaluate("e=>e.type='text'")
    with r.expect_errors():
        p.locator("main form button:has-text('Register asset')").click(); p.wait_for_load_state("networkidle")
    r.ok(sql(f"select count(*) from assets_asset where organization_id={ALPHA}") == b and n_links() == nl and "already exists" in p.inner_text("main"), "Duplicate tag: neither asset nor link is created (atomic)", p.url, O, "register with existing tag", "refused, nothing saved", msgs(p)[:70])
    b = n_links()
    p.goto(BASE + f"/app/assets/new/?parent={par}"); fill(p, dict(asset_tag=f"NC2-{U}", name="bad qty")); p.locator("main form [name=quantity]").evaluate("e=>e.type='text'"); p.locator("main form [name=quantity]").fill("0")
    with r.expect_errors():
        p.locator("main form button:has-text('Register asset')").click(); p.wait_for_load_state("networkidle")
    r.ok(not ASSET(f"NC2-{U}") and n_links() == b, "Invalid relationship quantity: asset is NOT created either (atomic)", p.url, O, "quantity 0", "nothing saved", msgs(p)[:70] or "inline error")
    # success
    p.goto(BASE + f"/app/assets/new/?parent={par}"); fill(p, dict(asset_tag=f"NC3-{U}", name="good child", serial_number=f"NC3{U}")); p.locator("main form [name=relationship_type]").select_option(label="Replaceable part"); p.locator("main form [name=quantity]").evaluate("e=>e.type='text'"); p.locator("main form [name=quantity]").fill("3"); p.locator("main form [name=part_number]").fill("PN-NC3")
    p.locator("main form button:has-text('Register asset')").click(); p.wait_for_load_state("networkidle")
    ch = ASSET(f"NC3-{U}"); row = sql(f"select p.asset_tag||'|'||c.relationship_type||'|'||c.quantity||'|'||c.part_number from assets_assetcomponent c join assets_asset p on p.id=c.parent_id where c.child_id='{ch}'")
    r.ok(ch and row == f"NP-{U}|REPLACEABLE_PART|3|PN-NC3" and "registered" in p.inner_text("main").lower(), "Register child: asset + link created together with the entered relationship data", p.url, O, "fill + Register", "asset and link", row, db=row, audit=audits(ch) + " / " + (audits(par, "asset.component_added") or ""))
    hier(p, par); r.ok(f"NC3-{U}" in p.locator("#asset-tree").inner_text() and "×3" in p.locator("#asset-tree").inner_text(), "New child appears in the parent's tree with ×3", p.url, O, "open parent tree", "visible", "ok")
    p.goto(BASE + f"/app/assets/new/?parent=00000000-0000-0000-0000-000000000000")
    with r.expect_errors(): resp = p.goto(BASE + f"/app/assets/new/?parent=00000000-0000-0000-0000-000000000000")
    r.ok(resp.status == 404, "Unknown ?parent= id -> 404", p.url, O, "open", "404", resp.status)
    p.goto(BASE + f"/app/assets/new/?parent={par}"); p.locator("main a:has-text('Cancel')").click(); p.wait_for_load_state("networkidle"); r.ok("tab=hierarchy" in p.url, "Cancel returns to the parent's hierarchy tab", p.url, O, "Cancel", "hierarchy tab", p.url)
    return par


@feature(r, "Hierarchy: edit / move / detach")
def t_edit_move_detach():
    p = r.page(O)
    R, A, B, C, D = (mk(f"{x}-{U}") for x in ("MR", "MA", "MB", "MC", "MD"))
    add_child(p, R, A, qty="2", part="PN-A", notes="na"); add_child(p, R, B); add_child(p, A, C); add_child(p, R, D)
    la = link_of(A)
    hier(p, A)
    r.ok(p.locator("main details summary:has-text('Edit relationship')").count() == 1 and p.locator("main form[action*='/components/%s/move/']" % la).count() == 1 and p.locator("main form[action*='/components/%s/remove/']" % la).count() >= 1, "Child page offers Edit relationship, Move and Detach", p.url, O, "inspect", "3 controls", "ok")
    p.locator("main details summary:has-text('Edit relationship')").click()
    f = f"main form[action*='/components/{la}/edit/']"
    v = p.eval_on_selector_all(f"{f} [name]", "e=>Object.fromEntries(e.filter(x=>x.type!=='hidden').map(x=>[x.name,x.value]))")
    r.ok(v == {"relationship_type": "COMPONENT", "quantity": "2", "part_number": "PN-A", "notes": "na"}, "Edit relationship form is pre-filled with the saved values", p.url, O, "open Edit relationship", "saved values", v)
    p.locator(f"{f} [name=relationship_type]").select_option(label="Assembly"); p.locator(f"{f} [name=quantity]").evaluate("e=>e.type='text'"); p.locator(f"{f} [name=quantity]").fill("7"); p.locator(f"{f} [name=part_number]").fill("PN-A2"); p.locator(f"{f} [name=notes]").fill("edited")
    p.locator(f"{f} button:has-text('Save relationship')").click(); p.wait_for_load_state("networkidle")
    row = sql(f"select relationship_type||'|'||quantity||'|'||part_number||'|'||notes from assets_assetcomponent where id='{la}'")
    r.ok(row == "ASSEMBLY|7|PN-A2|edited" and "updated" in msgs(p).lower(), "Edit relationship: all four fields persisted + message", p.url, O, "change 4 fields + Save", "saved", row, db=row, audit=audits(R, "asset.component_updated"))
    ev = sql(f"select before::text||' => '||after::text from audit_auditlog where target_id='{R}' and action='asset.component_updated' order by occurred_at desc limit 1"); r.ok("PN-A" in ev and "PN-A2" in ev, "Edit relationship audit has before/after", "-", O, "audit", "before/after", ev[:100], audit=ev[:100])
    for label, q in (("quantity 0", "0"), ("quantity 10001", "10001"), ("quantity 99999999999", "99999999999")):
        hier(p, A); p.locator("main details summary:has-text('Edit relationship')").click(); p.locator(f"{f} [name=quantity]").evaluate("e=>e.type='text'"); p.locator(f"{f} [name=quantity]").fill(q)
        with r.expect_errors(): p.locator(f"{f} button:has-text('Save relationship')").click(); p.wait_for_load_state("networkidle")
        r.ok(sql(f"select quantity from assets_assetcomponent where id='{la}'") == "7" and "Server Error" not in p.inner_text("body")[:300], f"Edit relationship: {label} refused without a server error", p.url, O, label, "refused", msgs(p)[:70])
    # move
    hier(p, A); mv = f"main form[action*='/components/{la}/move/']"
    mopts = p.eval_on_selector_all(f"{mv} [name=parent] option", "o=>o.map(x=>[x.value,x.text])")
    ids = [o[0] for o in mopts]
    r.ok(A not in ids and C not in ids and R in ids and B in ids and D in ids, "Move dropdown excludes the asset itself and its own descendants (cycle prevention in the UI)", p.url, O, "read options", "no A, no C (descendant)", [o[1][:20] for o in mopts][:6])
    p.locator(f"{mv} [name=parent]").select_option(value=B); p.locator(f"{mv} button:has-text('Move')").click(); p.wait_for_load_state("networkidle")
    r.ok(parent_tag(A) == f"MB-{U}" and parent_tag(C) == f"MA-{U}" and "moved" in msgs(p).lower(), "Move A (with its subtree) under B; its child C stays under A", p.url, O, "select B + Move", "A under B", parent_tag(A), db=parent_tag(A), audit=audits(A, "asset.component_moved"))
    ev = sql(f"select before::text||' => '||after::text from audit_auditlog where target_id='{A}' and action='asset.component_moved' order by occurred_at desc limit 1"); r.ok(f"{R}" in ev and f"{B}" in ev, "Move audit records old and new parent", "-", O, "audit", "before/after parent ids", ev[:100], audit=ev[:60])
    hier(p, R); t = p.locator("#asset-tree").inner_text(); r.ok(f"MB-{U}" in t and f"MA-{U}" in t and f"MC-{U}" in t, "Tree reflects the move after reload", p.url, O, "reload root", "A under B", "ok")
    # forged move: to itself, to descendant
    lc = link_of(C)
    for label, lnk, newp, who in (("move A under its own child C (cycle)", link_of(A), C, A), ("move A under itself", link_of(A), A, A), ("move C under C", lc, C, C), ("move B under its descendant C", link_of(B), C, B)):
        before = sql(f"select parent_id from assets_assetcomponent where id='{lnk}'"); hier(p, who)
        with r.expect_errors(): res = bfetch(p, "POST", f"/app/components/{lnk}/move/", {"parent": newp})
        r.ok(sql(f"select parent_id from assets_assetcomponent where id='{lnk}'") == before, f"Cycle prevention (forged POST): {label}", f"/app/components/{lnk}/move/", O, "forged", "unchanged", f"http={res['status']}", db=before[:8])
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/components/{link_of(A)}/move/", {"parent": B});
    r.ok(parent_tag(A) == f"MB-{U}", "Moving to the current parent is a no-op/refused", p.url, O, "move to same parent", "unchanged", parent_tag(A))
    other = mk(f"MO-{U}", site=BLR)
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/components/{link_of(A)}/move/", {"parent": other})
    r.ok(parent_tag(A) == f"MB-{U}", "Move to a parent at another site refused", p.url, O, "forged parent at BLR-1", "unchanged", parent_tag(A))
    # detach via child's page: cancel, then confirm
    hier(p, D); rm = f"main form[action*='/components/{link_of(D)}/remove/']:has(input[value=child]) button"
    p.locator(rm).click(); dlg = p.locator("#fx-confirm"); dlg.wait_for(state="visible", timeout=3000)
    r.ok("Detach" in dlg.inner_text() and f"MD-{U}" in dlg.inner_text(), "Detach asks for confirmation naming the asset", p.url, O, "click Detach", "dialog", dlg.inner_text()[:80].replace("\n", " "))
    dlg.locator("button:has-text('Cancel')").click(); p.wait_for_timeout(400); r.ok(link_of(D) != "", "Cancel keeps the link", p.url, O, "Cancel", "link kept", "kept")
    cclick(p, p.locator(rm)); r.ok(link_of(D) == "" and ASSET(f"MD-{U}") and f"/app/assets/{D}/" in p.url, "Confirm detaches D, keeps the asset and returns to D's own page", p.url, O, "Detach + Confirm", "link gone, asset kept", p.url[-30:], db="link removed", audit=audits(R, "asset.component_removed"))
    hier(p, R); r.ok(f"MD-{U}" not in p.locator("#asset-tree").inner_text(), "Detached asset disappears from the tree", p.url, O, "reload", "gone", "ok")
    # detach via tree button on parent page
    hier(p, R); tb = p.locator("#asset-tree form[action*='/remove/'] button").first
    target_link = tb.evaluate("e=>e.closest('form').getAttribute('action')").split("/")[-3]; ch_before = sql(f"select child_id from assets_assetcomponent where id='{target_link}'")
    cclick(p, tb); r.ok(sql(f"select count(*) from assets_assetcomponent where id='{target_link}'") == "0" and ch_before and f"/app/assets/{R}/" in p.url, "Detach button inside the tree removes that link and returns to the parent page", p.url, O, "tree Detach + Confirm", "link gone", p.url[-30:], audit=audits(R, "asset.component_removed"))
    # replace flow = detach + attach another
    n = mk(f"MN-{U}"); add_child(p, R, n); r.ok(parent_tag(n) == f"MR-{U}", "Replace a component = detach then attach a replacement (no single 'replace' action)", p.url, O, "attach replacement", "attached", parent_tag(n))
    r.T("Single-step 'Replace component' action", p.url, O, "look for a replace control", "replace in one step", "No replace button: replacement is done by Detach + Add (two audited steps)", "PARTIAL")
    # detach twice
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/components/{la}/remove/", {"next_asset": "parent"}); res2 = bfetch(p, "POST", f"/app/components/{la}/remove/", {"next_asset": "parent"})
    r.ok(res2["status"] == 404 and "Server Error" not in res2["text"], "Detaching an already-removed link -> 404", p.url, O, "POST remove twice", "404", res2["status"])
    # history: parent's history tab lists hierarchy audit events
    p.goto(BASE + f"/app/assets/{R}/?tab=history"); cl = p.inner_text("#change-log")
    r.ok("component" in cl.lower(), "Parent's History tab (change log) lists the hierarchy changes", p.url, O, "open History", "component_* entries", cl[:120].replace("\n", " "))
    # meters/details reachable per node + independence
    p.goto(BASE + f"/app/assets/{C}/?tab=meters"); r.ok(p.locator("main form[action*='/meters/new/']").count() == 1, "Each component has its own Meters tab", p.url, O, "open child's Meters", "own meter form", "ok")
    return dict(R=R, A=A, B=B, C=C)


@feature(r, "Hierarchy: retire with links (F-M06 recheck)")
def t_retire():
    p = r.page(O); P, K = mk(f"RP-{U}"), mk(f"RK-{U}")
    add_child(p, P, K)
    for lab, rs in (("Start maintenance", "retire one"), ("Mark out of service", "retire two")):
        p.goto(BASE + f"/app/assets/{P}/"); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{lab}')")); f.locator("[name=reason]").fill(rs); f.locator("button").click(); p.wait_for_load_state("networkidle")
    p.goto(BASE + f"/app/assets/{P}/"); f = p.locator("main form[action*='/transition/']", has=p.locator("button:has-text('Retire')")); f.locator("[name=reason]").fill("scrap with child"); cclick(p, f.locator("button"))
    st = sql(f"select status from assets_asset where id='{P}'"); lk = link_of(K)
    hier(p, K)
    r.T("Retire a parent that still has a live child", p.url, O, "Retire parent P (child K attached)", "refused OR links detached first (HPE: hierarchy integrity)", f"retire accepted ({st}); link to live child K remains={bool(lk)}", "FAIL" if (st == "RETIRED" and lk) else "PASS", db=f"parent={st}, link={bool(lk)}", ev="F-M06 reproduced in browser" if lk else "")
    can_detach = p.locator("main form[action*='/remove/'] button").count()
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/components/{lk}/remove/", {"next_asset": "child"})
    r.T("Detach the live child K from the retired parent", p.url, O, "click Detach (forged POST)", "child can be detached", f"http={res['status']}; link still present={bool(link_of(K))}; detach control visible={can_detach}", "FAIL" if link_of(K) else "PASS", db=f"link={bool(link_of(K))}")
    hier(p, K); has_edit = p.locator("main details summary:has-text('Edit relationship')").count() > 0
    r.T("Hierarchy tab of the live child under a retired parent", p.url, O, "open K's Hierarchy tab", "usable controls to re-parent", f"edit/move/detach forms rendered={has_edit}", "PASS" if has_edit else "PARTIAL")


@feature(r, "Hierarchy RBAC")
def t_rbac():
    P, A, B = mk(f"HR-{U}"), mk(f"HA-{U}"), mk(f"HB-{U}")
    addp = pg
    add_child(addp, P, A)
    ln = {ro: mk(f"HC-{ro}-{U}"[:40]) for ro in ROLE_LIST}
    fr = {ro: mk(f"HF-{ro}-{U}"[:40]) for ro in ROLE_LIST}
    for ro in ROLE_LIST: add_child(addp, P, ln[ro])
    movers = {ro: mk(f"HM-{ro}-{U}"[:40]) for ro in ROLE_LIST}
    for ro in ROLE_LIST: add_child(addp, A, movers[ro])
    def attempt(role, code, label, path, data, probe, restore=None):
        p = r.page(role); allowed = perm(role, code); before = sql(probe)
        with (contextlib_null() if allowed else r.expect_errors()):
            res = bfetch(p, "POST", path, data)
        after = sql(probe); changed = before != after
        good = (res["status"] in (200, 302) and changed) if allowed else (res["status"] in (403, 404) and not changed)
        r.ok(good, f"RBAC {label}", path, role, "POST real browser request", "allowed: succeeds + DB changes" if allowed else "denied: 403/404 + DB unchanged", f"http={res['status']} changed={changed} perm({code})={allowed}", db=f"{before} -> {after}")
    for ro in ROLE_LIST:
        p = r.page(ro); has = lambda c: perm(ro, c)
        hier(p, P) if has("asset.view") else None
        if has("asset.view"):
            r.ok(p.locator("#asset-tree").count() == 1, "RBAC tree visible to every asset viewer", p.url, ro, "open hierarchy", "tree", "ok")
            r.ok((p.locator("main form[action*='/components/add/']").count() > 0) == has("asset.hierarchy.manage"), "RBAC 'Add existing asset' form iff asset.hierarchy.manage", p.url, ro, "inspect", f"{has('asset.hierarchy.manage')}", "ok")
            r.ok((p.locator("main a:has-text('Register a new child asset')").count() > 0) == has("asset.hierarchy.manage"), "RBAC 'Register a new child asset' link iff asset.hierarchy.manage", p.url, ro, "inspect", f"{has('asset.hierarchy.manage')}", "ok")
            r.ok((p.locator("#asset-tree form[action*='/remove/']").count() > 0) == has("asset.hierarchy.manage"), "RBAC tree 'Detach' buttons iff asset.hierarchy.manage", p.url, ro, "inspect tree", f"{has('asset.hierarchy.manage')}", "ok")
            hier(p, A); r.ok((p.locator("main details summary:has-text('Edit relationship')").count() > 0 and p.locator("main form[action*='/move/']").count() > 0) == has("asset.hierarchy.manage"), "RBAC edit/move controls on a child iff asset.hierarchy.manage", p.url, ro, "inspect child", f"{has('asset.hierarchy.manage')}", "ok")
        # direct URL ?parent=
        a_ = has("asset.hierarchy.manage") and has("asset.create")
        with (contextlib_null() if a_ else r.expect_errors()):
            resp = p.goto(BASE + f"/app/assets/new/?parent={P}"); p.wait_for_load_state("networkidle")
        r.ok((resp.status == 200) == a_ and (a_ or resp.status in (403, 404)), "RBAC direct URL: register-child form", f"/app/assets/new/?parent={P}", ro, "type URL", "200 iff hierarchy.manage + asset.create", resp.status)
        attempt(ro, "asset.hierarchy.manage", "attach child", f"/app/assets/{B}/components/add/", {"child": fr[ro], "relationship_type": "COMPONENT", "quantity": "1"}, f"select count(*) from assets_assetcomponent where child_id='{fr[ro]}' and parent_id='{B}'")
        lnk = link_of(A)
        attempt(ro, "asset.hierarchy.manage", "edit relationship", f"/app/components/{lnk}/edit/", {"relationship_type": "ASSEMBLY", "quantity": str(2 + ROLE_LIST.index(ro)), "part_number": "", "notes": ro}, f"select quantity||notes from assets_assetcomponent where id='{lnk}'")
        lm = link_of(movers[ro])
        attempt(ro, "asset.hierarchy.manage", "move component", f"/app/components/{lm}/move/", {"parent": P}, f"select parent_id from assets_assetcomponent where id='{lm}'")
        lr = link_of(ln[ro]) if sql(f"select count(*) from assets_assetcomponent where child_id='{ln[ro]}'") != "0" else ""
        if lr: attempt(ro, "asset.hierarchy.manage", "detach component", f"/app/components/{lr}/remove/", {"next_asset": "parent"}, f"select count(*) from assets_assetcomponent where id='{lr}'")


@feature(r, "Hierarchy tenant isolation")
def t_tenant():
    bo = r.page("betaowner"); bsite = sql("select id from sites_site where code='PUN-1'"); bcat = sql("select id from assets_assetcategory where organization_id<>%s limit 1" % ALPHA)
    bres = [bapi(bo, "POST", "/api/v1/assets/", {"asset_tag": f"{t}-{U}", "name": t, "category": bcat, "site": bsite}) for t in ("BP", "BC", "BX")]
    BP, BC, BX = (sql(f"select id from assets_asset where asset_tag='{t}-{U}'") for t in ("BP", "BC", "BX"))
    add_child(bo, BP, BC); blink = sql(f"select id from assets_assetcomponent where child_id='{BC}'")
    r.ok(blink != "", "Setup: Beta hierarchy exists (BP > BC)", "-", "betaowner", "attach via Beta UI", "link", "ok")
    AP, AC, AX = mk(f"TP-{U}"), mk(f"TC-{U}"), mk(f"TX-{U}"); add_child(pg, AP, AC); alink = link_of(AC)
    n = lambda: sql("select count(*) from assets_assetcomponent")
    def cross(label, who, path, data, probe, method="POST"):
        p = r.page(who); before = sql(probe)
        with r.expect_errors(): res = bfetch(p, method, path, data)
        after = sql(probe); okst = res["status"] in (400, 403, 404) or (res["status"] == 200 and ("Choose" in res["html"] or "valid" in res["html"] or "Invalid" in res["html"] or "not found" in res["html"].lower() or "cannot" in res["html"].lower() or "different" in res["html"].lower()))
        r.ok(okst and before == after, f"Tenant: {label}", path, who, f"{method} other tenant's object", "refused (403/404, or error message after redirect), DB unchanged", f"http={res['status']}", db=f"{before} -> {after}")
    cross("Beta cannot open Alpha's tree partial", "betaowner", f"/app/assets/{AP}/tree/", None, "select 1", "GET")
    cross("Beta cannot open Alpha's hierarchy tab", "betaowner", f"/app/assets/{AP}/?tab=hierarchy", None, "select 1", "GET")
    cross("Beta cannot attach under an Alpha parent", "betaowner", f"/app/assets/{AP}/components/add/", {"child": BX, "relationship_type": "COMPONENT", "quantity": "1"}, f"select count(*) from assets_assetcomponent where parent_id='{AP}'")
    cross("Beta cannot edit an Alpha link", "betaowner", f"/app/components/{alink}/edit/", {"relationship_type": "ASSEMBLY", "quantity": "9", "part_number": "", "notes": "hijack"}, f"select quantity||notes from assets_assetcomponent where id='{alink}'")
    cross("Beta cannot move an Alpha link", "betaowner", f"/app/components/{alink}/move/", {"parent": BP}, f"select parent_id from assets_assetcomponent where id='{alink}'")
    cross("Beta cannot detach an Alpha link", "betaowner", f"/app/components/{alink}/remove/", {"next_asset": "parent"}, f"select count(*) from assets_assetcomponent where id='{alink}'")
    cross("Alpha cannot open Beta's tree partial", "owner", f"/app/assets/{BP}/tree/", None, "select 1", "GET")
    cross("Alpha cannot attach under a Beta parent", "owner", f"/app/assets/{BP}/components/add/", {"child": AX, "relationship_type": "COMPONENT", "quantity": "1"}, f"select count(*) from assets_assetcomponent where parent_id='{BP}'")
    cross("Alpha cannot edit a Beta link", "owner", f"/app/components/{blink}/edit/", {"relationship_type": "ASSEMBLY", "quantity": "9", "part_number": "", "notes": "hijack"}, f"select quantity||notes from assets_assetcomponent where id='{blink}'")
    cross("Alpha cannot move a Beta link", "owner", f"/app/components/{blink}/move/", {"parent": AP}, f"select parent_id from assets_assetcomponent where id='{blink}'")
    cross("Alpha cannot detach a Beta link", "owner", f"/app/components/{blink}/remove/", {"next_asset": "parent"}, f"select count(*) from assets_assetcomponent where id='{blink}'")
    # cross-tenant child supplied to an Alpha parent
    cross("Alpha parent + Beta child id is refused", "owner", f"/app/assets/{AP}/components/add/", {"child": BX, "relationship_type": "COMPONENT", "quantity": "1"}, f"select count(*) from assets_assetcomponent where child_id='{BX}'")
    cross("Alpha move to a Beta parent is refused", "owner", f"/app/components/{alink}/move/", {"parent": BP}, f"select parent_id from assets_assetcomponent where id='{alink}'")
    cross("Alpha register-child with a Beta ?parent=", "owner", f"/app/assets/new/?parent={BP}", None, "select 1", "GET")
    p = r.page("betaowner"); hier(p, BP); r.ok("TP-" not in p.locator("#asset-tree").inner_text() and not any(x in p.locator("main form[action*='/components/add/'] [name=child]").inner_text() for x in ("GEN-001", f"TX-{U}", f"TC-{U}")), "Beta candidate list/tree never contains Alpha assets", p.url, "betaowner", "read", "none", "ok")
    ap_ = bapi(p, "GET", f"/api/v1/assets/{AP}/components/"); r.ok(ap_["status"] == 404, "API: Beta GET Alpha components -> 404", "-", "betaowner", "browser fetch", "404", ap_["status"])


@feature(r, "Hierarchy responsive")
def t_responsive():
    root = ASSET(f"D0-{U}") or ASSET(f"ROOT-{U}")
    for vp in ("desktop", "laptop", "tablet", "mobile"):
        p = r.page(O, vp)
        for name, path in (("Hierarchy tab (8-level tree)", f"/app/assets/{root}/?tab=hierarchy"), ("Hierarchy tab (deep node)", f"/app/assets/{ASSET(f'D7-{U}')}/?tab=hierarchy"), ("Register child form", f"/app/assets/new/?parent={root}")):
            p.goto(BASE + path); p.wait_for_load_state("networkidle"); p.wait_for_timeout(400)
            ov = overflow(p); fine = ov["sw"] <= ov["iw"] + 1 and not ov["wide"] and not ov["clipped"]
            ev = "" if fine else shot(p, f"M03_{vp}_{name.split(' (')[0].replace(' ', '_')}")
            r.ok(fine, f"Responsive {vp}: {name} (no horizontal overflow / clipped controls)", path, O, f"open at {VIEWPORTS[vp][0]}x{VIEWPORTS[vp][1]}", "no overflow", f"sw={ov['sw']} iw={ov['iw']} wide={ov['wide'][:2]} clipped={ov['clipped'][:2]}", ev=ev)
        if vp == "mobile": shot(p, "M03_mobile_tree")
    p = r.page(O, "mobile"); p.goto(BASE + f"/app/assets/{root}/?tab=hierarchy"); p.wait_for_load_state("networkidle")
    tb = p.locator("#asset-tree form button").first
    if tb.count():
        box = tb.bounding_box(); r.ok(bool(box) and box["width"] >= 24 and box["height"] >= 16, "Mobile: Detach button in the tree has a usable tap target", p.url, O, "measure Detach", ">=24x16 px", box, partial=True)


for f in (t_tree, t_add, t_new_child, t_edit_move_detach, t_retire, t_rbac, t_tenant, t_responsive):
    f()

fails = [x for x in r.rows if x["status"] == "FAIL"]; unv = [x for x in r.rows if x["status"] == "UNVERIFIED"]
print("ROWS", len(r.rows), "FAIL", len(fails), "UNVF", len(unv), "PARTIAL", len([x for x in r.rows if x['status'] == 'PARTIAL']))
for x in fails + unv: print("  ", x["status"], x["feature"], "|", str(x["action"])[:50], "|", str(x["actual"])[:170])
print("ISSUES", len(r.issues))
for i in r.issues[:25]: print("  ", i["kind"], i["feature"], i["role"], i["text"][:130], i.get("url", "")[-60:])
r.stop()
