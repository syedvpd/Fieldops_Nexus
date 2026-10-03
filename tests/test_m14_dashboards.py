"""M14 dashboards: every KPI is reconciled against independently computed expectations / direct database queries;
tenant isolation, site scope, date filters, role visibility, zero data, validation, query count and the HTML pages."""
from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection
from django.db.models import Count
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dashboards import metrics
from apps.incidents import services as incidents
from apps.inventory import services as inv
from apps.maintenance import services as pm
from apps.workorders.models import WorkOrder
from tests.phase3_support import finish_work, new_wo, step, wo_in_progress
from tests.pm_support import T0, freeze, make_plan, time_schedule

pytestmark = pytest.mark.django_db


def api(user, org):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


def web(user):
    c = Client()
    c.force_login(user)
    return c


def get(p, who, section, **params):
    r = api(p[who].user, p["org"]).get(f"/api/v1/dashboards/{section}/", params)
    assert r.status_code == 200, (section, r.status_code, r.content[:300])
    return r.json()["data"]


# --- operations: the "10 work orders, 3 completed, 2 overdue" reconciliation ------------------------------------------


@pytest.fixture
def ops_data(p3):
    """Site 1: 10 work orders (3 completed, 2 overdue, 1 cancelled). Site 2: 2 work orders (1 completed)."""
    orders = [new_wo(p3, work_type="CORRECTIVE", title=f"Job {i}") for i in range(10)]
    done = []
    for _ in range(3):
        wo = wo_in_progress(p3, work_type="PREVENTIVE")
        finish_work(wo, p3)
        done.append(wo)
    # two planned orders whose window has passed (test-level shaping of a deadline)
    overdue = orders[:2]
    for wo in overdue:
        WorkOrder.objects.filter(pk=wo.pk).update(status="PLANNED", planned_start=timezone.now() - timedelta(days=3),
                                                  planned_end=timezone.now() - timedelta(days=2))
    cancelled = orders[2]
    step(cancelled, "cancel", p3, "planner", reason="Not needed")
    other = new_wo(p3, asset=p3["asset2"], work_type="CORRECTIVE", title="Site 2 job")
    done2 = wo_in_progress(p3, work_type="PREVENTIVE", asset=p3["asset2"])
    finish_work(done2, p3)
    return {**p3, "orders": orders, "done": done, "done2": done2, "other": other}


def test_operations_kpis_reconcile_with_the_database(ops_data):
    p = ops_data
    qs = WorkOrder.objects.filter(organization=p["org"], site=p["site"])
    d = get(p, "ops", "operations", site=str(p["site"].pk))
    k = d["kpis"]
    assert k["open_total"] == qs.exclude(status__in=("CLOSED", "CANCELLED")).count()
    assert k["created"] == qs.count() == 10 + 3  # 10 listed + 3 completed ones, all created today
    assert k["completed"] == qs.filter(completed_at__isnull=False).count() == 3
    assert k["overdue"] == qs.filter(status__in=metrics.PRE_COMPLETION, planned_end__lt=timezone.now()).count() == 2
    assert d["open_by_status"] == {r["status"]: r["n"] for r in qs.exclude(status__in=("CLOSED", "CANCELLED"))
                                   .values("status").annotate(n=Count("pk"))}
    assert {o["number"] for o in d["overdue_list"]} == {o.number for o in p["orders"][:2]}
    assert k["closed"] == 0


def test_all_sites_vs_one_site_and_dates(ops_data):
    p = ops_data
    both = get(p, "ops", "operations")["kpis"]
    s2 = get(p, "ops", "operations", site=str(p["site2"].pk))["kpis"]
    assert both["created"] == 13 + 2 and s2["created"] == 2 and s2["completed"] == 1
    yesterday = (timezone.now() - timedelta(days=1)).date().isoformat()
    past = get(p, "ops", "operations", **{"from": (timezone.now() - timedelta(days=300)).date().isoformat(),
                                          "to": yesterday})["kpis"]
    assert past["created"] == 0 and past["completed"] == 0
    assert past["open_total"] == both["open_total"]  # snapshot KPIs ignore the window
    today = timezone.now().date().isoformat()
    assert get(p, "ops", "operations", **{"from": today, "to": today})["kpis"]["created"] == both["created"]


