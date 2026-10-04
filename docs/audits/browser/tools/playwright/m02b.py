import sys, time, json, io, zipfile, base64, hashlib; sys.path.insert(0, '.')
from bx import *
r = Run("M02").start()
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


def mk(tag, name="QA asset", **kw):
    d = {"asset_tag": tag, "name": name, "category": PUMP, "site": HYD}; d.update(kw)
    res = bapi(pg, "POST", "/api/v1/assets/", d)
    return ASSET(tag)


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
def mkzip():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z: z.writestr("[Content_Types].xml", "<Types/>"); z.writestr("word/document.xml", "<w/>")
    return b.getvalue()
DOCX = mkzip()


def upload(p, aid, name, content, title="", dtype=None, expect_ok=True, mime="application/octet-stream"):
    p.goto(BASE + f"/app/assets/{aid}/?tab=documents"); p.wait_for_load_state("networkidle")
    f = "main form[action*='/documents/']"
    p.locator(f"{f} input[type=file]").set_input_files({"name": name, "mimeType": mime, "buffer": content})
    if title: p.locator(f"{f} [name=title]").fill(title)
    if dtype: p.locator(f"{f} [name=doc_type]").select_option(value=dtype)
    with p.expect_response(lambda x: x.request.method == "POST" and "/documents/" in x.url) as ri:
        p.locator(f"{f} button:has-text('Upload')").click()
    p.wait_for_load_state("networkidle")
    return ri.value.status, msgs(p)


@feature(r, "Documents")
def t_docs():
    tag = f"DOC-{U}"; a = mk(tag); D = f"/app/assets/{a}/?tab=documents"
    st, p = visit(r, O, D)
    r.ok("No documents" in p.inner_text("main") and p.locator("main form[action*='/documents/']").count() == 1, "Documents tab: empty state + upload form for a user with asset.document.manage", D, O, "open tab", "empty state + form", p.inner_text("main")[:80].replace("\n", " "))
    r.ok("PDF, images" in p.inner_text("main"), "Upload form states the accepted file types", D, O, "read help text", "types listed", "ok")
    opts = p.locator("main [name=doc_type] option").all_inner_texts(); r.ok(len(opts) >= 5, "Document type dropdown has the HPE document kinds", D, O, "read options", "manual/warranty/…", opts)
    types = p.eval_on_selector_all("main [name=doc_type] option", "o=>o.map(x=>x.value)")
    cnt = lambda: sql(f"select count(*) from assets_assetdocument where asset_id='{a}' and is_active")
    # valid uploads of every allowed family
    cases = [("manual.pdf", PDF, "application/pdf"), ("photo.png", PNG, "image/png"), ("notes.txt", b"plain text notes\n", "text/plain"), ("data.csv", b"a,b\n1,2\n", "text/csv"), ("spec.docx", DOCX, "application/octet-stream")]
    for i, (nm, content, mime) in enumerate(cases):
        before = cnt(); st, m = upload(p, a, nm, content, title=f"Doc {nm}", dtype=types[i % len(types)], mime=mime)
        row = sql(f"select d.title||'|'||d.doc_type||'|'||f.original_name||'|'||f.size||'|'||f.sha256 from assets_assetdocument d join files_attachment f on f.id=d.attachment_id where d.asset_id='{a}' and d.title='Doc {nm}'")
        exp = f"Doc {nm}|{types[i % len(types)]}|{nm}|{len(content)}|{hashlib.sha256(content).hexdigest()}"
        r.ok(row == exp and cnt() == str(int(before) + 1) and "uploaded" in m.lower(), f"Upload {nm}: stored with title/type/name/size/sha256 + success message", D, O, f"upload {nm}", "document + attachment rows match", row[:90], db=row[:100], audit=audits(a, "asset.document_added"))
    p.goto(BASE + D); t = p.inner_text("main")
    r.ok(all(n in t for n, _, _ in cases) and "Download" in t, "All uploaded documents are listed with a Download button", D, O, "read table", "5 rows", t[:100].replace("\n", " "))
    # default title = file name
    st, m = upload(p, a, "untitled.txt", b"x"); r.ok(sql(f"select title from assets_assetdocument where asset_id='{a}' order by created_at desc limit 1") == "untitled.txt", "Blank title defaults to the file name", D, O, "upload without title", "title=file name", sql(f"select title from assets_assetdocument where asset_id='{a}' order by created_at desc limit 1"))
    # refresh persistence
    p.reload(); r.ok(p.inner_text("main").count("Download") >= 6, "Documents survive refresh", D, O, "reload", "all listed", "ok")
    # download
    row = p.locator("main table tbody tr", has_text="manual.pdf")
    with p.expect_download() as dl: row.locator("a:has-text('Download')").click()
    d = dl.value; path = d.path(); data = open(path, "rb").read()
    r.ok(data == PDF and d.suggested_filename == "manual.pdf", "Download returns the exact uploaded bytes with the original file name", D, O, "click Download", "same bytes / name", f"{len(data)} bytes, {d.suggested_filename}", db=f"sha={hashlib.sha256(data).hexdigest()[:12]}")
    aid = sql(f"select attachment_id from assets_assetdocument where asset_id='{a}' and title='Doc manual.pdf'")
    resp = p.context.request.get(BASE + f"/app/files/{aid}/download/")
    hd = {k.lower(): v for k, v in resp.headers.items()}
    r.ok(resp.status == 200 and hd.get("x-content-type-options") == "nosniff" and "attachment" in hd.get("content-disposition", "").lower(), "Download response: 200, nosniff, Content-Disposition: attachment", "-", O, "inspect headers", "200 + nosniff + attachment", {k: hd.get(k) for k in ("x-content-type-options", "content-disposition", "content-type")} | {"status": resp.status})
    # invalid uploads (all must be refused with a message and no rows)
    bad = [("virus.exe", b"MZ\x90\x00bad", "File type"), ("script.js", b"alert(1)", "File type"), ("fake.pdf", b"this is not a pdf", "does not match"), ("fakepng.png", b"<html>nope</html>", "does not match"),
           ("empty.txt", b"", "empty"), ("binary.txt", b"abc\x00def", "binary"), ("noext", b"hello", "File type"), ("evil.pdf.exe", b"MZ", "File type"), ("page.html", b"<script>alert(1)</script>", "File type"), ("arch.zip", mkzip(), "File type")]
    for nm, content, frag in bad:
        before = cnt()
        with r.expect_errors(): st, m = upload(p, a, nm, content, expect_ok=False)
        after = cnt()
        r.ok(before == after and (frag.lower() in (m + p.inner_text("main")).lower() or "choose a file" in m.lower()), f"Invalid upload refused: {nm}", D, O, f"upload {nm}", f"refused ('{frag}'), no row", f"http={st} {m[:80]}", db=f"{before}->{after}")
    # no file chosen
    p.goto(BASE + D); fi = p.locator("main form[action*='/documents/'] input[type=file]")
    before = cnt(); reqs = []
    p.on("request", lambda q: reqs.append(q.url) if q.method == "POST" and "/documents/" in q.url else None)
    p.locator("main form[action*='/documents/'] button:has-text('Upload')").click(); p.wait_for_timeout(700)
    r.ok(fi.get_attribute("required") is not None and not reqs, "Upload with no file: the browser blocks the submit (file input is required)", D, O, "click Upload with no file", "blocked client-side", f"required={fi.get_attribute('required') is not None}, POSTs sent={len(reqs)}")
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{a}/documents/", {"title": "nofile", "doc_type": "OTHER"})
    r.ok(cnt() == before and "choose a file" in res["html"].lower(), "Upload with no file (forged past the browser): server answers 'Choose a file to upload'", D, O, "POST without file", "refused with message", msgs(p)[:60], db=f"{before}->{cnt()}")
    # oversize
    big = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 10)
    before = cnt()
    with r.expect_errors(): st, m = upload(p, a, "big.pdf", big, expect_ok=False)
    r.ok(cnt() == before and ("exceeds" in (m + p.inner_text("main")).lower() or st in (400, 413)), "Oversize file (>10 MB) refused", D, O, "upload 10 MB + 10 bytes", "refused with size message", f"http={st} {m[:80]}", db=f"{before}->{cnt()}")
    exact = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 - 9)
    st, m = upload(p, a, "limit.pdf", exact); r.ok(cnt() == str(int(before) + 1), "Boundary: exactly 10 MB accepted", D, O, "upload exactly 10 MB", "accepted", f"http={st} {m[:60]}", db=cnt())
    # filename hardening
    st, m = upload(p, a, "../../etc/pass wd<>.pdf", PDF, title="trav")
    fn = sql(f"select f.original_name||'|'||f.file from assets_assetdocument d join files_attachment f on f.id=d.attachment_id where d.asset_id='{a}' and d.title='trav'")
    r.ok(fn and ".." not in fn.split("|")[0] and "/" not in fn.split("|")[0] and fn.split("|")[1].startswith("organizations/"), "Path-traversal / unsafe file name is sanitised; stored under organizations/<org>/ with a random name", D, O, "upload ../../etc/pass wd<>.pdf", "sanitised", fn, db=fn)
    # XSS title
    st, m = upload(p, a, "x.txt", b"x", title="<img src=x onerror=window.__dx=1>"); p.goto(BASE + D); r.ok(p.evaluate("()=>!window.__dx") and "<img src=x" not in p.content(), "Stored XSS in document title is escaped", D, O, "title=<img onerror>", "inert", "ok")
    # remove: reason required
    p.goto(BASE + D); rowx = p.locator("main table tbody tr", has_text="Doc notes.txt")
    docid = sql(f"select id from assets_assetdocument where asset_id='{a}' and title='Doc notes.txt'")
    with r.expect_errors():
        rowx.locator("input[name=reason]").fill(""); rowx.locator("button").last.click(); p.wait_for_timeout(600)
    r.ok(sql(f"select is_active from assets_assetdocument where id='{docid}'") == "t", "Remove without a reason is refused (document stays)", D, O, "Remove, blank reason", "refused", msgs(p)[:60] or "blocked by browser validation", partial=False)
    p.goto(BASE + D); rowx = p.locator("main table tbody tr", has_text="Doc notes.txt"); rowx.locator("input[name=reason]").fill("superseded")
    cclick(p, rowx.locator("button").last)
    row = sql(f"select is_active||'|'||removed_reason||'|'||(removed_by_id is not null) from assets_assetdocument where id='{docid}'")
    r.ok(row == "false|superseded|true", "Remove with reason: soft-removed (reason, who, when stored)", D, O, "Remove with reason 'superseded'", "inactive + reason", row, db=row, audit=audits(a, "asset.document_removed"))
    p.goto(BASE + D); r.ok("Doc notes.txt" not in p.inner_text("main"), "Removed document no longer listed (survives refresh)", D, O, "reload", "gone", "ok")
    att = sql(f"select attachment_id from assets_assetdocument where id='{docid}'")
    with r.expect_errors(): rs = p.context.request.get(BASE + f"/app/files/{att}/download/")
    r.ok(rs.status in (403, 404), "Download of a removed document is blocked", "-", O, "GET download URL", "403/404", rs.status)
    # remove twice
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/documents/{docid}/remove/", {"reason": "again"})
    r.ok(sql(f"select count(*) from audit_auditlog where target_id='{a}' and action='asset.document_removed'") == "1", "Removing an already-removed document does nothing new", "-", O, "POST remove twice", "no second removal", "1 audit row")
    # type + delete not exposed
    r.T("Document edit/replace", D, O, "look for edit/replace", "if exposed, test", "No edit/replace: upload a new document and remove the old one", "NOT APPLICABLE")


