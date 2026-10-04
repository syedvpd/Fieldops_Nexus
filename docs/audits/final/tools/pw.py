import os, re, json
from playwright.sync_api import sync_playwright
S=open('/tmp/claude-0/audit/S').read().strip()
BASE="http://127.0.0.1:8098"
CREDS={}
for l in open(S+"/.env.browser-qa-users"):
    if "=" in l and not l.startswith("#"):
        k,v=l.strip().split("=",1); CREDS[k]=v
def launch(p):
    exe=None
    for c in ["/opt/pw-browsers/chromium-1194/chrome-linux/chrome","/opt/pw-browsers/chromium"]:
        if os.path.exists(c): exe=c;break
    return p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
def login(ctx, email):
    pg=ctx.new_page()
    pg.goto(BASE+"/accounts/login/")
    pg.fill("input[name=username]", email); pg.fill("input[name=password]", CREDS[email])
    pg.click("form button.btn-primary")
    pg.wait_for_load_state("networkidle")
    return pg

RESULTS=[]
def rec(mod, scenario, status, note="", evidence=""):
    RESULTS.append(dict(module=mod, scenario=scenario, status=status, note=note, evidence=evidence))
    print(f"[{status}] {mod} | {scenario} | {note}"[:300])
    with open(S+"/browser_results.jsonl","a") as f: f.write(json.dumps(RESULTS[-1])+"\n")

def forms(pg):
    return pg.evaluate("""()=>[...document.querySelectorAll('form')].map(f=>({action:f.getAttribute('action'),method:f.method,
      fields:[...f.querySelectorAll('input,select,textarea,button')].map(e=>({tag:e.tagName,name:e.name,type:e.type,
        req:e.required,opts:e.tagName=='SELECT'?[...e.options].slice(0,12).map(o=>o.value+':'+o.text.trim()):undefined,text:e.tagName=='BUTTON'?e.innerText.trim():undefined}))}))""")
def dump(pg, forms_only=False):
    print("URL",pg.url,"|",pg.title())
    for f in forms(pg):
        print(" FORM",f['method'],f['action'])
        for x in f['fields']:
            if x['name'] in ('csrfmiddlewaretoken',): continue
            print("   ",x)
    if not forms_only:
        print(" TEXT:",pg.inner_text("main")[:1500].replace("\n"," | "))
def fill(pg, values, scope="main form"):
    for k,v in values.items():
        loc=pg.locator(f"{scope} [name='{k}']").first
        tag=loc.evaluate("e=>e.tagName"); typ=loc.evaluate("e=>e.type")
        if tag=="SELECT":
            try: loc.select_option(label=v) if not str(v).startswith("value:") else loc.select_option(value=v[6:])
            except Exception: loc.select_option(value=str(v))
        elif typ=="checkbox":
            loc.set_checked(bool(v))
        elif typ=="file": loc.set_input_files(v)
        else: loc.fill(str(v))
def msgs(pg):
    return " || ".join(t.strip() for t in pg.locator(".alert, .invalid-feedback, .text-danger, .errorlist").all_inner_texts() if t.strip())
class Mon:
    def __init__(self, pg):
        self.console=[]; self.failed=[]; self.bad=[]
        pg.on("console", lambda m: self.console.append((m.type,m.text[:200])) if m.type in ("error",) else None)
        pg.on("pageerror", lambda e: self.console.append(("pageerror",str(e)[:200])))
        pg.on("requestfailed", lambda r: self.failed.append((r.url,r.failure)))
        pg.on("response", lambda r: self.bad.append((r.status,r.url)) if r.status>=400 else None)

import subprocess
def sql(q):
    r=subprocess.run(["psql","postgres://fieldops:test_only@localhost:5432/fieldops_browser_qa","-At","-F","|","-c",q],capture_output=True,text=True)
    return (r.stdout+r.stderr).strip()

import time
R=str(int(time.time())%100000)
def audits(tid):
    return sql(f"select action from audit_auditlog where target_id='{tid}' order by occurred_at").replace("\n",",")

VIEWPORTS={"desktop":(1920,1080),"laptop":(1440,900),"tablet":(1024,768),"mobile":(390,844)}
def overflow(pg):
    return pg.evaluate("()=>({sw:document.documentElement.scrollWidth,iw:window.innerWidth,wide:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.right>window.innerWidth+1&&r.width>0&&!e.closest('.table-responsive,.overflow-auto,.overflow-x-auto,pre')}).slice(0,3).map(e=>e.tagName+'.'+e.className.toString().slice(0,40))})")
def responsive(browser, email, paths, mod):
    for vp,(w,h) in VIEWPORTS.items():
        ctx=browser.new_context(viewport={"width":w,"height":h}); pg=login(ctx,email)
        bad=[]
        for path in paths:
            pg.goto(BASE+path); pg.wait_for_load_state("networkidle")
            o=overflow(pg)
            if o['sw']>o['iw']+1 or o['wide']: bad.append((path,o))
        rec(mod,f"Responsive {vp} {w}x{h}: no horizontal overflow on {len(paths)} pages","PASS" if not bad else "FAIL",str(bad)[:300])
        pg.screenshot(path=f"shots/{mod}_{vp}.png"); ctx.close()

def cclick(pg, locator):
    """click a button that may be guarded by the app's confirm dialog, then confirm."""
    locator.click()
    dlg=pg.locator("#fx-confirm")
    try:
        if dlg.is_visible(timeout=2500):
            dlg.locator("button:has-text('Confirm')").click()
    except Exception: pass
    pg.wait_for_load_state("networkidle")

def post(ctx, path, data=None, files=None):
    """crafted form POST with valid CSRF (browser session) -> (status, text)"""
    ck={c['name']:c['value'] for c in ctx.cookies()}
    r=ctx.request.post(BASE+path, form=data or {}, headers={"X-CSRFToken":ck.get("csrftoken",""),"Referer":BASE+"/"}, max_redirects=0)
    return r.status, r.text()[:300]
def api(ctx, method, path, data=None, org=None):
    ck={c['name']:c['value'] for c in ctx.cookies()}
    h={"X-CSRFToken":ck.get("csrftoken",""),"Referer":BASE+"/"}
    if org: h["X-Organization"]=org
    f=getattr(ctx.request,method)
    r=f(BASE+path, data=json.dumps(data) if data is not None else None, headers={**h,"Content-Type":"application/json"}, max_redirects=0) if method!="get" else f(BASE+path, headers=h)
    try: j=r.json()
    except Exception: j=r.text()[:200]
    return r.status, j

def mk_asset(pg, tag, name, cat="Pump", site="HYD-1 · Hyderabad Operations Site", zone=None):
    pg.goto(BASE+"/app/assets/new/"); v=dict(asset_tag=tag,name=name,category=cat,site=site)
    if zone: v["zone"]=zone
    fill(pg,v); pg.click("main form button:has-text('Register asset')"); pg.wait_for_load_state()
    return sql(f"select id from assets_asset where asset_tag='{tag}'")
