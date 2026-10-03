"""Site-scoped authorization (MembershipRole.site): org-wide vs site grants, no leakage, IDOR on every
site-bound resource, assignment services/API."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.assets import hierarchy, services
from apps.audit.models import AuditLog
from apps.core.exceptions import ValidationFailed
from apps.rbac import services as rbac
from apps.rbac.models import MembershipRole
from apps.tenancy.models import Membership
from tests.conftest import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(org_a, owner_a, site_a1, site_a2, make_asset, make_zone, make_scoped_member):
    """Assets on two sites of org A, plus an asset manager restricted to site A1."""
    z1, z2 = make_zone(site_a1, "Hall 1"), make_zone(site_a2, "Hall 2")
    a1 = make_asset(org_a, site_a1, "S1-1", zone=z1)
    a1b = make_asset(org_a, site_a1, "S1-2")
    a2 = make_asset(org_a, site_a2, "S2-1", zone=z2)
    a2b = make_asset(org_a, site_a2, "S2-2")
    link = hierarchy.add_component(a2, a2b, actor=owner_a)
    meter = services.create_meter(a2, name="Hours", unit="h", actor=owner_a)
    services.record_reading(meter, value=5, actor=owner_a)
    doc = services.add_document(a2, SimpleUploadedFile("n.txt", b"secret B", content_type="text/plain"),
                                title="Secret", actor=owner_a)
    from apps.sites import services as site_services
    cal = site_services.create_calendar(site_a2, actor=owner_a, name="Std", is_24x7=True)
    contact = site_services.add_contact(site_a2, actor=owner_a, name="Boss", phone="1")
    manager = make_scoped_member(org_a, "mgr@alpha.test", "asset_manager", [site_a1])
    return dict(z1=z1, z2=z2, a1=a1, a1b=a1b, a2=a2, a2b=a2b, link=link, meter=meter, doc=doc, cal=cal,
                contact=contact, manager=manager)


# --- rbac unit ---------------------------------------------------------------------------------------------------


def test_org_wide_vs_site_scoped_permission(org_a, site_a1, site_a2, make_member, make_scoped_member):
    wide = make_member(org_a, "wide@alpha.test", "asset_manager")
    scoped = make_scoped_member(org_a, "narrow@alpha.test", "asset_manager", [site_a1])
    assert rbac.has_permission(wide, "asset.update") and rbac.has_permission(wide, "asset.update", site_a2)
    assert not rbac.has_permission(scoped, "asset.update")  # no org-wide grant
    assert rbac.has_permission(scoped, "asset.update", site_a1)
    assert not rbac.has_permission(scoped, "asset.update", site_a2)  # wrong site
    assert rbac.has_permission_anywhere(scoped, "asset.update")
    assert rbac.site_scope(wide, "asset.view").all_sites
    s = rbac.site_scope(scoped, "asset.view")
    assert not s.all_sites and s.site_ids == {site_a1.pk}
    assert not rbac.site_scope(scoped, "audit.view").site_ids  # nothing for unrelated permissions


def test_site_assignment_never_widens_non_site_scoped_permissions(org_a, site_a1, make_scoped_member):
    admin = make_scoped_member(org_a, "limited-admin@alpha.test", "admin", [site_a1])
    assert rbac.has_permission(admin, "site.update", site_a1)  # site-scopable: granted for A1
    for code in ("user.view", "user.update", "role.manage", "organization.update", "site.create",
                 "asset.category.manage"):
        assert not rbac.has_permission_anywhere(admin, code), code


def test_owner_is_implicitly_org_wide_and_cannot_be_site_scoped(org_a, owner_a, site_a1, make_member):
    owner = Membership.objects.get(user=owner_a, organization=org_a)
    assert rbac.has_permission(owner, "asset.update") and rbac.has_permission(owner, "user.update")
    target = make_member(org_a, "x@alpha.test", "technician")
    with pytest.raises(ValidationFailed) as exc:
        rbac.set_membership_assignments(
            target, [(rbac.system_role_by_key(org_a, "owner"), site_a1)], actor=owner_a)
    assert exc.value.code == "owner_not_site_scoped"


def test_cross_tenant_site_or_role_rejected_in_assignment(org_a, org_b, site_b1, make_member):
    m = make_member(org_a, "z@alpha.test", "technician")
    with pytest.raises(ValidationFailed) as exc:
        rbac.set_membership_assignments(m, [(rbac.system_role_by_key(org_a, "technician"), site_b1)], actor=None,
                                        system=True)
    assert exc.value.code == "cross_tenant_site"
    with pytest.raises(ValidationFailed) as exc:
        rbac.set_membership_assignments(m, [(rbac.system_role_by_key(org_b, "technician"), None)], actor=None,
                                        system=True)
    assert exc.value.code == "cross_tenant_role"


def test_suspended_member_loses_site_grants(org_a, site_a1, make_scoped_member):
    m = make_scoped_member(org_a, "susp@alpha.test", "asset_manager", [site_a1])
    m.status = Membership.Status.SUSPENDED
    m.save()
    m._site_perm_cache = None
    assert not rbac.has_permission(m, "asset.view", site_a1)


def test_assignment_is_audited_with_site(org_a, owner_a, site_a1, make_member):
    m = make_member(org_a, "aud@alpha.test", "technician")
    rbac.set_membership_assignments(
        m, [(rbac.system_role_by_key(org_a, "technician"), site_a1)], actor=owner_a)
    entry = AuditLog.objects.filter(organization=org_a, action="membership.roles_changed").latest("occurred_at")
    assert entry.after == {"roles": ["Technician @ A1"]}
    assert MembershipRole.objects.get(membership=m).site_id == site_a1.pk


# --- list endpoints never leak out-of-scope data ------------------------------------------------------------------------


def test_scoped_user_sees_only_own_site_everywhere(as_user, org_a, world, site_a1, site_a2):
    c = as_user(world["manager"].user, org_a)
    assert [s["code"] for s in c.get("/api/v1/sites/").json()["results"]] == ["A1"]
    assert {a["asset_tag"] for a in c.get("/api/v1/assets/").json()["results"]} == {"S1-1", "S1-2"}
    assert [z["name"] for z in c.get("/api/v1/zones/").json()["results"]] == ["Hall 1"]
    assert c.get("/api/v1/calendars/").json()["count"] == 0
    assert c.get("/api/v1/site-contacts/").json()["count"] == 0
    assert c.get("/api/v1/meters/").json()["count"] == 0
    assert c.get("/api/v1/asset-components/").json()["count"] == 0
    # filters / search aimed at the other site return nothing instead of leaking
    assert c.get(f"/api/v1/assets/?site={site_a2.pk}").json()["count"] == 0
    assert c.get("/api/v1/assets/?q=S2").json()["count"] == 0
    assert c.get(f"/api/v1/zones/?site={site_a2.pk}").json()["count"] == 0
    assert c.get("/api/v1/sites/?q=A2").json()["count"] == 0
    assert c.get(f"/api/v1/assets/?category={world['a2'].category_id}").json()["count"] == 2  # only A1's two


def test_scoped_user_idor_for_other_site_resources(as_user, org_a, world, site_a2, make_category):
    c = as_user(world["manager"].user, org_a)
    a2, a2b = world["a2"], world["a2b"]
    gets = (f"/api/v1/sites/{site_a2.pk}/", f"/api/v1/sites/{site_a2.pk}/tree/", f"/api/v1/zones/{world['z2'].pk}/",
            f"/api/v1/calendars/{world['cal'].pk}/", f"/api/v1/site-contacts/{world['contact'].pk}/",
            f"/api/v1/assets/{a2.pk}/", f"/api/v1/assets/{a2.pk}/history/", f"/api/v1/assets/{a2.pk}/location-history/",
            f"/api/v1/assets/{a2.pk}/documents/", f"/api/v1/assets/{a2.pk}/tree/",
            f"/api/v1/assets/{a2.pk}/components/", f"/api/v1/assets/{a2.pk}/validate/",
            f"/api/v1/meters/{world['meter'].pk}/", f"/api/v1/meters/{world['meter'].pk}/readings/",
            f"/api/v1/asset-components/{world['link'].pk}/")
    for url in gets:
        assert c.get(url).status_code == 404, url
    assert c.patch(f"/api/v1/assets/{a2.pk}/", {"name": "x"}, format="json").status_code == 404
    assert c.post(f"/api/v1/assets/{a2.pk}/transition/", {"action": "start_maintenance", "reason": "x"},
                  format="json").status_code == 404
    assert c.post(f"/api/v1/assets/{a2.pk}/components/", {"child": str(world["a1"].pk)},
                  format="json").status_code == 404
    assert c.post(f"/api/v1/assets/{world['a1'].pk}/components/", {"child": str(a2b.pk)},
                  format="json").status_code == 404
    assert c.post(f"/api/v1/meters/{world['meter'].pk}/readings/", {"value": 9}, format="json").status_code == 404
    assert c.post("/api/v1/meters/", {"asset": str(a2.pk), "name": "x", "unit": "h"}, format="json").status_code == 404
    assert c.post(f"/api/v1/assets/{a2.pk}/documents/",
                  {"file": SimpleUploadedFile("a.txt", b"x", content_type="text/plain")},
                  format="multipart").status_code == 404
    assert c.delete(f"/api/v1/asset-components/{world['link'].pk}/").status_code == 404
    # creating on / moving to another site
    cat = make_category(org_a)
    r = c.post("/api/v1/assets/", {"asset_tag": "NEW-1", "name": "n", "category": str(cat.pk),
                                   "site": str(site_a2.pk)}, format="json")
    assert r.status_code == 404
    r = c.patch(f"/api/v1/assets/{world['a1'].pk}/", {"site": str(site_a2.pk)}, format="json")
    assert r.status_code == 404
    a2.refresh_from_db()
    assert a2.name == "Asset S2-1" and a2.status == "ACTIVE"


def test_scoped_user_can_work_on_their_own_site(as_user, org_a, world, site_a1, make_category):
    c = as_user(world["manager"].user, org_a)
    cat = make_category(org_a)
    r = c.post("/api/v1/assets/", {"asset_tag": "NEW-2", "name": "n", "category": str(cat.pk),
                                   "site": str(site_a1.pk)}, format="json")
    assert r.status_code == 201, r.content
    assert c.post(f"/api/v1/assets/{r.json()['id']}/transition/", {"action": "start_maintenance", "reason": "svc"},
                  format="json").status_code == 200
    assert c.patch(f"/api/v1/sites/{site_a1.pk}/", {"name": "Renamed"}, format="json").status_code == 200
    # but not org-level things
    assert c.post("/api/v1/sites/", {"code": "ZZ", "name": "Z"}, format="json").status_code == 403
    assert c.post("/api/v1/asset-categories/", {"name": "NewCat"}, format="json").status_code == 403
    assert c.get("/api/v1/members/").status_code == 403


def test_scoped_user_cannot_deactivate_or_edit_in_other_scope_but_view_scope_gives_403(
        as_user, org_a, site_a1, site_a2, make_scoped_member):
    """View on A1+A2 but update only on A1: A2 is visible, so a write there is 403 (not 404)."""
    from apps.rbac.models import Role

    role = Role.objects.get(organization=org_a, system_key="asset_manager")
    viewer_role = Role.objects.get(organization=org_a, system_key="auditor")
    m = make_scoped_member(org_a, "mix@alpha.test", "asset_manager", [site_a1])
    rbac.set_membership_assignments(m, [(role, site_a1), (viewer_role, site_a2)], actor=None, system=True)
    c = as_user(m.user, org_a)
    assert c.get(f"/api/v1/sites/{site_a2.pk}/").status_code == 200
    assert c.patch(f"/api/v1/sites/{site_a2.pk}/", {"name": "x"}, format="json").status_code == 403
    assert c.patch(f"/api/v1/sites/{site_a1.pk}/", {"name": "ok"}, format="json").status_code == 200


def test_document_download_follows_site_scope(client, org_a, world, owner_a, tech_a, make_scoped_member):
    url = f"/app/files/{world['doc'].attachment_id}/download/"
    client.force_login(world["manager"].user)
    assert client.get(url).status_code == 404  # asset is at site A2; manager has A1 only
    client.logout()
    client.force_login(owner_a)
    assert client.get(url).status_code == 200
    client.logout()
    client.force_login(tech_a)  # org-wide technician
    assert client.get(url).status_code == 200


def test_ui_pages_are_site_scoped(client, org_a, world, site_a1, site_a2):
    client.force_login(world["manager"].user)
    assert client.get("/app/assets/").status_code == 200
    body = client.get("/app/assets/").content.decode()
    assert "S1-1" in body and "S2-1" not in body
    assert "A2" not in client.get("/app/sites/").content.decode().replace("A2 ", "")
    assert client.get(f"/app/sites/{site_a2.pk}/").status_code == 404
    assert client.get(f"/app/assets/{world['a2'].pk}/").status_code == 404
    assert client.get(f"/app/assets/{world['a2'].pk}/tree/").status_code == 404
    assert client.post(f"/app/assets/{world['a2'].pk}/transition/start_maintenance/", {"reason": "x"}).status_code == 404
    assert client.get(f"/app/assets/{world['a1'].pk}/").status_code == 200


# --- assignment through the API ------------------------------------------------------------------------------------------


def test_api_invite_and_update_with_site_scope(as_user, owner_a, org_a, site_a1, site_a2, org_b, site_b1):
    from apps.rbac.models import Role

    tech = Role.objects.get(organization=org_a, system_key="technician")
    c = as_user(owner_a, org_a)
    r = c.post("/api/v1/members/", {"email": "newtech@alpha.test", "full_name": "New Tech",
                                    "role_ids": [str(tech.pk)], "site_ids": [str(site_a1.pk)]}, format="json")
    assert r.status_code == 201, r.content
    roles = r.json()["roles"]
    assert len(roles) == 1 and roles[0]["site_code"] == "A1"
    mid = r.json()["id"]
    # explicit per-role assignments, including an org-wide one
    r = c.patch(f"/api/v1/members/{mid}/", {"role_assignments": [
        {"role_id": str(tech.pk), "site_id": str(site_a2.pk)}, {"role_id": str(tech.pk), "site_id": None}]},
        format="json")
    assert r.status_code == 200 and {x["site_code"] for x in r.json()["roles"]} == {"A2", None}
    # cross-tenant site id is rejected, nothing changes
    r = c.patch(f"/api/v1/members/{mid}/", {"role_ids": [str(tech.pk)], "site_ids": [str(site_b1.pk)]}, format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_sites"
    assert MembershipRole.objects.filter(membership_id=mid).count() == 2
    # owner role cannot be scoped
    owner_role = Role.objects.get(organization=org_a, system_key="owner")
    r = c.patch(f"/api/v1/members/{mid}/", {"role_ids": [str(owner_role.pk)], "site_ids": [str(site_a1.pk)]},
                format="json")
    assert r.status_code == 400
    # mixing styles is a validation error
    r = c.patch(f"/api/v1/members/{mid}/", {"role_ids": [str(tech.pk)], "role_assignments": []}, format="json")
    assert r.status_code == 400


def test_ui_assign_and_remove_scoped_role(client, owner_a, org_a, site_a1, tech_a):
    from apps.rbac.models import Role

    m = Membership.objects.get(organization=org_a, user=tech_a)
    sup = Role.objects.get(organization=org_a, system_key="supervisor")
    client.force_login(owner_a)
    r = client.post(f"/app/users/{m.pk}/", {"action": "assign_role", "role": sup.pk, "site": site_a1.pk})
    assert r.status_code == 302
    assert MembershipRole.objects.filter(membership=m, role=sup, site=site_a1).exists()
    page = client.get(f"/app/users/{m.pk}/").content.decode()
    assert "Site A1" in page and "Organization-wide" in page
    mr = MembershipRole.objects.get(membership=m, role=sup)
    assert client.post(f"/app/users/{m.pk}/", {"action": "remove_role", "assignment_id": mr.pk}).status_code == 302
    assert not MembershipRole.objects.filter(pk=mr.pk).exists()
    # the last remaining role cannot be removed
    only = MembershipRole.objects.get(membership=m)
    client.post(f"/app/users/{m.pk}/", {"action": "remove_role", "assignment_id": only.pk})
    assert MembershipRole.objects.filter(membership=m).count() == 1
    assert User.objects.filter(pk=tech_a.pk).exists()


def test_ui_foreign_site_cannot_be_assigned(client, owner_a, org_a, site_b1, tech_a):
    from apps.rbac.models import Role

    m = Membership.objects.get(organization=org_a, user=tech_a)
    sup = Role.objects.get(organization=org_a, system_key="supervisor")
    client.force_login(owner_a)
    client.post(f"/app/users/{m.pk}/", {"action": "assign_role", "role": sup.pk, "site": site_b1.pk})
    assert not MembershipRole.objects.filter(membership=m, role=sup).exists()