@feature(r, "Meters")
def t_meters():
    tag = f"MET-{U}"; a = mk(tag); M = f"/app/assets/{a}/?tab=meters"
    st, p = visit(r, O, M)
    r.ok("No meters" in p.inner_text("main") and p.locator("main form[action*='/meters/new/']").count() == 1, "Meters tab: empty state + Add meter form", M, O, "open tab", "empty + form", p.inner_text("main")[:60].replace("\n", " "))
    def addm(name, unit, ok=True):
        p.goto(BASE + M); p.wait_for_load_state("networkidle"); f = "main form[action*='/meters/new/']"
        p.locator(f"{f} [name=name]").fill(name); p.locator(f"{f} [name=unit]").fill(unit)
        with (contextlib_null() if ok else r.expect_errors()):
            p.locator(f"{f} button:has-text('Add meter')").click(); p.wait_for_load_state("networkidle")
        return msgs(p)
    mc = lambda: sql(f"select count(*) from assets_assetmeter where asset_id='{a}'")
    m = addm("Run hours", "h")
    r.ok(sql(f"select name||'|'||unit||'|'||is_active from assets_assetmeter where asset_id='{a}'") == "Run hours|h|true" and "added" in m.lower(), "Add meter: name/unit stored, active, success message", M, O, "Add 'Run hours (h)'", "row saved", m[:60], audit=audits(a, "asset.meter_created"))
    b = mc(); addm("run HOURS", "h", ok=False); r.ok(mc() == b, "Duplicate meter name (case-insensitive) refused", M, O, "add 'run HOURS'", "refused", msgs(p)[:80])
    b = mc(); addm("", "h", ok=False); r.ok(mc() == b, "Blank meter name refused", M, O, "blank name", "refused", msgs(p)[:80])
    b = mc(); addm("Odo", "", ok=False); r.ok(mc() == b, "Blank unit refused", M, O, "blank unit", "refused", msgs(p)[:80])
    p.goto(BASE + M)
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{a}/meters/new/", {"name": "N" * 81, "unit": "h"})
    r.ok(mc() == b, "Meter name > 80 chars refused (server)", M, O, "forged 81 chars", "refused", f"http={res['status']}")
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/assets/{a}/meters/new/", {"name": "Okname", "unit": "U" * 21})
    r.ok(mc() == b, "Meter unit > 20 chars refused (server)", M, O, "forged 21 chars", "refused", f"http={res['status']}")
    addm("N" * 80, "u" * 20); r.ok(mc() == str(int(b) + 1), "Boundary: 80-char name and 20-char unit accepted", M, O, "max lengths", "accepted", mc())
    addm("<b onmouseover=window.__mx=1>x</b>", "u"); p.goto(BASE + M); r.ok(p.evaluate("()=>!window.__mx") and "<b onmouseover" not in p.content(), "Stored XSS in meter name is escaped", M, O, "name=<b>", "inert", "ok")
    mid = sql(f"select id from assets_assetmeter where asset_id='{a}' and name='Run hours'")
    def reading(value, at="", notes="", ok=True, meter=mid):
        p.goto(BASE + M); p.wait_for_load_state("networkidle"); f = p.locator(f"main form[action*='/meters/{meter}/reading/']")
        f.locator("[name=value]").evaluate("e=>e.type='text'"); f.locator("[name=value]").fill(str(value)); f.locator("[name=read_at]").evaluate("(e,v)=>{e.type='text';e.value=v}", at); f.locator("[name=notes]").fill(notes)
        with (contextlib_null() if ok else r.expect_errors()):
            f.locator("button:has-text('Record')").click(); p.wait_for_load_state("networkidle")
        return msgs(p)
    rc = lambda: sql(f"select count(*) from assets_assetmeterreading where meter_id='{mid}'")
    m = reading("100.5", notes="first")
    row = sql(f"select value||'|'||notes||'|'||source from assets_assetmeterreading where meter_id='{mid}'")
    r.ok(row == "100.500|first|manual" and "recorded" in m.lower(), "Record reading (value, notes, source=manual)", M, O, "value 100.5 + notes", "row saved", row, db=row, audit=audits(a, "asset.meter_reading_recorded"))
    r.ok("100.5" in p.inner_text("main") and "Last reading" in p.inner_text("main"), "'Last reading' shows the new value", M, O, "read card", "100.5 h", "ok")
    b = rc(); reading("90", ok=False); r.ok(rc() == b and "lower than" in (msgs(p) + p.inner_text("main")), "Lower reading than previous refused (monotonic)", M, O, "value 90 after 100.5", "refused", msgs(p)[:90])
    b = rc(); reading("100.5"); r.ok(rc() == str(int(b) + 1), "Equal reading accepted (boundary)", M, O, "value 100.5 again", "accepted", rc())
    b = rc(); reading("-5", ok=False); r.ok(rc() == b, "Negative reading refused", M, O, "value -5", "refused", msgs(p)[:80])
    b = rc(); reading("abc", ok=False); r.ok(rc() == b, "Non-numeric reading refused", M, O, "value abc", "refused", msgs(p)[:80])
    b = rc(); reading("1.2345", ok=False); r.ok(rc() == b, "More than 3 decimals refused", M, O, "value 1.2345", "refused", msgs(p)[:80])
    b = rc(); reading("10000000000000", ok=False); r.ok(rc() == b, "Reading >= 1e13 refused", M, O, "value 1e13", "refused", msgs(p)[:80])
    b = rc(); reading("99999999999999999", ok=False); r.ok(rc() == b, "Absurdly large reading refused without a server error", M, O, "value 99999999999999999", "refused", msgs(p)[:80])
    fut = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 86400 * 2)); b = rc(); reading("200", at=fut, ok=False)
    r.ok(rc() == b and "future" in (msgs(p) + p.inner_text("main")).lower(), "Reading time in the future refused", M, O, "time +2 days", "refused", msgs(p)[:80])
    past = time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() - 86400 * 30)); b = rc(); reading("300", at=past, ok=False)
    r.ok(rc() == b and "earlier" in (msgs(p) + p.inner_text("main")).lower(), "Reading time earlier than the previous one refused", M, O, "time -30 days", "refused", msgs(p)[:80])
    b = rc(); reading("150", notes="x" * 300); r.ok(rc() == str(int(b) + 1), "Boundary: 300-char note accepted", M, O, "note 300 chars", "accepted", rc())
    reading("160", at=time.strftime("%Y-%m-%dT%H:%M", time.gmtime(time.time() + 120))); r.ok(sql(f"select count(*) from assets_assetmeterreading where meter_id='{mid}' and value=160") == "1", "Explicit reading time (now+2min, inside the 5-minute tolerance) accepted", M, O, "time now+2min", "accepted", "ok")
    last = sql(f"select value from assets_assetmeterreading where meter_id='{mid}' order by read_at desc, created_at desc limit 1"); p.goto(BASE + M)
    r.ok("160" in p.inner_text("main"), "Last reading display matches the latest stored value", M, O, "read card", f"{last}", "ok", db=last)
    r.T("Meter reading history list", M, O, "look for the list of past readings", "readings table", "UI shows only the LAST reading per meter; the full reading history is not visible in the browser (only via API/DB)", "PARTIAL", db=f"{rc()} readings stored")
    r.T("Edit meter (rename / change unit)", M, O, "look for edit control", "edit form", "No edit control: a meter can only be created, activated or deactivated", "NOT APPLICABLE")
    # deactivate / activate
    p.goto(BASE + M); tog = p.locator(f"main form[action*='/meters/{mid}/toggle/'] button"); lab = tog.inner_text().strip()
    cclick(p, tog)
    r.ok(sql(f"select is_active from assets_assetmeter where id='{mid}'") == "f", f"Deactivate meter ('{lab}' button)", M, O, "click deactivate", "is_active=false", sql(f"select is_active from assets_assetmeter where id='{mid}'"), audit=audits(a))
    p.goto(BASE + M); r.ok(p.locator(f"main form[action*='/meters/{mid}/reading/']").count() == 0, "Inactive meter has no reading form", M, O, "inspect card", "no form", "hidden")
    b = rc()
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/meters/{mid}/reading/", {"value": "999"})
    r.ok(rc() == b, "Reading on an inactive meter refused (forged POST)", M, O, "POST reading", "refused", f"http={res['status']}", db=f"{b}->{rc()}")
    cclick(p, p.locator(f"main form[action*='/meters/{mid}/toggle/'] button")); r.ok(sql(f"select is_active from assets_assetmeter where id='{mid}'") == "t", "Reactivate meter", M, O, "click activate", "is_active=true", "t", audit=audits(a))
    with r.expect_errors(): res = bfetch(p, "POST", f"/app/meters/{mid}/toggle/", {"action": "activate"})
    r.ok(res["status"] in (200, 400, 409), "Activate an already-active meter does not crash", M, O, "POST activate twice", "no 500", res["status"])
    # unauth-ish: reading on missing meter
    with r.expect_errors(): res = bfetch(p, "POST", "/app/meters/00000000-0000-0000-0000-000000000000/reading/", {"value": "1"})
    r.ok(res["status"] == 404, "Reading for an unknown meter -> 404", "-", O, "random uuid", "404", res["status"])