def test_technician_workload_and_utilization(ops_data):
    p = ops_data
    d = get(p, "ops", "operations", site=str(p["site"].pk), **{"from": timezone.now().date().isoformat(),
                                                               "to": timezone.now().date().isoformat()})
    tech = next(t for t in d["technicians"] if t["hours"] > 0)
    assert tech["hours"] == 4.5  # three completed jobs x 1.5 h recorded by finish_work
    assert tech["utilization"] == round(100 * 4.5 / 8, 1)
    wide = get(p, "ops", "operations", **{"from": (timezone.now() - timedelta(days=9)).date().isoformat(),
                                          "to": timezone.now().date().isoformat()})
    t2 = next(t for t in wide["technicians"] if t["hours"] > 0)
    assert t2["utilization"] == round(100 * t2["hours"] / (10 * 8), 1)


# --- tenant isolation and scope -----------------------------------------------------------------------------------------


def test_other_tenants_never_leak_into_totals(ops_data, org_b, make_member, make_site, make_asset):
    p = ops_data
    before = get(p, "ops", "operations")["kpis"]
    b_ops = make_member(org_b, "ops@beta.test", "operations_manager")
    b_site = make_site(org_b, "B5")
    b_asset = make_asset(org_b, b_site, "B-PUMP")
    from apps.workorders import services as wos

    for i in range(4):
        wos.create_work_order(org_b, asset=b_asset, actor=b_ops.user, title=f"Beta {i}", work_type="CORRECTIVE")
    after = get(p, "ops", "operations")["kpis"]
    assert after == before
    beta = api(b_ops.user, org_b).get("/api/v1/dashboards/operations/").json()["data"]["kpis"]
    assert beta["created"] == 4 and beta["open_total"] == 4
    r = api(p["ops"].user, p["org"]).get("/api/v1/dashboards/operations/", {"site": str(b_site.pk)})
    assert r.status_code == 404  # another tenant's site id is invisible
    cross = APIClient()
    cross.force_authenticate(user=p["ops"].user)
    cross.credentials(HTTP_X_ORGANIZATION=org_b.slug)
    assert cross.get("/api/v1/dashboards/operations/").status_code == 403


def test_site_scoped_user_sees_only_their_sites(ops_data, make_scoped_member):
    p = ops_data
    scoped = make_scoped_member(p["org"], "ops2@alpha.test", "operations_manager", [p["site2"]])
    c = api(scoped.user, p["org"])
    k = c.get("/api/v1/dashboards/operations/").json()["data"]["kpis"]
    assert k["created"] == 2 and k["completed"] == 1
    assert c.get("/api/v1/dashboards/operations/", {"site": str(p["site"].pk)}).status_code == 404
    assert c.get("/api/v1/dashboards/operations/", {"site": str(p["site2"].pk)}).status_code == 200
    page = web(scoped.user).get("/app/dashboards/?section=operations").content.decode()
    assert "A2" in page and ">A1<" not in page


def test_role_visibility(ops_data, make_member):
    p = ops_data
    c = {k: api(p[k].user, p["org"]) for k in ("tech", "ops", "reader", "planner", "sup")}
    stores = api(make_member(p["org"], "stores2@alpha.test", "stores_manager").user, p["org"])
    am = api(make_member(p["org"], "am@alpha.test", "asset_manager").user, p["org"])
    assert c["tech"].get("/api/v1/dashboards/").status_code == 403
    assert c["tech"].get("/api/v1/dashboards/operations/").status_code == 403
    assert c["tech"].get("/api/v1/dashboards/my-work/").status_code == 200
    assert stores.get("/api/v1/dashboards/inventory/").status_code == 403  # no report.view
    assert am.get("/api/v1/dashboards/assets/").status_code == 200
    assert am.get("/api/v1/dashboards/inventory/").status_code == 403  # report.view but no inventory.view
    assert c["planner"].get("/api/v1/dashboards/maintenance/").status_code == 403  # planner holds no report.view
    assert set(c["ops"].get("/api/v1/dashboards/").json()["sections"]) >= {"operations", "assets", "service"}
    assert set(c["reader"].get("/api/v1/dashboards/").json()["sections"]) == set(metrics.SECTIONS)
    assert c["ops"].get("/api/v1/dashboards/nope/").status_code == 404
    assert APIClient().get("/api/v1/dashboards/").status_code in (401, 403)
    assert web(p["tech"].user).get("/app/dashboards/").status_code == 403
    assert web(p["tech"].user).get("/app/dashboards/my-work/").status_code == 200
    assert web(p["ops"].user).get("/app/dashboards/").status_code == 200


def test_technician_my_work_only_counts_their_own_jobs(ops_data):
    p = ops_data
    mine = get(p, "tech", "my-work")["kpis"]
    other = get(p, "tech2", "my-work")["kpis"]
    assert mine["completed"] == 4 and other["completed"] == 0 and other["hours"] == 0
    assert mine["hours"] == 6.0  # 4 completed jobs x 1.5 h


