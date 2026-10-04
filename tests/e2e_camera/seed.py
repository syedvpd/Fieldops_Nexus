# ruff: noqa  (stand-alone helper for the real-browser camera check, see README.md)
import json, django
django.setup()
from django.contrib.auth import get_user_model
from apps.tenancy import services as tenancy
from apps.tenancy.models import Membership
from apps.rbac import services as rbac
from apps.sites import services as sites
from apps.assets import services as assets
from apps.identification import services as idn
User = get_user_model()
PW = "Correct-Horse-Battery-9"  # local e2e database only
admin = User.objects.filter(email="root@e2e.test").first() or User.objects.create_user(email="root@e2e.test", password=PW, full_name="Root", is_platform_admin=True)
def org(name, owner):
    o, m = tenancy.create_organization(name=name, owner_email=owner, owner_name=name + " Owner", actor=admin)
    m.status = Membership.Status.ACTIVE; m.save(update_fields=["status"])
    m.user.set_password(PW); m.user.save()
    return o
def member(o, email, role, site=None):
    u = User.objects.create_user(email=email, password=PW, full_name=email.split("@")[0])
    m = Membership(organization=o, user=u, status=Membership.Status.ACTIVE); m.save()
    r = rbac.system_role_by_key(o, role)
    if site: rbac.set_membership_assignments(m, [(r, site)], actor=None, system=True)
    else: rbac.set_membership_roles(m, [r], actor=None, system=True)
    return m
out = {}
a = org("Alpha E2E", "owner@alpha.test"); b = org("Beta E2E", "owner@beta.test")
for tag, o in (("a", a), ("b", b)):
    s1 = sites.create_site(o, actor=None, code="S1", name="Main site"); s2 = sites.create_site(o, actor=None, code="S2", name="Other site")
    cat = assets.create_category(o, name="Pump", actor=None)
    p1 = assets.create_asset(o, site=s1, category=cat, actor=None, asset_tag=f"E2E-PUMP-{tag.upper()}", name=f"Boiler feed pump {tag.upper()}")
    p2 = assets.create_asset(o, site=s2, category=cat, actor=None, asset_tag=f"E2E-FAN-{tag.upper()}", name=f"Fan {tag.upper()}")
    qr = idn.generate(p1, "QR", actor=None); qr2 = idn.generate(p2, "QR", actor=None)
    out[tag] = {"token": qr.token, "token_other_site": qr2.token, "asset": str(p1.pk), "site2": str(s2.pk), "site1": str(s1.pk)}
member(a, "tech@alpha.test", "technician")
member(b, "tech@beta.test", "technician")
out["scoped"] = member(a, "scoped@alpha.test", "technician", User and __import__("apps.sites.models", fromlist=["Site"]).Site.objects.for_organization(a).get(code="S2")).user.email
out["pw"] = PW
open("e2e_seed.json", "w").write(json.dumps(out, indent=1))
print(json.dumps({k: (v if k in ("pw",) else "ok") for k, v in out.items()}))
