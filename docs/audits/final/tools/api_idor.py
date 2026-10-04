import sys, re, json; sys.path.insert(0,'.')
from pw import *
o=json.load(open("api_sweep.json"))
lines=[l.split("  [")[0] for l in open("urls_api.txt").read().splitlines()]
eps=sorted({re.sub(r"\(\?P<([a-z_]+)>[^)]*\)","{\\1}",l.replace("^","").replace("$","").replace("\\.",".")) for l in lines if "format" not in l})
detail=[e for e in eps if re.fullmatch(r"api/v1/[a-z\-/]+/\{pk\}/",e) and e.count("{")==1]
actions=[e for e in eps if re.fullmatch(r"api/v1/[a-z\-/]+/\{pk\}/[a-z\-]+/",e) and e.count("{")==1]
res={"detail":[],"actions":[]}
with sync_playwright() as p:
    b=launch(p); A=b.new_context(); login(A,"owner@alpha.qa.test"); B=b.new_context(); login(B,"owner@beta.qa.test")
    def ids(ctx,base):
        r=ctx.request.get(BASE+"/"+base)
        if r.status!=200: return []
        try: j=r.json()
        except Exception: return []
        d=j.get("data",j) if isinstance(j,dict) else j
        if isinstance(d,dict) and "results" in d: d=d["results"]
        return [x["id"] for x in d if isinstance(x,dict) and "id" in x][:2] if isinstance(d,list) else []
    leaks=[]; tested=0
    for e in detail:
        base=e.replace("{pk}/","")
        ia=ids(A,base); ib=ids(B,base)
        for (src,dst,idl,lab) in ((A,B,ia,"ALPHA->BETA"),(B,A,ib,"BETA->ALPHA")):
            for i in idl[:1]:
                tested+=1
                r=dst.request.get(BASE+"/"+e.replace("{pk}",i)); res["detail"].append((lab,e,r.status))
                if r.status==200: leaks.append((lab,e,i))
    # actions: POST on foreign object
    ck={c['name']:c['value'] for c in B.cookies()}
    atested=0
    for e in actions:
        base=e.rsplit("{pk}",1)[0]
        ia=ids(A,base)
        if not ia: continue
        for (dst,lab) in ((B,"ALPHA->BETA"),):
            ck={c['name']:c['value'] for c in dst.cookies()}
            r=dst.request.post(BASE+"/"+e.replace("{pk}",ia[0]),data=json.dumps({}),headers={"X-CSRFToken":ck.get("csrftoken",""),"Content-Type":"application/json","Referer":BASE+"/"},max_redirects=0)
            atested+=1; res["actions"].append((lab,e,r.status))
            if r.status not in (403,404,405,401,400): leaks.append((lab,e,r.status))
    json.dump(res,open("api_idor.json","w"),indent=1)
    print("detail endpoints tested:",tested,"action endpoints tested:",atested,"LEAKS:",leaks)
    from collections import Counter
    print(Counter(x[2] for x in res["detail"]), Counter(x[2] for x in res["actions"]))
    b.close()