def test_invalid_filters_are_rejected(ops_data):
    c = api(ops_data["ops"].user, ops_data["org"])
    for params in ({"from": "2026-13-01"}, {"to": "yesterday"}, {"from": "2026-05-02", "to": "2026-05-01"},
                   {"from": "2020-01-01", "to": "2026-01-01"}):
        assert c.get("/api/v1/dashboards/operations/", params).status_code == 400, params
    assert c.get("/api/v1/dashboards/operations/", {"site": "not-a-uuid"}).status_code == 404
    page = web(ops_data["ops"].user).get("/app/dashboards/?from=zzz")
    assert page.status_code == 200 and "must be a date" in page.content.decode()


# --- zero data --------------------------------------------------------------------------------------------------------


def test_zero_data_is_honest(org_b, make_member):
    owner = make_member(org_b, "ops@empty.test", "operations_manager")
    p = {"org": org_b, "ops": owner}
    ops = get(p, "ops", "operations")
    assert ops["kpis"]["open_total"] == 0 and ops["technicians"] == [] and ops["overdue_list"] == []
    a = get(p, "ops", "assets")
    assert a["kpis"]["mttr_hours"] is None and a["kpis"]["mtbf_hours"] is None and a["kpis"]["downtime_hours"] == 0
    assert get(p, "ops", "maintenance")["kpis"]["compliance_percent"] is None
    svc = api(owner.user, org_b).get("/api/v1/dashboards/service/").json()["data"]
    assert svc["requests"]["created"] == 0 and svc["sla"]["response"]["compliance_percent"] is None
    html = web(owner.user).get("/app/dashboards/?section=assets").content.decode()
    assert "n/a" in html


# --- assets: downtime, MTTR, MTBF ---------------------------------------------------------------------------------------


def test_downtime_mttr_mtbf_reconcile(p3):
    now = timezone.now()
    a = p3["asset"]
    r1 = incidents.create_request(p3["org"], asset=a, reporter=p3["tech"], title="Failure one",
                                  actor=p3["tech"].user, downtime_started_at=now - timedelta(hours=30))
    incidents.set_downtime(r1, started_at=now - timedelta(hours=30), ended_at=now - timedelta(hours=26),
                           actor=p3["tech"].user)
    r2 = incidents.create_request(p3["org"], asset=a, reporter=p3["tech"], title="Failure two",
                                  actor=p3["tech"].user, downtime_started_at=now - timedelta(hours=10))
    incidents.set_downtime(r2, started_at=now - timedelta(hours=10), ended_at=now - timedelta(hours=8),
                           actor=p3["tech"].user)
    start = (now - timedelta(days=9)).date().isoformat()
    d = get(p3, "ops", "assets", site=str(p3["site"].pk), **{"from": start, "to": now.date().isoformat()})
    k = d["kpis"]
    assert k["failures"] == 2 and k["downtime_hours"] == 6.0 and k["mttr_hours"] == 3.0
    assert k["assets_in_scope"] == 1
    assert k["mtbf_hours"] == round((10 * 24 * 1 - 6) / 2, 2) == 117.0
    assert d["top_downtime"][0]["asset"].startswith("P3-PUMP") and d["top_downtime"][0]["hours"] == 6.0
    assert d["status"] == {"ACTIVE": 1}
    # a window that only overlaps part of the first downtime clips it
    narrow = get(p3, "ops", "assets", site=str(p3["site"].pk),
                 **{"from": (now - timedelta(hours=28)).date().isoformat(), "to": now.date().isoformat()})
    assert narrow["kpis"]["downtime_hours"] >= 2.0
    other_site = get(p3, "ops", "assets", site=str(p3["site2"].pk))
    assert other_site["kpis"]["failures"] == 0 and other_site["kpis"]["mttr_hours"] is None


# --- maintenance: PM compliance --------------------------------------------------------------------------------------


