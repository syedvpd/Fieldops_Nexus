import sys, re, json; sys.path.insert(0,'.')
from pw import *
lines=[l.split("  [")[0] for l in open("urls_api.txt").read().splitlines()]
eps=sorted({re.sub(r"\(\?P<([a-z_]+)>[^)]*\)","{\\1}",l.replace("^","").replace("$","").replace("\\.",".")) for l in lines if "format" not in l and "schema" not in l and "docs" not in l})
lists=[e for e in eps if "{" not in e and not any(x in e for x in ("auth/token","process","generate-work-orders"))]
ROLES={"owner":"owner@alpha.qa.test","admin":"admin@alpha.qa.test","ops":"ops@alpha.qa.test","supervisor":"supervisor@alpha.qa.test","assets":"assets@alpha.qa.test","planner":"planner@alpha.qa.test","tech":"tech1@alpha.qa.test","stores":"stores@alpha.qa.test","service":"service@alpha.qa.test","auditor":"auditor@alpha.qa.test","client":"client@alpha.qa.test","betaowner":"owner@beta.qa.test","platform":"superadmin@platform.qa.test"}
out={}
with sync_playwright() as p:
    b=launch(p)
    ctxs={}
    for r,e in ROLES.items():
        c=b.new_context(); login(c,e); ctxs[r]=c
    anon=b.new_context()
    for e in lists:
        row={}
        for r,c in list(ctxs.items())+[("anon",anon)]:
            try:
                resp=c.request.get(BASE+"/"+e)
                n=None
                if resp.status==200:
                    try:
                        j=resp.json(); d=j.get("data",j) if isinstance(j,dict) else j
                        n=len(d) if isinstance(d,list) else (d.get("count") if isinstance(d,dict) and "count" in d else "obj")
                        if isinstance(j,dict) and isinstance(j.get("meta"),dict): n=j["meta"].get("count",n)
                    except Exception: n="?"
                row[r]=(resp.status,n)
            except Exception as ex: row[r]=("ERR",str(ex)[:40])
        out[e]=row
    json.dump(out,open("api_sweep.json","w"),indent=1)
    b.close()
print(len(lists),"list endpoints x",len(ROLES)+1,"principals")
# summary: anomalies
for e,row in out.items():
    if any(v[0]==500 or v[0]=="ERR" for v in row.values()): print("5xx/ERR",e,{k:v for k,v in row.items() if v[0] in(500,"ERR")})
    if row["anon"][0]==200: print("ANON 200!",e)