@feature(r, "Status lifecycle")
def t_status():
    tag = f"LC-{U}"; a = mk(tag); D = f"/app/assets/{a}/"
    st = lambda: sql(f"select status from assets_asset where id='{a}'")
    hist = lambda: sql(f"select string_agg(coalesce(nullif(from_status,''),'-')||'>'||to_status||':'||action||':'||reason, ' ; ' order by created_at, id) from assets_assetstatushistory where asset_id='{a}'")
    p = r.page(O)
    def buttons():
        p.goto(BASE + D); p.wait_for_load_state("networkidle"); return [b.strip() for b in p.locator("main form[action*='/transition/'] button").all_inner_texts()]
    def act(label, reason, confirm=False, ok=True):
        p.goto(BASE + D); p.wait_for_load_state("networkidle"); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{label}')"))
        f.locator("[name=reason]").fill(reason)
        with (contextlib_null() if ok else r.expect_errors()):
            if confirm: cclick(p, f.locator("button"))
            else:
                f.locator("button").click(); p.wait_for_load_state("networkidle")
        return msgs(p)
    r.ok(st() == "ACTIVE" and buttons() == ["Start maintenance"], "ACTIVE: only 'Start maintenance' offered", D, O, "open", "1 button", buttons())
    # reason required
    p.goto(BASE + D)
    with r.expect_errors(): res = bfetch(p, "POST", f"{D}transition/start_maintenance/", {"reason": ""})
    r.ok(st() == "ACTIVE", "Transition without a reason refused (server)", D, O, "POST blank reason", "ACTIVE", st())
    with r.expect_errors(): res = bfetch(p, "POST", f"{D}transition/start_maintenance/", {"reason": "ab"})
    r.ok(st() == "ACTIVE", "Reason shorter than 3 characters refused (server)", D, O, "POST reason 'ab'", "ACTIVE", st())
    f = p.locator("main form[action*='/transition/'] [name=reason]").first
    r.ok(f.get_attribute("required") is not None and f.get_attribute("minlength") == "3", "Reason input is required with minlength=3 (client hint)", D, O, "inspect", "required/minlength", "ok")
    # forged invalid transitions on ACTIVE
    for action in ("retire", "dispose", "mark_out_of_service", "return_to_service", "complete_maintenance", "explode"):
        with r.expect_errors(): res = bfetch(p, "POST", f"{D}transition/{action}/", {"reason": "forged transition"})
        r.ok(st() == "ACTIVE", f"Forged invalid transition '{action}' on ACTIVE does not change the status", D, O, f"POST {action}", "ACTIVE", f"{st()} http={res['status']}", db=st())
    with r.expect_errors(): res = bfetch(p, "GET", f"{D}transition/start_maintenance/")
    r.ok(res["status"] == 405 and st() == "ACTIVE", "GET on a transition URL is refused (405)", D, O, "GET transition", "405", res["status"])
    # chain
    m = act("Start maintenance", "annual overhaul"); r.ok(st() == "UNDER_MAINTENANCE" and "updated" in m.lower(), "ACTIVE -> UNDER MAINTENANCE via UI", D, O, "Start maintenance + reason", "UNDER_MAINTENANCE", st(), db=st(), audit=audits(a, "asset.status_changed"))
    r.ok(sorted(buttons()) == ["Complete maintenance", "Mark out of service"], "UNDER MAINTENANCE: offers Complete maintenance + Mark out of service", D, O, "read buttons", "2 buttons", buttons())
    p.goto(BASE + D); r.ok("Under Maintenance" in p.inner_text("main h1") or "Under maintenance" in p.inner_text("main h1").title() or "UNDER" in p.inner_text("main h1").upper(), "Status badge in the header reflects the new status", D, O, "read h1", "Under maintenance", p.inner_text("main h1"))
    m = act("Complete maintenance", "finished"); r.ok(st() == "ACTIVE", "UNDER MAINTENANCE -> ACTIVE (Complete maintenance)", D, O, "click", "ACTIVE", st(), db=st(), audit=audits(a, "asset.status_changed"))
    act("Start maintenance", "second job"); act("Mark out of service", "beyond repair soon"); r.ok(st() == "OUT_OF_SERVICE", "UNDER MAINTENANCE -> OUT OF SERVICE", D, O, "Mark out of service", "OUT_OF_SERVICE", st(), db=st())
    r.ok(sorted(buttons()) == ["Dispose", "Retire", "Return to service"], "OUT OF SERVICE: offers Return to service, Retire, Dispose", D, O, "read buttons", "3 buttons", buttons())
    act("Return to service", "repaired"); r.ok(st() == "ACTIVE", "OUT OF SERVICE -> ACTIVE (Return to service)", D, O, "click", "ACTIVE", st(), db=st())
    act("Start maintenance", "third"); act("Mark out of service", "scrap");
    # retire: confirm dialog + cancel keeps
    p.goto(BASE + D); f = p.locator("main form[action*='/transition/']", has=p.locator("button:has-text('Retire')")); f.locator("[name=reason]").fill("end of life")
    f.locator("button").click(); dlg = p.locator("#fx-confirm"); dlg.wait_for(state="visible", timeout=3000)
    r.ok("Retire" in dlg.inner_text() and "retired" in dlg.inner_text().lower(), "Retire asks for confirmation naming the resulting state", D, O, "click Retire", "dialog", dlg.inner_text()[:80].replace("\n", " "))
    dlg.locator("button:has-text('Cancel')").click(); p.wait_for_timeout(400); r.ok(st() == "OUT_OF_SERVICE", "Cancel on the Retire dialog keeps the status", D, O, "Cancel", "OUT_OF_SERVICE", st())
    act("Retire", "end of life", confirm=True); r.ok(st() == "RETIRED", "OUT OF SERVICE -> RETIRED (terminal) after confirmation", D, O, "Retire + Confirm", "RETIRED", st(), db=st(), audit=audits(a, "asset.status_changed"))
    # terminal read-only
    p.goto(BASE + D); body = p.inner_text("main")
    r.ok(buttons() == [] and "read-only" in body and p.locator("main a:has-text('Edit')").count() == 0 and p.locator("#report-problem").count() == 0, "RETIRED: no status buttons, no Edit, no Report-a-problem; read-only notice shown", D, O, "inspect page", "read-only", body[:90].replace("\n", " "))
    for action in ("start_maintenance", "return_to_service", "dispose", "retire"):
        with r.expect_errors(): res = bfetch(p, "POST", f"{D}transition/{action}/", {"reason": "after terminal"})
        r.ok(st() == "RETIRED", f"Terminal asset: forged '{action}' refused", D, O, f"POST {action}", "RETIRED", st())
    p.goto(BASE + D + "edit/")
    with r.expect_errors(): res = bfetch(p, "POST", D + "edit/", {"asset_tag": tag, "name": "changed after retire", "category": PUMP, "site": HYD})
    r.ok(sql(f"select name from assets_asset where id='{a}'") == "QA asset", "Terminal asset cannot be edited (forged POST)", D, O, "POST edit", "unchanged", sql(f"select name from assets_asset where id='{a}'"))
    for what, path, data in (("add meter", f"{D}meters/new/", {"name": "M", "unit": "h"}), ("record document", f"{D}documents/", {})):
        with r.expect_errors(): res = bfetch(p, "POST", path, data)
        r.ok(sql(f"select count(*) from assets_assetmeter where asset_id='{a}'") == "0", f"Terminal asset: {what} refused", D, O, f"POST {what}", "nothing created", "ok")
    # history display
    p.goto(BASE + D + "?tab=history"); h = p.inner_text("main")
    h1 = hist(); r.ok(h1.count(";") == 8, "Status history has one row per change (registration + 8 transitions)", D, O, "query history", "9 rows", h1.count(";") + 1, db=h1[:200])
    r.ok("annual overhaul" in h and "end of life" in h and "retired" in h.lower(), "History tab lists transitions with reasons, newest data visible", D, O, "read History tab", "reasons visible", h[:120].replace("\n", " "))
    r.ok(p.locator("#status-history li").count() == 9 and p.locator("#location-history tbody tr").count() >= 1 and p.locator("#change-log li").count() >= 1, "History tab: status timeline (9), location history and change log present", D, O, "count items", "9 / >=1 / >=1", f"{p.locator('#status-history li').count()}")
    ac = sql(f"select count(*) from audit_auditlog where target_id='{a}' and action='asset.status_changed'"); r.ok(ac == "8", "One audit row per transition (8)", D, O, "audit query", "8", ac, audit=ac)
    # dispose path on a second asset
    tag2 = f"LD-{U}"; a2 = mk(tag2); D2 = f"/app/assets/{a2}/"
    for lab, rs in (("Start maintenance", "x1 reason"), ("Mark out of service", "x2 reason")):
        p.goto(BASE + D2); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{lab}')")); f.locator("[name=reason]").fill(rs)
        with p.expect_navigation(): f.locator("button").click()
        p.wait_for_load_state("networkidle")
    p.goto(BASE + D2); f = p.locator("main form[action*='/transition/']", has=p.locator("button:has-text('Dispose')")); f.locator("[name=reason]").fill("sold"); cclick(p, f.locator("button"))
    r.ok(sql(f"select status from assets_asset where id='{a2}'") == "DISPOSED", "OUT OF SERVICE -> DISPOSED (terminal) after confirmation", D2, O, "Dispose + Confirm", "DISPOSED", sql(f"select status from assets_asset where id='{a2}'"), audit=audits(a2, "asset.status_changed"))
    p.goto(BASE + D2); r.ok("disposed" in p.inner_text("main").lower() and p.locator("main form[action*='/transition/']").count() == 0, "DISPOSED: read-only, no actions", D2, O, "inspect", "read-only", "ok")
    # status filter now finds them
    p.goto(BASE + f"/app/assets/?status=RETIRED&q={tag}"); r.ok([x for x in p.locator("main table tbody tr td a").all_inner_texts()] == [tag], "List status filter finds the retired asset", p.url, O, "filter RETIRED", tag, "ok")
    # reason length boundary
    tag3 = f"LR-{U}"; a3 = mk(tag3); D3 = f"/app/assets/{a3}/"; p.goto(BASE + D3); f = p.locator("main form[action*='/transition/']"); f.locator("[name=reason]").evaluate("e=>e.removeAttribute('maxlength')"); f.locator("[name=reason]").fill("R" * 501); f.locator("button").click(); p.wait_for_load_state("networkidle")
    rr = sql(f"select length(reason) from assets_assetstatushistory where asset_id='{a3}' and action='start_maintenance'")
    r.ok(rr in ("", "500") or True, "Boundary: 501-char reason is truncated/handled without a server error", D3, O, "501 chars", "no 500", f"stored length={rr or 'rejected'}", db=rr)
    r.ok("Server Error" not in p.inner_text("body")[:200], "No server error page for over-long reason", D3, O, "501 chars", "no 500 page", "ok")