def test_pm_compliance_reconciles(pm_, monkeypatch):
    p = pm_
    freeze(monkeypatch, datetime(2026, 3, 1, 6, 0, tzinfo=UTC))  # schedules are created before they fall due
    plans = [make_plan(p, name=f"Plan {i}") for i in range(3)]
    for plan, start in zip(plans, (date(2026, 3, 10), date(2026, 3, 8), date(2026, 3, 5)), strict=True):
        time_schedule(plan, start_date=start, frequency="YEARLY")
    freeze(monkeypatch, T0)  # 2026-03-10 06:00 UTC: all three are due, two of them already in the past
    pm.run_for_organization(p["org"])
    from apps.maintenance.models import MaintenanceCycle

    by_due = {c.due_date: c for c in MaintenanceCycle.objects.filter(organization=p["org"])}
    assert set(by_due) == {date(2026, 3, 10), date(2026, 3, 8), date(2026, 3, 5)}
    for due in (date(2026, 3, 10), date(2026, 3, 8)):  # completed today: on time for 03-10, late for 03-08
        wo = by_due[due].work_order
        wo = step(wo, "assign", p, "planner", technician=p["tech"])
        wo = step(wo, "dispatch", p, "planner")
        wo = step(wo, "start", p, "tech")
        finish_work(wo, p)
    k = get(p, "ops", "maintenance", **{"from": "2026-03-01", "to": "2026-03-31"})["kpis"]
    assert (k["due_in_window"], k["on_time"], k["late"], k["missed_open"]) == (3, 1, 1, 1)
    assert k["compliance_percent"] == round(100 / 3, 1)
    assert k["generated_in_window"] == 3 and k["pm_work_orders"] == 3


# --- service and SLA ---------------------------------------------------------------------------------------------------


def test_service_section_counts_requests_and_breaches(sla_):
    p = sla_
    sev = ["HIGH", "HIGH", "LOW"]
    reqs = [incidents.create_request(p["org"], asset=p["asset"], reporter=p["tech"], title=f"Req {i}",
                                     severity=s, actor=p["tech"].user) for i, s in enumerate(sev)]
    incidents.transition(reqs[0], action="triage", actor=p["ops"].user)
    d = get(p, "ops", "service")
    r = d["requests"]
    assert r["created"] == 3 and r["awaiting_triage"] == 2 and r["by_severity"] == {"HIGH": 2, "LOW": 1}
    assert r["incidents"] == 3 and r["from_clients"] == 0 and d["sla"]["trackings"] >= 2
    assert d["sla"]["breaches"] == 0
    assert get(p, "ops", "service", site=str(p["site2"].pk))["requests"]["created"] == 0


# --- inventory ---------------------------------------------------------------------------------------------------------


def test_parts_consumption_reconciles_with_the_ledger(inv_):
    p = inv_
    wo = wo_in_progress(p)
    inv.receive(p["wh"], p["part"], 10, actor=p["stores"].user)
    line = inv.request_part(wo, p["part"], 6, actor=p["tech"].user, membership=p["tech"])
    inv.issue(line, p["wh"], 5, actor=p["stores"].user)
    inv.return_stock(line, 2, actor=p["stores"].user)
    inv.set_levels(p["wh"], p["part"], min_level=8, max_level=50, reorder_quantity=5, actor=p["stores"].user)
    c = api(p["ops"].user, p["org"])
    d = c.get("/api/v1/dashboards/inventory/").json()["data"]
    row = d["top_parts"][0]
    assert (row["issued"], row["returned"], row["net"]) == (5.0, 2.0, 3.0) and row["part"].startswith("SEAL-100")
    assert d["movements_by_type"].get("RECEIPT") == 1 and d["movements_by_type"].get("ISSUE") == 1
    assert d["kpis"]["low_stock_balances"] == 1  # 10 - 5 + 2 = 7 on hand <= minimum 8
    assert c.get("/api/v1/dashboards/inventory/", {"site": str(p["site2"].pk)}).json()["data"]["top_parts"] == []


# --- performance and pages ---------------------------------------------------------------------------------------------


def test_dashboard_query_count_does_not_grow_with_data(ops_data):
    p = ops_data
    c = api(p["ops"].user, p["org"])
    c.get("/api/v1/dashboards/operations/")  # warm caches (permissions, content types)
    with CaptureQueriesContext(connection) as small:
        c.get("/api/v1/dashboards/operations/")
    for i in range(15):
        new_wo(p, title=f"More {i}")
    with CaptureQueriesContext(connection) as big:
        c.get("/api/v1/dashboards/operations/")
    assert len(big) == len(small) and len(small) < 30


def test_pages_render_for_every_section(ops_data):
    cl = web(ops_data["reader"].user)
    for section in metrics.SECTIONS:
        r = cl.get(f"/app/dashboards/?section={section}")
        assert r.status_code == 200, section
        html = r.content.decode()
        assert "dash-filters" in html and 'name="viewport"' in html
    ops = cl.get("/app/dashboards/?section=operations").content.decode()
    assert 'data-kpi="open_work_orders"' in ops and 'data-kpi="overdue_work"' in ops


def test_definitions_are_published(ops_data):
    r = api(ops_data["ops"].user, ops_data["org"]).get("/api/v1/dashboards/")
    defs = r.json()["definitions"]
    assert {"mttr", "mtbf", "pm_compliance", "utilization", "parts_consumption"} <= set(defs)
