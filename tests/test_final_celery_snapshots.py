"""Final reconciliation: per-organization Celery fan-out (D-056) and report snapshots (D-054, HPE ReportSnapshot).
Tenant-aware, idempotent, suspended organizations skipped, snapshot figures equal the live dashboard queries."""
import json
from datetime import date

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.test import APIClient

from apps.contracts import tasks as contract_tasks
from apps.core.tenant import tenant_context
from apps.dashboards import metrics, services
from apps.dashboards import tasks as dash_tasks
from apps.dashboards.models import ReportSnapshot
from apps.maintenance import tasks as pm_tasks
from apps.sla import tasks as sla_tasks
from apps.tenancy import services as tenancy
from tests.phase3_support import new_wo

pytestmark = pytest.mark.django_db


def api(user, org):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


@pytest.fixture
def two_orgs(p3, org_b, owner_a, owner_b):
    new_wo(p3, title="Alpha job 1")
    new_wo(p3, title="Alpha job 2")
    return p3


def test_snapshot_equals_live_metrics_is_idempotent_and_immutable(two_orgs, org_a, owner_a):
    day = date(2026, 10, 3)
    first = services.snapshot_organization(org_a, day)
    assert first == {"created": len(metrics.SECTIONS), "existing": 0, "skipped": None}
    second = services.snapshot_organization(org_a, day)
    assert second["created"] == 0 and second["existing"] == len(metrics.SECTIONS)  # idempotent
    snap = ReportSnapshot.objects.for_organization(org_a).get(kind="operations", period_to=day)
    with tenant_context(org_a):
        owner = services._owner_membership(org_a)
        f = metrics.parse_filters({"from": snap.period_from.isoformat(), "to": day.isoformat()}, owner, org_a)
        live = json.loads(json.dumps(metrics.operations(owner, org_a, f), cls=DjangoJSONEncoder))
    assert snap.payload == live  # same queries, no second formula
    assert snap.payload["kpis"]["created"] == 2 if "kpis" in snap.payload else True
    snap.payload = {"x": 1}
    with pytest.raises(ValueError):
        snap.save()  # immutable once written


def test_snapshots_are_tenant_isolated_api_and_scope(two_orgs, org_a, org_b, owner_a, owner_b, site_a1, make_scoped_member):
    services.snapshot_organization(org_a, date(2026, 10, 3))
    services.snapshot_organization(org_b, date(2026, 10, 3))
    a = api(owner_a, org_a).get("/api/v1/report-snapshots/").json()
    ids_a = {r["id"] for r in a["results"]}
    assert len(ids_a) == len(metrics.SECTIONS)
    b = api(owner_b, org_b).get("/api/v1/report-snapshots/").json()
    assert not ids_a & {r["id"] for r in b["results"]}
    some = next(iter(ids_a))
    assert api(owner_b, org_b).get(f"/api/v1/report-snapshots/{some}/").status_code == 404  # IDOR
    assert api(owner_a, org_a).post("/api/v1/report-snapshots/", {}, format="json").status_code in (403, 405)
    # a site-scoped report user must not read organization-wide frozen figures
    scoped = make_scoped_member(org_a, "scopedrep@alpha.test", "operations_manager", [site_a1])
    assert api(scoped.user, org_a).get("/api/v1/report-snapshots/").status_code == 403
    # a technician has no report right at all
    assert api(two_orgs["tech"].user, org_a).get("/api/v1/report-snapshots/").status_code == 403


def test_fan_out_dispatches_one_task_per_active_org_and_skips_suspended(two_orgs, org_a, org_b, platform_admin):
    for fan in (sla_tasks.fan_out_sla_monitor, pm_tasks.fan_out_maintenance, contract_tasks.fan_out_renewal_alerts,
                dash_tasks.fan_out_report_snapshots):
        assert fan() == {"dispatched": 2}
    tenancy.set_organization_status(org_b, active=False, reason="audit test", actor=platform_admin)
    assert sla_tasks.fan_out_sla_monitor() == {"dispatched": 1}
    for per_org in (sla_tasks.monitor_sla_for_org, pm_tasks.generate_due_maintenance_for_org,
                    contract_tasks.send_renewal_alerts_for_org):
        assert per_org(str(org_b.pk)).get("skipped") is True  # a suspended tenant is never processed
    assert dash_tasks.snapshot_organization(str(org_b.pk)).get("skipped")
    assert not ReportSnapshot.objects.for_organization(org_b).exists()
    assert ReportSnapshot.objects.for_organization(org_a).count() == len(metrics.SECTIONS)  # fan-out ran for Alpha


def test_per_org_task_only_touches_its_own_tenant(two_orgs, org_a, org_b):
    res = dash_tasks.snapshot_organization(str(org_a.pk))
    assert res["organization"] == str(org_a.pk) and res["created"] == len(metrics.SECTIONS)
    assert not ReportSnapshot.objects.for_organization(org_b).exists()
    assert pm_tasks.generate_due_maintenance_for_org(str(org_b.pk))["organization"] == str(org_b.pk)


def test_snapshot_kinds_follow_the_sections_data_permissions(two_orgs, org_a, make_member):
    """An asset manager holds report.view but not inventory.view / work_order.view organization-wide: those frozen
    sections must stay hidden (the live endpoint refuses them too)."""
    services.snapshot_organization(org_a, date(2026, 10, 3))
    am = make_member(org_a, "am2@alpha.test", "asset_manager")
    resp = api(am.user, org_a).get("/api/v1/report-snapshots/").json()
    kinds = {r["kind"] for r in resp["results"]}
    from apps.rbac import services as rbac
    expected = {k for k, (_l, _f, codes) in metrics.SECTIONS.items()
                if all(rbac.has_permission(am, c) for c in codes)}
    assert kinds == expected and "inventory" not in kinds
    hidden = ReportSnapshot.objects.for_organization(org_a).get(kind="inventory")
    assert api(am.user, org_a).get(f"/api/v1/report-snapshots/{hidden.pk}/").status_code == 404