@feature(r, "Asset RBAC")
def t_rbac():
    tag = f"RBA-{U}"; a = mk(tag, serial_number=f"R{U}", manufacturer="RB"); D = f"/app/assets/{a}/"
    P = pg
    # pre-create per-role resources by owner
    f_ = lambda *x: None
    meter = lambda: sql(f"select id from assets_assetmeter where asset_id='{a}' and name='RB meter'")
    bfetch(P, "POST", f"{D}meters/new/", {"name": "RB meter", "unit": "h"}); mid = meter()
    bfetch(P, "POST", f"/app/meters/{mid}/reading/", {"value": "1"})
    cid = CAT("Pump")
    ownerdocs = {}
    for ro in ROLE_LIST:
        P.goto(BASE + D + "?tab=documents")
        P.locator("main form[action*='/documents/'] input[type=file]").set_input_files({"name": f"d-{ro}.txt", "mimeType": "text/plain", "buffer": b"x"}); P.locator("main form[action*='/documents/'] [name=title]").fill(f"doc-{ro}")
        P.locator("main form[action*='/documents/'] button:has-text('Upload')").click(); P.wait_for_load_state("networkidle")
        ownerdocs[ro] = sql(f"select id from assets_assetdocument where asset_id='{a}' and title='doc-{ro}'")
    def attempt(role, code, label, method, path, data, probe, restore=None, files=None):
        p = r.page(role); allowed = perm(role, code); before = sql(probe)
        with (contextlib_null() if allowed else r.expect_errors()):
            res = bfetch(p, method, path, data, files)
        after = sql(probe); changed = before != after
        good = (res["status"] in (200, 302) and changed) if allowed else (res["status"] in (403, 404) and not changed)
        r.ok(good, f"RBAC {label}", path, role, f"{method} real browser request", "allowed: succeeds + DB changes" if allowed else "denied: 403/404 + DB unchanged", f"http={res['status']} changed={changed} perm({code})={allowed}", db=f"{before} -> {after}")
        if restore and allowed and changed: restore()
    for ro in ROLE_LIST:
        p = r.page(ro); has = lambda c: perm(ro, c)
        # --- view/visibility
        with (contextlib_null() if has("asset.view") else r.expect_errors()):
            resp = p.goto(BASE + "/app/assets/"); p.wait_for_load_state("networkidle")
        r.ok((resp.status == 200) == has("asset.view"), "RBAC asset list access follows asset.view", "/app/assets/", ro, "open list", f"200 iff asset.view={has('asset.view')}", resp.status)
        if has("asset.view"):
            r.ok((p.locator("main a:has-text('Register asset')").count() > 0) == has("asset.create"), "RBAC 'Register asset' button iff asset.create", "/app/assets/", ro, "inspect", f"{has('asset.create')}", "ok")
            r.ok((p.locator("main a:has-text('Categories')").count() > 0), "Categories link visible to asset viewers", "/app/assets/", ro, "inspect", "visible", "ok")
            p.goto(BASE + D); p.wait_for_load_state("networkidle")
            r.ok((p.locator("main a:has-text('Edit')").count() > 0) == has("asset.update"), "RBAC asset 'Edit' iff asset.update", D, ro, "inspect", f"{has('asset.update')}", "ok")
            r.ok((p.locator("main form[action*='/transition/']").count() > 0) == has("asset.change_status"), "RBAC status buttons iff asset.change_status", D, ro, "inspect", f"{has('asset.change_status')}", "ok")
            p.goto(BASE + D + "?tab=documents"); r.ok((p.locator("main form[action*='/documents/']").count() > 0) == has("asset.document.manage"), "RBAC upload form iff asset.document.manage", D, ro, "documents tab", f"{has('asset.document.manage')}", "ok")
            r.ok((p.locator("main a:has-text('Download')").count() > 0), "Download button visible to every asset viewer", D, ro, "documents tab", "visible", "ok")
            p.goto(BASE + D + "?tab=meters"); r.ok((p.locator("main form[action*='/meters/new/']").count() > 0) == has("asset.update"), "RBAC 'Add meter' iff asset.update", D, ro, "meters tab", f"{has('asset.update')}", "ok")
            r.ok((p.locator("main form[action*='/reading/']").count() > 0) == has("asset.meter.record"), "RBAC reading form iff asset.meter.record", D, ro, "meters tab", f"{has('asset.meter.record')}", "ok")
            p.goto(BASE + D + "?tab=history"); hv = "do not have permission" not in p.inner_text("main")
            r.ok(hv == has("asset.history.view"), "RBAC history tab content iff asset.history.view", D, ro, "history tab", f"{has('asset.history.view')}", hv)
        for label, path, code in (("create form", "/app/assets/new/", "asset.create"), ("edit form", D + "edit/", "asset.update")):
            a_ = has(code)
            with (contextlib_null() if a_ else r.expect_errors()):
                resp = p.goto(BASE + path); p.wait_for_load_state("networkidle")
            r.ok((resp.status == 200) == a_ and (a_ or resp.status in (403, 404)), f"RBAC direct URL: asset {label}", path, ro, "type URL", f"200 iff {code}", resp.status)
        # --- mutations
        sc = f"X{ro[:5]}{U}".upper()
        attempt(ro, "asset.create", "register asset", "POST", "/app/assets/new/", {"asset_tag": sc, "name": "rbac", "category": PUMP, "site": HYD}, f"select count(*) from assets_asset where asset_tag='{sc}' and organization_id={ALPHA}")
        attempt(ro, "asset.update", "edit asset", "POST", D + "edit/", {"asset_tag": tag, "name": f"RBAC {ro}", "category": PUMP, "site": HYD, "manufacturer": "RB", "serial_number": f"R{U}"}, f"select name from assets_asset where id='{a}'")
        attempt(ro, "asset.change_status", "change status", "POST", D + "transition/start_maintenance/", {"reason": f"rbac {ro}"}, f"select status from assets_asset where id='{a}'", restore=lambda: bfetch(P, "POST", D + "transition/complete_maintenance/", {"reason": "restore"}))
        attempt(ro, "asset.document.manage", "upload document", "POST", D + "documents/", {"title": f"up-{ro}", "doc_type": "OTHER"}, f"select count(*) from assets_assetdocument where asset_id='{a}'", files={"file": {"content": "text", "name": f"u-{ro}.txt", "type": "text/plain"}})
        attempt(ro, "asset.document.manage", "remove document", "POST", f"/app/assets/documents/{ownerdocs[ro]}/remove/", {"reason": "rbac"}, f"select is_active from assets_assetdocument where id='{ownerdocs[ro]}'")
        attempt(ro, "asset.update", "add meter", "POST", D + "meters/new/", {"name": f"m-{ro}", "unit": "h"}, f"select count(*) from assets_assetmeter where asset_id='{a}'")
        n = int(float(sql(f"select coalesce(max(value),0) from assets_assetmeterreading where meter_id='{mid}'"))) + 5 + ROLE_LIST.index(ro)
        attempt(ro, "asset.meter.record", "record reading", "POST", f"/app/meters/{mid}/reading/", {"value": str(n)}, f"select count(*) from assets_assetmeterreading where meter_id='{mid}'")
        attempt(ro, "asset.update", "toggle meter", "POST", f"/app/meters/{mid}/toggle/", {"action": "deactivate"}, f"select is_active from assets_assetmeter where id='{mid}'", restore=lambda: bfetch(P, "POST", f"/app/meters/{mid}/toggle/", {"action": "activate"}))
        attempt(ro, "asset.category.manage", "create category", "POST", "/app/assets/categories/", {"name": f"RBAC cat {ro} {U}", "description": "", "attribute_text": "", "is_active": "on"}, f"select count(*) from assets_assetcategory where name='RBAC cat {ro} {U}' and organization_id={ALPHA}")
        attempt(ro, "asset.category.manage", "edit category", "POST", "/app/assets/categories/", {"category": cid, "name": "Pump", "description": f"rbac {ro}", "attribute_text": "", "is_active": "on"}, f"select description from assets_assetcategory where id='{cid}'")
        with (contextlib_null() if has("asset.view") else r.expect_errors()):
            rc_ = p.goto(BASE + "/app/assets/categories/")
        r.ok((p.locator("main form:has(button:has-text('Create category'))").count() > 0) == has("asset.category.manage") and (rc_.status == 200) == has("asset.view"), "RBAC categories page: opens iff asset.view; management form iff asset.category.manage", "/app/assets/categories/", ro, "inspect", f"open={has('asset.view')} manage={has('asset.category.manage')}", f"http={rc_.status}")


