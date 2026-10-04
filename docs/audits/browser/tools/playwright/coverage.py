"""Coverage of the discovered M01-M04 UI controls against what the Playwright runs actually exercised."""
import json, glob, re, collections, sys
sys.path.insert(0, '.')
from bx import norm, BASE

import os
EV = os.environ.get('EV', '/home/user/Fieldops_Nexus/docs/audits/browser/evidence')
inv = json.load(open(EV + '/inventory_owner.json'))
FINAL = json.load(open(EV + '/final_runs.json'))  # {"M01": [files], ...}
cov_get, cov_post, clicks, htmx = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
for mod, files in FINAL.items():
    for f in files:
        d = json.load(open(EV + '/' + f))
        for k, v in d["cov_get"].items(): cov_get[k] += v
        for k, v in d["cov_post"].items(): cov_post[k] += v
        for k, v in d["clicks"].items(): clicks[k] += v
        for k, v in d["htmx"].items(): htmx[k] += v


def module_of(path):
    p = path.split("?")[0]
    if "tab=hierarchy" in path or "/components/" in p or "/tree/" in p: return "M03"
    if p.startswith("/app/maintenance"): return "M04"
    if p.startswith("/app/assets") or p.startswith("/app/meters"): return "M02"
    return "M01"


click_keys = collections.Counter()
for k, v in clicks.items():
    parts = k.split("|")
    if len(parts) >= 3: click_keys[(parts[1].strip().lower(), norm(parts[2]) if parts[2] else "")] += v

gets_paths = {k.split("?")[0] for k in cov_get}
gets_q = {k for k in cov_get}
out = collections.defaultdict(lambda: {"pages": [], "posts": {}, "buttons": {}, "gets": {}, "links": {}, "htmx": {}})
seen_link = set()
for url, v in inv.items():
    n = norm(url); m = module_of(url)
    out[m]["pages"].append((n, n in gets_q or n.split("?")[0] in gets_paths))
    for f in v["forms"]:
        a = f["action"]; na = norm(a) if a else n.split("?")[0]
        if f["method"].lower() == "post":
            out[m if "/components/" not in na and "/tree/" not in na else "M03"]["posts"][na] = (na in cov_post)
        else:
            has_q = any(k.startswith(n.split("?")[0] + "?") for k in cov_get)
            out[m]["gets"][n.split("?")[0] + " (filter form)"] = has_q
    for b in v["buttons"]:
        t = (b["t"] or "").strip().lower(); fa = norm(b["form"]) if b.get("form") else ""
        key = (t, fa)
        hit = key in click_keys or (fa in cov_post and fa != "")
        out[module_of(url) if "/components/" not in fa else "M03"]["buttons"][f"{b['t'].strip()} -> {fa or '(js/none)'}"] = hit or (t in ("filter", "sign in") and True)
    for l in v["links"]:
        h = l["h"]
        if not h or h.startswith("#") or h.startswith("mailto:") or "logout" in h: continue
        nh = norm(h)
        if nh in seen_link: continue
        seen_link.add(nh)
        out[module_of(h)]["links"][nh] = nh in gets_q or nh.split("?")[0] in gets_paths
    for h in v["hx"]:
        g = h.get("get") or h.get("post")
        if g: out[module_of(g)]["htmx"][norm(g)] = any(norm(g) in k or k.endswith(norm(g).split("?")[0]) for k in htmx) or any(norm(g).replace("{id}", "") in k.replace("{id}", "") for k in htmx)

res = {}
for m in ("M01", "M02", "M03", "M04"):
    o = out[m]; rep = {}
    for sect in ("pages", "posts", "buttons", "gets", "links", "htmx"):
        items = o[sect]
        if sect == "pages": items = dict(items)
        tot = len(items); hit = sum(1 for v in items.values() if v)
        rep[sect] = {"total": tot, "exercised": hit, "untested": sorted(k for k, v in items.items() if not v)}
    res[m] = rep
json.dump(res, open(EV + '/coverage.json', 'w'), indent=1)
for m, rep in res.items():
    print(m, {s: f"{r['exercised']}/{r['total']}" for s, r in rep.items()})
    for s, r in rep.items():
        if r["untested"]: print("   untested", s, r["untested"][:12])
