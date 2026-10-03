"""Role templates versus the REAL registered permission catalog: no inert pattern, no accidental grants, minimal client role."""
import fnmatch

import pytest

from apps.rbac import catalog
from apps.rbac import services as rbac
from apps.rbac.role_templates import TEMPLATES

pytestmark = pytest.mark.django_db

CODES = sorted(catalog.all_codes())


def resolved(template):
    return rbac._template_codes(template)


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.key)
def test_every_pattern_matches_a_registered_permission(template):
    inert = [p for p in template.patterns if not any(fnmatch.fnmatchcase(c, p) for c in CODES)]
    assert inert == [], f"{template.key} has inert patterns {inert}"
    for ex in template.excludes:
        assert any(fnmatch.fnmatchcase(c, ex) for c in CODES), f"{template.key} exclude {ex} matches nothing"


def test_every_registered_permission_is_reachable_by_some_role():
    granted = set().union(*(resolved(t) for t in TEMPLATES))
    assert set(CODES) - granted == set()


def test_owner_gets_everything():
    owner = next(t for t in TEMPLATES if t.is_owner)
    assert resolved(owner) == set(CODES)


def test_client_requester_has_exactly_the_portal_client_permissions():
    client = next(t for t in TEMPLATES if t.key == "client_requester")
    assert resolved(client) == {"portal.request.create", "portal.request.view", "portal.request.confirm"}


def test_only_the_client_and_owner_roles_hold_portal_client_permissions():
    for t in TEMPLATES:
        if t.key in ("client_requester",) or t.is_owner:
            continue
        leaked = {c for c in resolved(t) if c.startswith("portal.request.")}
        assert leaked == set(), f"{t.key} gets client portal permissions {leaked}"


def test_sensitive_permissions_go_to_the_intended_roles_only():
    by_role = {t.key: resolved(t) for t in TEMPLATES}
    holders = lambda code: {k for k, v in by_role.items() if code in v}  # noqa: E731
    assert holders("audit.export") == {"owner", "auditor"}
    assert holders("portal.manage") == {"owner", "service_manager"}
    assert holders("contract.create") == {"owner", "asset_manager", "service_manager"}
    assert holders("qr.generate") == {"owner", "asset_manager"}
    assert holders("report.view") >= {"owner", "admin", "operations_manager", "asset_manager", "supervisor",
                                      "service_manager", "auditor"}
    assert "technician" not in holders("report.view") and "client_requester" not in holders("report.view")
    assert holders("contract.check") >= {"owner", "operations_manager", "maintenance_planner", "asset_manager",
                                         "service_manager"}


def test_client_requester_has_no_internal_operational_permission(org_a, make_member):
    m = make_member(org_a, "client@roles.test", "client_requester")
    perms = rbac.membership_permissions(m)
    assert perms == {"portal.request.create", "portal.request.view", "portal.request.confirm"}
    for code in CODES:
        if not code.startswith("portal.request."):
            assert not rbac.has_permission_anywhere(m, code), code


def test_seeded_database_roles_equal_the_template_resolution(org_a):
    from apps.rbac.models import Role

    for t in TEMPLATES:
        role = Role.objects.unscoped().get(organization=org_a, system_key=t.key)
        assert set(role.role_permissions.values_list("permission__code", flat=True)) == resolved(t), t.key


def test_exclude_never_removes_an_explicitly_named_permission():
    from apps.rbac.role_templates import RoleTemplate

    t = RoleTemplate("x", "X", "", ("*.view", "portal.request.view"), excludes=("portal.request.*",))
    got = rbac._template_codes(t)
    assert "portal.request.view" in got and "portal.request.create" not in got