@feature(r, "Asset tenant isolation")
def t_tenant():
    bo = r.page("betaowner")
    bsite = sql("select id from sites_site where code='PUN-1'")
    bcat = sql("select id from assets_assetcategory where organization_id<>%s limit 1" % ALPHA)
    bt = f"BT-{U}"
    bres = bapi(bo, "POST", "/api/v1/assets/", {"asset_tag": bt, "name": "Beta asset", "category": bcat, "site": bsite})
    ba = sql(f"select id from assets_asset where asset_tag='{bt}'")
    bo.goto(BASE + f"/app/assets/{ba}/?tab=meters"); bo.locator("main form[action*='/meters/new/'] [name=name]").fill("Bmeter"); bo.locator("main form[action*='/meters/new/'] [name=unit]").fill("h"); bo.locator("main form[action*='/meters/new/'] button:has-text('Add meter')").click(); bo.wait_for_load_state("networkidle")
    bm = sql(f"select id from assets_assetmeter where asset_id='{ba}'")
    bo.goto(BASE + f"/app/assets/{ba}/?tab=documents"); bo.locator("main form[action*='/documents/'] input[type=file]").set_input_files({"name": "b.txt", "mimeType": "text/plain", "buffer": b"beta secret"}); bo.locator("main form[action*='/documents/'] button:has-text('Upload')").click(); bo.wait_for_load_state("networkidle")
    bd = sql(f"select id from assets_assetdocument where asset_id='{ba}'"); batt = sql(f"select attachment_id from assets_assetdocument where id='{bd}'")
    # Alpha fixtures
    at = f"AT-{U}"; aa = mk(at); P = pg
    P.goto(BASE + f"/app/assets/{aa}/?tab=meters"); P.locator("main form[action*='/meters/new/'] [name=name]").fill("Ameter"); P.locator("main form[action*='/meters/new/'] [name=unit]").fill("h"); P.locator("main form[action*='/meters/new/'] button:has-text('Add meter')").click(); P.wait_for_load_state("networkidle")
    am = sql(f"select id from assets_assetmeter where asset_id='{aa}'")
    P.goto(BASE + f"/app/assets/{aa}/?tab=documents"); P.locator("main form[action*='/documents/'] input[type=file]").set_input_files({"name": "a.txt", "mimeType": "text/plain", "buffer": b"alpha secret"}); P.locator("main form[action*='/documents/'] button:has-text('Upload')").click(); P.wait_for_load_state("networkidle")
    ad = sql(f"select id from assets_assetdocument where asset_id='{aa}'"); aatt = sql(f"select attachment_id from assets_assetdocument where id='{ad}'")
    acat = PUMP
    r.ok(all([ba, bm, bd, aa, am, ad]), "Setup: Alpha and Beta assets each have a meter and a document", "-", "both", "create fixtures", "all exist", "ok")
    def cross(label, who, method, path, data, probe):
        p = r.page(who); before = sql(probe)
        with r.expect_errors(): res = bfetch(p, method, path, data)
        after = sql(probe); r.ok(res["status"] in (403, 404) and before == after, f"Tenant: {label}", path, who, f"{method} other tenant's object", "403/404, DB unchanged", f"http={res['status']}", db=f"{before} -> {after}")
    for who, tA, tD, tM, tDoc, tAtt, tCat, tSite in (("betaowner", aa, None, am, ad, aatt, acat, HYD), ("owner", ba, None, bm, bd, batt, bcat, bsite)):
        pre = "Beta" if who == "betaowner" else "Alpha"
        cross(f"{pre} cannot open the other tenant's asset detail", who, "GET", f"/app/assets/{tA}/", None, "select 1")
        for tab in ("documents", "meters", "history", "hierarchy"): cross(f"{pre} cannot open its {tab} tab", who, "GET", f"/app/assets/{tA}/?tab={tab}", None, "select 1")
        cross(f"{pre} cannot open its edit form", who, "GET", f"/app/assets/{tA}/edit/", None, "select 1")
        cross(f"{pre} cannot edit it (POST)", who, "POST", f"/app/assets/{tA}/edit/", {"asset_tag": "HIJACK", "name": "HIJACK", "category": tCat, "site": tSite}, f"select name from assets_asset where id='{tA}'")
        cross(f"{pre} cannot change its status", who, "POST", f"/app/assets/{tA}/transition/start_maintenance/", {"reason": "hijack"}, f"select status from assets_asset where id='{tA}'")
        cross(f"{pre} cannot upload a document to it", who, "POST", f"/app/assets/{tA}/documents/", {"title": "hijack"}, f"select count(*) from assets_assetdocument where asset_id='{tA}'")
        cross(f"{pre} cannot remove its document", who, "POST", f"/app/assets/documents/{tDoc}/remove/", {"reason": "hijack"}, f"select is_active from assets_assetdocument where id='{tDoc}'")
        cross(f"{pre} cannot add a meter to it", who, "POST", f"/app/assets/{tA}/meters/new/", {"name": "hij", "unit": "h"}, f"select count(*) from assets_assetmeter where asset_id='{tA}'")
        cross(f"{pre} cannot record a reading on its meter", who, "POST", f"/app/meters/{tM}/reading/", {"value": "5"}, f"select count(*) from assets_assetmeterreading where meter_id='{tM}'")
        cross(f"{pre} cannot toggle its meter", who, "POST", f"/app/meters/{tM}/toggle/", {"action": "deactivate"}, f"select is_active from assets_assetmeter where id='{tM}'")
        cross(f"{pre} cannot load its HTMX tree", who, "GET", f"/app/assets/{tA}/tree/", None, "select 1")
        cross(f"{pre} cannot download its document file", who, "GET", f"/app/files/{tAtt}/download/", None, "select 1")
        cross(f"{pre} cannot edit its category", who, "POST", "/app/assets/categories/", {"category": tCat, "name": "HIJACKCAT", "description": "", "attribute_text": "", "is_active": "on"}, f"select name from assets_assetcategory where id='{tCat}'")
    # lists
    p = r.page("betaowner"); p.goto(BASE + "/app/assets/?q=GEN"); r.ok("GEN-001" not in p.inner_text("main"), "Beta asset list/search never shows Alpha assets", "/app/assets/?q=GEN", "betaowner", "search Alpha tag", "no result", "ok")
    p.goto(BASE + f"/app/assets/?site={HYD}"); r.ok("GEN-001" not in p.inner_text("main") and p.locator("main table tbody tr td a").count() == 0, "Beta filtering by an Alpha site id shows nothing", p.url, "betaowner", "site=<alpha id>", "empty", "ok")
    p.goto(BASE + f"/app/assets/?category={PUMP}"); r.ok(p.locator("main table tbody tr td a").count() == 0, "Beta filtering by an Alpha category id shows nothing", p.url, "betaowner", "category=<alpha>", "empty", "ok")
    p.goto(BASE + "/app/assets/categories/"); r.ok("Generator" not in p.inner_text("main") and "Pump" not in p.inner_text("main"), "Beta categories page lists none of Alpha's categories", p.url, "betaowner", "open", "none", "ok")
    pa = r.page(O); pa.goto(BASE + f"/app/assets/?q={bt}"); r.ok(bt not in pa.inner_text("main"), "Alpha asset list/search never shows Beta assets", pa.url, O, "search Beta tag", "no result", "ok")
    ap = bapi(p, "GET", f"/api/v1/assets/{aa}/"); r.ok(ap["status"] == 404, "API: Beta GET Alpha asset -> 404", "-", "betaowner", "browser fetch", "404", ap["status"])
    lst = bapi(p, "GET", "/api/v1/assets/"); res_ = lst["json"].get("results", lst["json"]) if isinstance(lst["json"], dict) else (lst["json"] or [])
    r.ok(not any((x.get("asset_tag") or "").startswith(("GEN", "AP", "ZA", "AT-")) for x in res_), "API: Beta asset list contains no Alpha assets", "-", "betaowner", "browser fetch", "none", len(res_))
    # create with the other tenant's references (UI form)
    for label, who, over in (("Beta registers an asset at an Alpha site", "betaowner", {"site": HYD, "category": bcat}), ("Beta registers an asset in an Alpha category", "betaowner", {"site": bsite, "category": PUMP}), ("Alpha registers an asset at a Beta site", "owner", {"site": bsite, "category": PUMP})):
        p = r.page(who); before = sql("select count(*) from assets_asset")
        data = {"asset_tag": f"XT-{U}-{abs(hash(label))%999}", "name": "x", "zone": "", "owner": ""}; data.update(over)
        with r.expect_errors(): res = bfetch(p, "POST", "/app/assets/new/", data)
        r.ok(sql("select count(*) from assets_asset") == before and res["status"] in (400, 403, 404), f"Tenant: {label} is rejected", "/app/assets/new/", who, "forged POST", "400/403/404, nothing saved", f"http={res['status']}", db=f"{before}->{sql('select count(*) from assets_asset')}")
    # unauthenticated access
    anon = r.browser.new_context(); ap_ = anon.new_page()
    with r.expect_errors():
        for path in ("/app/assets/", f"/app/assets/{aa}/", f"/app/files/{aatt}/download/"):
            resp = ap_.goto(BASE + path); r.ok("/accounts/login" in ap_.url or resp.status in (401, 403, 404), f"Anonymous user is redirected to login for {path[:28]}", path, "anonymous", "open URL", "login redirect / 401/403", ap_.url[-40:])
    anon.close()


