"""Batch-1 browser acceptance harness: role contexts, console/network capture, coverage tracking, test matrix."""
import json, os, re, subprocess, time, contextlib
from playwright.sync_api import sync_playwright

S = open('/tmp/claude-0/audit/S').read().strip()
BASE = "http://127.0.0.1:8098"
OUT = S + "/batch1"
os.makedirs(OUT, exist_ok=True)
CREDS = {}
for l in open(S + "/.env.browser-qa-users"):
    if "=" in l and not l.startswith("#"):
        k, v = l.strip().split("=", 1); CREDS[k] = v
ROLES = {"owner": "owner@alpha.qa.test", "admin": "admin@alpha.qa.test", "ops": "ops@alpha.qa.test", "supervisor": "supervisor@alpha.qa.test",
         "assets": "assets@alpha.qa.test", "planner": "planner@alpha.qa.test", "tech": "tech1@alpha.qa.test", "tech2": "tech2@alpha.qa.test",
         "stores": "stores@alpha.qa.test", "service": "service@alpha.qa.test", "auditor": "auditor@alpha.qa.test", "client": "client@alpha.qa.test",
         "betaowner": "owner@beta.qa.test", "betatech": "tech@beta.qa.test"}
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
VIEWPORTS = {"desktop": (1920, 1080), "laptop": (1440, 900), "tablet": (1024, 768), "mobile": (390, 844)}
RUN = time.strftime("%H%M%S")


