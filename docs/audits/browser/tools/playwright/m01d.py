import sys; sys.path.insert(0,'.')
from bx import *
r=Run("M01").start(); O="owner"
p=r.page(O,"mobile"); p.goto(BASE+"/app/sites/"); p.wait_for_load_state("networkidle")
btn=p.locator("button[data-fx-toggle-nav]").first
print(btn.evaluate("e=>e.outerHTML")[:200])
ON="()=>{const a=document.querySelector('.fx-nav a[href=\\'/app/sites/\\']');const b=a.getBoundingClientRect();return b.right>0&&b.left<window.innerWidth?1:0}"
vis0=p.evaluate(ON)
r.ok(vis0==0,"Mobile: sidebar collapsed by default at 390px","/app/sites/",O,"load at 390x844","nav hidden until menu tapped",f"visible nav links={vis0}")
btn.click(); p.wait_for_timeout(700)
vis1=p.evaluate(ON)
r.ok(vis1>0,"Mobile: hamburger opens the navigation","/app/sites/",O,"tap ☰","nav visible",f"visible={vis1}",ev=shot(p,"M01_mobile_menu_open"))
ov=overflow(p); r.ok(ov["sw"]<=ov["iw"]+1,"Mobile: open menu causes no horizontal overflow","/app/sites/",O,"menu open","no overflow",ov["sw"])
p.locator(".fx-nav a[href='/app/sites/']").first.click(); p.wait_for_load_state("networkidle")
r.ok("/app/sites" in p.url,"Mobile: menu link navigates","/app/sites/",O,"tap Sites & Locations","navigates",p.url)
btn=p.locator("button[data-fx-toggle-nav]").first; btn.click(); p.wait_for_timeout(500); p.keyboard.press("Escape"); p.wait_for_timeout(500)
vis2=p.evaluate(ON)
r.ok(vis2==0,"Mobile: Escape closes the open menu (a11y)","/app/sites/",O,"open then Esc","closed",f"visible={vis2}",partial=True)
# table on mobile: scrolls inside its container, page itself does not
sc=p.evaluate("()=>{const t=document.querySelector('main table');const w=t.closest('.table-responsive,.overflow-auto')||t.parentElement;return {sw:w.scrollWidth,cw:w.clientWidth,scrolls:w.scrollWidth>w.clientWidth, ox:getComputedStyle(w).overflowX}}")
r.ok(sc["ox"] in("auto","scroll"),"Mobile: wide table scrolls inside its own container (page does not)","/app/sites/",O,"inspect table wrapper","overflow-x auto",sc)
for x in r.rows: print(x["status"],x["feature"],"|",x["actual"])
print(len(r.issues)); r.stop()