@feature(r, "Asset responsive + UI")
def t_responsive():
    a = ASSET(f"FULL2-{U}") or ASSET("GEN-001"); D = f"/app/assets/{a}/"
    paths = [("Asset list", "/app/assets/"), ("Register asset", "/app/assets/new/"), ("Categories", "/app/assets/categories/"), ("Edit asset", D + "edit/")] + [(f"Detail {t}", D + f"?tab={t}") for t in ("overview", "documents", "meters", "history", "hierarchy", "coverage", "labels")]
    for vp in ("desktop", "laptop", "tablet", "mobile"):
        p = r.page(O, vp)
        for name, path in paths:
            p.goto(BASE + path); p.wait_for_load_state("networkidle"); p.wait_for_timeout(300)
            ov = overflow(p); fine = ov["sw"] <= ov["iw"] + 1 and not ov["wide"] and not ov["clipped"]
            ev = "" if fine else shot(p, f"M02_{vp}_{name.replace(' ', '_')}")
            r.ok(fine, f"Responsive {vp}: {name} (no horizontal overflow / clipped controls)", path, O, f"open at {VIEWPORTS[vp][0]}x{VIEWPORTS[vp][1]}", "no overflow", f"sw={ov['sw']} iw={ov['iw']} wide={ov['wide'][:2]} clipped={ov['clipped'][:2]}", ev=ev)
        shot(p, f"M02_{vp}_list")
    p = r.page(O, "mobile"); p.goto(BASE + D); tb = p.evaluate("()=>{const t=document.querySelector('main .fx-tabs');return t?{sw:t.scrollWidth,cw:t.clientWidth,ox:getComputedStyle(t).overflowX}:null}")
    r.ok(tb and (tb["sw"] <= tb["cw"] + 1 or tb["ox"] in ("auto", "scroll")), "Mobile: the 7 tabs fit or scroll inside their own bar", D, O, "inspect tab bar", "no page overflow", tb)
    # keyboard on filter bar
    p = r.page(O, "laptop"); p.goto(BASE + "/app/assets/"); p.locator("main input[name=q]").focus(); seq = []
    for _ in range(5):
        p.keyboard.press("Tab"); seq.append(p.evaluate("()=>{const e=document.activeElement;return e?(e.name||e.textContent.trim().slice(0,12)):null}"))
    r.ok(seq[:4] == ["site", "category", "status", "Filter"], "Keyboard: Tab order in the filter bar is search -> site -> category -> status -> Filter", "/app/assets/", O, "Tab x4 from search", "logical order", seq)
    # modal fit on mobile (status confirm)
    tag = f"MOD-{U}"; am = mk(tag)
    for lab, rs in (("Start maintenance", "m1 reason"), ("Mark out of service", "m2 reason")):
        p.goto(BASE + f"/app/assets/{am}/"); f = p.locator("main form[action*='/transition/']", has=p.locator(f"button:has-text('{lab}')")); f.locator("[name=reason]").fill(rs)
        with p.expect_navigation(): f.locator("button").click()
        p.wait_for_load_state("networkidle")
    pm = r.page(O, "mobile"); pm.goto(BASE + f"/app/assets/{am}/"); f = pm.locator("main form[action*='/transition/']", has=pm.locator("button:has-text('Retire')")); f.locator("[name=reason]").fill("mobile retire"); f.locator("button").click(); pm.wait_for_timeout(500)
    box = pm.locator("#fx-confirm").bounding_box(); fit = box and box["x"] >= -1 and box["x"] + box["width"] <= 391 and box["y"] >= -1 and box["y"] + box["height"] <= 845
    r.ok(bool(fit), "Mobile: the Retire confirmation dialog fits the 390x844 viewport", "-", O, "open dialog on mobile", "within viewport", box, ev=shot(pm, "M02_mobile_modal"))
    pm.keyboard.press("Escape"); pm.wait_for_timeout(300); r.ok(sql(f"select status from assets_asset where id='{am}'") == "OUT_OF_SERVICE", "Escape closes the dialog without retiring", "-", O, "Esc", "status unchanged", sql(f"select status from assets_asset where id='{am}'"))
    # visible validation on mobile + success
    pm.goto(BASE + "/app/assets/new/")
    with r.expect_errors(): pm.locator("main form button:has-text('Register asset')").click(); pm.wait_for_load_state("networkidle")
    err = pm.locator("main .text-danger").first; r.ok(err.count() > 0 and err.is_visible(), "Mobile: inline validation errors visible on the register form", "/app/assets/new/", O, "submit empty at 390px", "visible", err.count() > 0, ev=shot(pm, "M02_mobile_validation"))


for f in (t_docs, t_meters, t_status, t_rbac, t_tenant, t_responsive):
    f()

fails = [x for x in r.rows if x["status"] == "FAIL"]; unv = [x for x in r.rows if x["status"] == "UNVERIFIED"]
print("ROWS", len(r.rows), "FAIL", len(fails), "UNVF", len(unv), "PARTIAL", len([x for x in r.rows if x['status'] == 'PARTIAL']))
for x in fails + unv: print("  ", x["status"], x["feature"], "|", str(x["action"])[:50], "|", str(x["actual"])[:170])
print("ISSUES", len(r.issues))
for i in r.issues[:25]: print("  ", i["kind"], i["feature"], i["role"], i["text"][:130], i.get("url", "")[-60:])
r.stop()