def sql(q):
    r = subprocess.run(["psql", "postgres://fieldops:test_only@localhost:5432/fieldops_browser_qa", "-At", "-F", "|", "-c", q], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def norm(u):
    u = u.replace(BASE, "").split("#")[0]
    path, _, q = u.partition("?")
    path = UUID.sub("{id}", path)
    path = re.sub(r"/s/[A-Za-z0-9_-]{8,}/", "/s/{token}/", path)
    return path + (("?" + "&".join(sorted(p.split("=")[0] for p in q.split("&") if p))) if q else "")


CLICK_JS = """
(()=>{ if(window.__clk) return; window.__clk=1;
 document.addEventListener('click',e=>{const t=e.target.closest('a,button,input[type=submit],label,summary,[data-confirm],[hx-get],[hx-post],[role=tab]'); if(!t) return;
  const f=t.closest('form'); console.log('CLK|'+(t.tagName)+'|'+((t.innerText||t.value||t.getAttribute('aria-label')||'').trim().slice(0,40))+'|'+(f?(f.getAttribute('action')||location.pathname):'')+'|'+(t.getAttribute('href')||'')+'|'+location.pathname);},true);
 document.addEventListener('keydown',e=>{ if(e.key==='Tab') console.log('KEY|tab'); },true);
})();
"""


class Run:
    def __init__(self, module):
        self.module = module
        self.rows = []
        self.issues = []       # unexplained browser problems
        self.expected = []     # problems that were provoked deliberately
        self.cov_post = collections_Counter()
        self.cov_get = collections_Counter()
        self.clicks = collections_Counter()
        self.htmx = collections_Counter()
        self.htmx_fail = []
        self.benign = []
        self.exp = 0           # >0 while a deliberate negative is running
        self.cur = ""          # current feature label
        self.cur_role = ""
        self.pw = None; self.browser = None; self.ctxs = {}

    # ---- lifecycle
    def start(self):
        self.pw = sync_playwright().start()
        exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
        self.browser = self.pw.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        return self

    def stop(self):
        for c in list(self.ctxs.values()):
            with contextlib.suppress(Exception): c.close()
        self.browser.close(); self.pw.stop()
        self.save()

    # ---- contexts
    def ctx(self, role, vp="laptop", fresh=False):
        key = (role, vp)
        if key in self.ctxs and not fresh:
            return self.ctxs[key]
        w, h = VIEWPORTS[vp]
        c = self.browser.new_context(viewport={"width": w, "height": h})
        c.add_init_script(CLICK_JS)
        self._wire(c, role)
        pg = c.new_page()
        pg.goto(BASE + "/accounts/login/")
        pg.fill("input[name=username]", ROLES[role]); pg.fill("input[name=password]", CREDS[ROLES[role]])
        pg.click("form button.btn-primary"); pg.wait_for_load_state("networkidle")
        c._login_page = pg
        self.ctxs[key] = c
        return c

    def page(self, role, vp="laptop"):
        c = self.ctx(role, vp)
        return c._login_page

    def _wire(self, c, role):
        def on_console(m):
            t = m.text
            if t.startswith("CLK|"):
                self.clicks[t[4:]] += 1; return
            if t.startswith("KEY|"): return
            if m.type == "error":
                self._issue("console", role, t[:240], m.location.get("url", "") if hasattr(m, "location") and isinstance(m.location, dict) else "")
        def on_pageerror(e): self._issue("pageerror", role, str(e)[:240], "")
        def on_failed(r):
            self._issue("requestfailed", role, f"{r.method} {r.url[:160]} {r.failure}", r.url)
        def on_response(r):
            req = r.request
            if req.method == "POST": self.cov_post[norm(r.url)] += 1
            elif req.resource_type == "document": self.cov_get[norm(r.url)] += 1
            if req.headers.get("hx-request"):
                self.htmx[f"{req.method} {norm(r.url)}"] += 1
                if r.status >= 400: self.htmx_fail.append((self.cur, role, req.method, norm(r.url), r.status))
            if r.status >= 400:
                self._issue("http", role, f"{r.status} {req.method} {norm(r.url)}" + ((" body=" + re.sub(r"csrfmiddlewaretoken=[^&]+&?", "", req.post_data or "")[:110]) if req.method == "POST" else ""), r.url)
        c.on("console", on_console); c.on("pageerror", on_pageerror)
        c.on("requestfailed", on_failed); c.on("response", on_response)

    def _issue(self, kind, role, text, url):
        rec = dict(module=self.module, feature=self.cur, role=role, kind=kind, text=text, url=url)
        if kind == "requestfailed" and "ERR_ABORTED" in text:
            self.benign.append(rec); return          # a request cancelled by navigation (HTMX poll / unload), not a failure
        (self.expected if self.exp > 0 else self.issues).append(rec)

    @contextlib.contextmanager
    def expect_errors(self):
        self.exp += 1
        try: yield
        finally: self.exp -= 1

    # ---- matrix
    def T(self, feature, page, role, action, expected, actual, status, db="", api="", audit="", ev=""):
        row = dict(module=self.module, feature=feature, page=page, role=role, action=action, expected=expected, actual=str(actual)[:400],
                   db=str(db)[:300], api=str(api)[:200], audit=str(audit)[:200], status=status, evidence=ev)
        self.rows.append(row)
        flag = {"PASS": "PASS", "FAIL": "FAIL", "PARTIAL": "PART", "NOT APPLICABLE": "N/A", "UNVERIFIED": "UNVF"}[status]
        print(f"[{flag}] {self.module} | {feature} | {role} | {action} -> {str(actual)[:140]}")
        return status == "PASS"

    def ok(self, cond, feature, page, role, action, expected, actual="", db="", api="", audit="", ev="", partial=False):
        return self.T(feature, page, role, action, expected, actual, "PASS" if cond else ("PARTIAL" if partial else "FAIL"), db, api, audit, ev)

    def save(self):
        json.dump(dict(rows=self.rows, issues=self.issues, expected=self.expected, benign=self.benign, cov_post=self.cov_post, cov_get=self.cov_get,
                       clicks=self.clicks, htmx=self.htmx, htmx_fail=self.htmx_fail), open(f"{OUT}/{self.module}_run_{RUN}.json", "w"), indent=1)


def collections_Counter():
    import collections
    return collections.Counter()


def audits(target_id=None, action=None, since="10 minutes"):
    w = []
    if target_id: w.append(f"target_id='{target_id}'")
    if action: w.append(f"action='{action}'")
    w.append(f"occurred_at>now()-interval '{since}'")
    return sql("select string_agg(action,',' order by occurred_at) from audit_auditlog where " + " and ".join(w))


def msgs(pg):
    return " || ".join(t.strip().replace("\n", " ") for t in pg.locator(".alert, .invalid-feedback, .text-danger, .errorlist, .toast").all_inner_texts() if t.strip())[:300]


def fill(pg, values, scope="main form"):
    for k, v in values.items():
        loc = pg.locator(f"{scope} [name='{k}']").first
        tag = loc.evaluate("e=>e.tagName"); typ = loc.evaluate("e=>e.type")
        if tag == "SELECT":
            opts = loc.evaluate("e=>[...e.options].map(o=>[o.value,o.text.trim()])")
            if any(o[0] == str(v) for o in opts): loc.select_option(value=str(v))
            elif any(o[1] == str(v) for o in opts): loc.select_option(label=str(v))
            else: loc.select_option(value=str(v), timeout=2000)
        elif typ == "checkbox": loc.set_checked(bool(v))
        elif typ == "file": loc.set_input_files(v)
        else: loc.fill(str(v))


def cclick(pg, locator, wait=2500):
    locator.click()
    d = pg.locator("#fx-confirm")
    try:
        if d.is_visible(timeout=wait):
            d.locator("button:has-text('Confirm')").click(); pg.wait_for_timeout(500)
    except Exception: pass
    pg.wait_for_load_state("load"); pg.wait_for_load_state("networkidle")


def overflow(pg):
    return pg.evaluate("""()=>({sw:document.documentElement.scrollWidth,iw:window.innerWidth,
      wide:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.right>window.innerWidth+1&&!e.closest('.table-responsive,.overflow-auto,.overflow-x-auto,pre,.dropdown-menu,.offcanvas')&&getComputedStyle(e).position!=='fixed'}).slice(0,3).map(e=>e.tagName+'.'+String(e.className).slice(0,30)),
      clipped:[...document.querySelectorAll('button,a.btn,input,select,textarea')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.left<-1||r.right>window.innerWidth+1)&&!e.closest('.table-responsive,.overflow-auto,.dropdown-menu,.offcanvas')}).slice(0,3).map(e=>e.tagName+':'+(e.innerText||e.name||'').slice(0,20))})""")


INV_JS = """()=>{
 const vis=e=>{const r=e.getBoundingClientRect();const s=getComputedStyle(e);return true};
 const txt=e=>(e.innerText||e.value||e.getAttribute('aria-label')||e.title||'').trim().replace(/\\s+/g,' ').slice(0,50);
 const root=document.querySelector('main')||document.body;
 const links=[...root.querySelectorAll('a[href]')].map(a=>({t:txt(a),h:a.getAttribute('href')}));
 const nav=[...document.querySelectorAll('nav a[href], .fx-sidebar a[href], aside a[href], header a[href]')].map(a=>({t:txt(a),h:a.getAttribute('href')}));
 const buttons=[...root.querySelectorAll('button, input[type=submit], [role=button]')].map(b=>({t:txt(b),form:(b.closest('form')||{}).getAttribute?b.closest('form').getAttribute('action'):null,confirm:b.dataset.confirm||null,disabled:b.disabled,hx:b.getAttribute('hx-post')||b.getAttribute('hx-get')||null}));
 const forms=[...root.querySelectorAll('form')].map(f=>({action:f.getAttribute('action'),method:f.method,hx:f.getAttribute('hx-post')||f.getAttribute('hx-get')||null,
   fields:[...f.querySelectorAll('input,select,textarea')].filter(x=>x.type!=='hidden'||x.name==='action').map(x=>({n:x.name,type:x.type||x.tagName.toLowerCase(),req:x.required,opts:x.tagName==='SELECT'?[...x.options].length:undefined,max:x.maxLength>0&&x.maxLength<100000?x.maxLength:undefined,min:x.min||undefined,maxv:x.max||undefined}))}));
 const hx=[...root.querySelectorAll('[hx-get],[hx-post],[hx-trigger],[hx-target]')].map(e=>({tag:e.tagName,get:e.getAttribute('hx-get'),post:e.getAttribute('hx-post'),trig:e.getAttribute('hx-trigger')}));
 const tables=[...root.querySelectorAll('table')].map(t=>({heads:[...t.querySelectorAll('thead th')].map(h=>txt(h)),rows:t.querySelectorAll('tbody tr').length}));
 const tabs=[...root.querySelectorAll('[role=tab], .fx-tabs a, .nav-tabs a')].map(a=>({t:txt(a),h:a.getAttribute('href')}));
 const modals=[...document.querySelectorAll('dialog, .modal')].map(m=>m.id||m.tagName);
 return {title:document.title,h1:(root.querySelector('h1')||{}).innerText,links,nav,buttons,forms,hx,tables,tabs,modals,empty:!!root.querySelector('.fx-empty, .empty-state, [class*=empty]')};
}"""


def inventory(pg):
    return pg.evaluate(INV_JS)


ALPHA = "(select id from tenancy_organization where slug='alpha-field-services')"
def perm(role, code):
    """does the role's DB permission config grant `code` (org-wide or any site)?"""
    e = ROLES[role]
    return sql(f"select count(*) from tenancy_membership m join accounts_user u on u.id=m.user_id join rbac_membershiprole mr on mr.membership_id=m.id join rbac_rolepermission rp on rp.role_id=mr.role_id join rbac_permission p on p.id=rp.permission_id where u.email='{e}' and m.status='ACTIVE' and p.code='{code}'") not in ("0", "")


def bfetch(pg, method, path, data=None, files=None):
    """a real browser request (fetch from the page, session cookie + CSRF) -> dict(status,url,text)"""
    js = """async ([method,path,data,files])=>{
      const ck=Object.fromEntries(document.cookie.split('; ').map(c=>c.split('=')));
      const h={'X-CSRFToken':ck.csrftoken||''}; let body=undefined;
      if(files){const fd=new FormData(); for(const [k,v] of Object.entries(data||{})) fd.append(k,v);
         for(const [k,f] of Object.entries(files)) fd.append(k,new File([f.content],f.name,{type:f.type||'text/plain'})); body=fd;}
      else if(data && method!=='GET'){h['Content-Type']='application/x-www-form-urlencoded'; const u=new URLSearchParams(); for(const [k,v] of Object.entries(data)){ if(Array.isArray(v)) v.forEach(x=>u.append(k,x)); else u.append(k,v);} body=u.toString();}
      const r=await fetch(path,{method,headers:h,body,credentials:'same-origin',redirect:'follow'});
      const t=await r.text(); return {status:r.status,url:r.url,text:t.slice(0,600),html:t.slice(0,80000),ct:r.headers.get('content-type')};}"""
    return pg.evaluate(js, [method, path, data, files])


def shot(pg, name):
    p = f"{OUT}/shots"; os.makedirs(p, exist_ok=True)
    pg.screenshot(path=f"{p}/{name}.png"); return f"batch1/shots/{name}.png"


def visit(r, role, path, vp="laptop"):
    pg = r.page(role, vp)
    resp = pg.goto(BASE + path)
    pg.wait_for_load_state("networkidle")
    return resp.status if resp else None, pg


def denied(status, pg=None):
    return status in (403, 404) or (pg is not None and ("Access denied" in pg.inner_text("body")[:400] or "Not found" in pg.inner_text("body")[:400]))


def feature(run, name):
    """decorator: run one feature test; harness exceptions become UNVERIFIED rows, never silent passes"""
    def deco(fn):
        def wrapped(*a, **k):
            run.cur = name
            try: return fn(*a, **k)
            except Exception as e:
                run.T(name, "-", "-", "harness", "test completes", f"{type(e).__name__}: {str(e)[:260]}", "UNVERIFIED")
        wrapped.__name__ = fn.__name__
        return wrapped
    return deco


def bapi(pg, method, path, data=None):
    js = """async ([method,path,data])=>{const ck=Object.fromEntries(document.cookie.split('; ').map(c=>c.split('=')));
      const r=await fetch(path,{method,headers:{'X-CSRFToken':ck.csrftoken||'','Content-Type':'application/json'},body:data?JSON.stringify(data):undefined,credentials:'same-origin'});
      let j=null; try{j=await r.json()}catch(e){}; return {status:r.status,json:j};}"""
    return pg.evaluate(js, [method, path, data])


def sid(code): return sql(f"select id from sites_site where code='{code}' and organization_id={ALPHA}")
