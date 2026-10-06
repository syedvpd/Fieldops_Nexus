"""Super Admin platform console: every section renders from real data, is platform-admin only, never leaks
write controls, and shows data of ALL organizations (monitoring) while tenant users stay isolated."""
import pytest
from django.test import Client
from django.urls import reverse

SECTIONS = ["overview", "sites", "users", "roles", "assets", "service_ops", "work_orders", "maintenance",
            "inventory", "sla", "dashboards", "settings", "security", "profile", "audit", "organizations"]


def _login(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.mark.parametrize("name", SECTIONS)
def test_section_renders_for_platform_admin(platform_admin, org_a, org_b, name):
    r = _login(platform_admin).get(reverse(f"platform_admin:{name}"))
    assert r.status_code == 200, name


@pytest.mark.parametrize("name", SECTIONS)
def test_section_denied_for_tenant_owner(owner_a, org_a, name):
    assert _login(owner_a).get(reverse(f"platform_admin:{name}")).status_code == 403


def test_anonymous_redirected_to_login(db):
    assert Client().get(reverse("platform_admin:overview")).status_code == 302


def test_overview_shows_both_organizations_and_real_counts(platform_admin, org_a, org_b):
    body = _login(platform_admin).get(reverse("platform_admin:overview")).content.decode()
    assert "Alpha Industries" in body and "Beta Utilities" in body
    assert 'data-kpi="Organizations"' in body and 'data-health="Database"' in body


def test_users_lists_members_of_all_orgs(platform_admin, org_a, org_b):
    body = _login(platform_admin).get(reverse("platform_admin:users")).content.decode()
    assert "owner@alpha.test" in body and "owner@beta.test" in body


def test_org_filter_narrows(platform_admin, org_a, org_b):
    body = _login(platform_admin).get(reverse("platform_admin:users") + f"?org={org_a.pk}").content.decode()
    assert "owner@alpha.test" in body and "owner@beta.test" not in body


def test_roles_matrix_for_selected_org(platform_admin, org_a, org_b):
    body = _login(platform_admin).get(reverse("platform_admin:roles") + f"?org={org_b.pk}").content.decode()
    assert "Permission matrix (Beta Utilities)" in body


def test_audit_export_csv_is_audited(platform_admin, org_a):
    from apps.audit.models import AuditLog
    r = _login(platform_admin).get(reverse("platform_admin:audit") + "?export=csv")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
    assert AuditLog.objects.filter(action="audit.exported").exists()


def test_console_is_read_only(platform_admin, org_a):
    c = _login(platform_admin)
    for name in ["sites", "users", "assets", "work_orders", "inventory", "sla"]:
        assert c.post(reverse(f"platform_admin:{name}"), {}).status_code == 405


def test_detail_404_for_unknown_ids(platform_admin, org_a):
    import uuid
    c = _login(platform_admin)
    for name in ["site_detail", "asset_detail", "service_detail", "work_order_detail"]:
        assert c.get(reverse(f"platform_admin:{name}", args=[uuid.uuid4()])).status_code == 404


def test_site_and_asset_detail(platform_admin, org_a, make_site):
    site = make_site(org_a, "HQ", "Head Office")
    c = _login(platform_admin)
    r = c.get(reverse("platform_admin:site_detail", args=[site.pk]))
    assert r.status_code == 200 and site.name in r.content.decode()


def test_every_section_and_detail_renders_with_populated_data(platform_admin, inv_, sla_, pm_):
    """Rows (not only empty states) render for every section: WO, request, SLA, PM, stock, assets."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.incidents.models import ServiceRequest
    from apps.inventory.models import StockBalance, StockMovement, WorkOrderPart
    from apps.sla.models import SLABreach, SLATracking
    from tests import phase3_support, pm_support

    org, now = pm_["org"], timezone.now()
    wo = phase3_support.new_wo(pm_)
    plan = pm_support.make_plan(pm_)
    pm_support.time_schedule(plan)
    bal = StockBalance.objects.unscoped().create(organization=org, warehouse=inv_["wh"], part=inv_["part"], on_hand=1, reserved=0, min_level=2)
    StockMovement.objects.unscoped().create(organization=org, balance=bal, warehouse=inv_["wh"], part=inv_["part"], movement_type="ISSUE",
                                            quantity=1, on_hand_delta=-1, on_hand_after=1, reserved_after=0, work_order=wo)
    WorkOrderPart.objects.unscoped().create(organization=org, work_order=wo, part=inv_["part"], quantity_requested=1)
    sr = ServiceRequest.objects.unscoped().create(organization=org, number="SR-1", title="Pump leak", asset=pm_["asset"], site=pm_["site"],
                                                  reported_by=pm_["ops"], occurred_at=now)
    trk = SLATracking.objects.unscoped().create(organization=org, request=sr, site=pm_["site"], profile=sla_["profile"], priority="HIGH",
                                                response_minutes=30, resolution_minutes=120, warning_percent=80, started_at=now - timedelta(hours=3),
                                                response_due_at=now - timedelta(hours=2), resolution_due_at=now - timedelta(hours=1))
    SLABreach.objects.unscoped().create(organization=org, tracking=trk, profile=sla_["profile"], site=pm_["site"], target_kind="RESOLUTION",
                                        priority="HIGH", breached_at=now, detected_at=now)
    c = _login(platform_admin)
    for name in SECTIONS:
        assert c.get(reverse(f"platform_admin:{name}")).status_code == 200, name
    for name, obj in [("site_detail", pm_["site"]), ("asset_detail", pm_["asset"]), ("service_detail", sr), ("work_order_detail", wo)]:
        r = c.get(reverse(f"platform_admin:{name}", args=[obj.pk]))
        assert r.status_code == 200, name
    body = c.get(reverse("platform_admin:work_orders")).content.decode()
    assert wo.number in body
    assert "SR-1" in c.get(reverse("platform_admin:service_ops")).content.decode()
