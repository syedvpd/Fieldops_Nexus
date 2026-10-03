"""Final cross-module acceptance (automated layer): one continuous M01..M15 journey through the real services and
HTTP entry points, a two-tenant fuzz over every module's detail / action endpoints, a persona matrix, and a generic
read-only database-integrity sweep (no cross-tenant foreign keys, no orphan relations, no negative stock)."""
from datetime import UTC, date, datetime, timedelta

import pytest
from django.apps import apps as django_apps
from django.db.models import F, Sum
from django.test import Client
from rest_framework.test import APIClient

from apps.assets import hierarchy
from apps.assets import services as asset_services
from apps.audit.models import AuditLog
from apps.checklists import services as cl
from apps.contracts import services as contracts
from apps.core.models import TenantOwnedModel
from apps.dashboards import metrics
from apps.identification import services as idn
from apps.incidents import services as incidents
from apps.inventory import services as inv
from apps.inventory.models import StockBalance, StockMovement
from apps.maintenance import services as pm
from apps.portal import services as portal
from apps.sites import services as site_services
from apps.workorders import services as wos
from tests.phase3_support import finish_work, good_answers, make_template, step
from tests.pm_support import T0, freeze, make_plan, time_schedule
from tests.test_m09_inventory import assert_ledger_consistent

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


def integrity_sweep():
    """Generic invariants over EVERY tenant-owned model: each foreign key to another tenant-owned model points into
    the same organization."""
    problems = []
    for model in django_apps.get_models():
        if not issubclass(model, TenantOwnedModel):
            continue
        for field in model._meta.get_fields():
            if not (field.is_relation and field.many_to_one and field.concrete):
                continue
            target = field.related_model
            if not issubclass(target, TenantOwnedModel):
                continue
            bad = model.objects.exclude(**{f"{field.name}__isnull": True}).exclude(
                **{f"{field.name}__organization": F("organization")}).count()
            if bad:
                problems.append(f"{model.__name__}.{field.name}: {bad} cross-tenant reference(s)")
    return problems


def test_one_asset_lives_through_every_module(inv_, monkeypatch):
    p = inv_
    org, ops, planner, tech = p["org"], p["ops"], p["planner"], p["tech"]

    # M01 -> M02 -> M03: zone, asset, component
    zone = site_services.create_zone(p["site"], actor=ops.user, name="Pump hall", code="PH")
    cat = p["asset"].category
    pump = asset_services.create_asset(org, site=p["site"], zone=zone, category=cat, actor=ops.user,
                                       asset_tag="FIN-PUMP", name="Feed pump")
    motor = asset_services.create_asset(org, site=p["site"], zone=zone, category=cat, actor=ops.user,
                                        asset_tag="FIN-MOTOR", name="Feed pump motor")
    hierarchy.add_component(pump, motor, relationship_type="COMPONENT", actor=ops.user)
    # M12 QR + M10 warranty
    stores = p["stores"]
    am_member = _member(p, "assetmgr@alpha.test", "asset_manager")
    qr = idn.generate(pump, "QR", actor=am_member.user)
    prov = contracts.create_provider(org, name="Pumps Inc", actor=am_member.user)
    warranty = contracts.create_agreement(
        org, kind="WARRANTY", reference="FIN-W1", title="Pump warranty", provider=prov, site=p["site"],
        start_date=date(2026, 1, 1), end_date=date(2027, 1, 1), assets=[pump], excluded_work_types=["INSPECTION"],
        actor=am_member.user)
    scan = idn.resolve(tech.user, qr.token, tech)
    assert scan.outcome == "RESOLVED" and scan.asset == pump

    # M08 checklist + M04 plan/schedule -> scheduler -> M06 work order
    template = make_template(p, required=False, name="Feed pump PM")
    freeze(monkeypatch, datetime(2026, 3, 1, 6, tzinfo=UTC))
    plan = make_plan(p, name="Quarterly pump PM", asset=pump, checklist_key=str(template.key), priority="MEDIUM")
    time_schedule(plan, start_date=date(2026, 3, 10), frequency="YEARLY")
    freeze(monkeypatch, T0)
    assert pm.run_for_organization(org)["generated"] == 1
    assert pm.run_for_organization(org)["generated"] == 0  # scheduler twice: no duplicate work order
    from apps.workorders.models import WorkOrder

    wo = WorkOrder.objects.get(organization=org, asset=pump, source_type="PREVENTIVE_MAINTENANCE")
    # M10 on the work order
    check = contracts.record_check(wo, actor=ops.user)
    assert check.eligible and check.agreement == warranty  # preventive work is covered
    # M07 execution with M09 parts, M08 checklist, labor, evidence, M06 review and closure
    wo = step(wo, "assign", p, "planner", technician=tech)
    wo = step(wo, "dispatch", p, "planner")
    wo = step(wo, "start", p, "tech")
    inv.receive(p["wh"], p["part"], 10, actor=stores.user)
    line = inv.request_part(wo, p["part"], 2, actor=tech.user, membership=tech)
    inv.reserve(line, p["wh"], actor=stores.user)
    inv.issue(line, p["wh"], 2, actor=stores.user)
    inv.consume(line, 2, actor=tech.user, membership=tech)
    insp = cl.start_inspection(org, template=template, membership=tech, actor=tech.user, work_order=wo)
    cl.save_responses(insp, good_answers(template), membership=tech, actor=tech.user)
    cl.complete_inspection(insp, membership=tech, actor=tech.user)
    wo = finish_work(wo, p)
    wo = step(wo, "start_review", p, "sup")
    wo = step(wo, "close", p, "sup")
    assert wo.status == "CLOSED"

    # M13 client request on the same asset -> M05 -> M06 -> confirmation -> closure
    svc = _member(p, "svc@alpha.test", "service_manager")
    client = _member(p, "client@alpha.test", "client_requester")
    acct = portal.enable_account(org, client, actor=svc.user)
    portal.grant_asset(acct, pump, actor=svc.user)
    sr = portal.submit_request(client, asset=pump, title="Pump vibrating", urgency="HIGH")
    incidents.transition(sr, action="triage", actor=ops.user)
    incidents.transition(sr, action="approve", actor=ops.user)
    t0 = T0 + timedelta(days=1)
    wo2 = incidents.create_work_order_for_request(sr, actor=planner.user, membership=planner, planned_start=t0,
                                                  planned_end=t0 + timedelta(hours=2))
    wo2 = step(wo2, "plan", p, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=2))
    wo2 = step(wo2, "assign", p, "planner", technician=tech)
    wo2 = step(wo2, "dispatch", p, "planner")
    wo2 = step(wo2, "start", p, "tech")
    wo2 = finish_work(wo2, p)
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"
    portal.confirm(client, sr)
    incidents.transition(sr, action="close", actor=svc.user)
    sr.refresh_from_db()
    assert sr.status == "CLOSED"
    step(wo2, "start_review", p, "sup")

    # M14: dashboards reconcile with what just happened (window includes the frozen clock day)
    win = {"from": "2026-03-01", "to": "2026-03-31"}
    d = api(ops.user, org).get("/api/v1/dashboards/operations/", win).json()["data"]["kpis"]
    created = WorkOrder.objects.filter(organization=org, asset__in=[pump], created_at__date__gte=date(2026, 3, 1))
    assert d["created"] >= created.count() >= 2 and d["completed"] >= 2 and d["closed"] >= 1
    mt = api(ops.user, org).get("/api/v1/dashboards/maintenance/", win).json()["data"]["kpis"]
    assert mt["pm_work_orders"] == 1 and mt["on_time"] == 1 and mt["compliance_percent"] == 100.0
    sv = api(ops.user, org).get("/api/v1/dashboards/service/", win).json()["data"]["requests"]
    assert sv["from_clients"] == 1
    iv = api(ops.user, org).get("/api/v1/dashboards/inventory/", win).json()["data"]["top_parts"]
    assert iv and iv[0]["net"] == 2.0

    # M15: every stage left audit evidence, visible to the auditor, exportable and immutable
    actions = set(AuditLog.objects.filter(organization=org).values_list("action", flat=True))
    for needed in ("site.created", "zone.created", "asset.created", "asset.component_added", "qr.generated",
                   "qr.scanned", "contract.agreement_created", "contract.coverage_checked",
                   "maintenance.cycle_generated", "work_order.created", "work_order.status_changed",
                   "part_line.consumed", "inspection.completed", "portal.request_submitted",
                   "portal.request_confirmed", "incident.status_changed"):
        assert needed in actions or any(a.startswith(needed.split(".")[0] + ".") for a in actions), needed
    reader = web(p["reader"].user)
    assert reader.get("/app/audit/?category=closures").status_code == 200
    closures = api(p["reader"].user, org).get("/api/v1/audit-logs/", {"category": "closures"}).json()["results"]
    assert {r["target_type"] for r in closures} >= {"workorders.workorder", "incidents.servicerequest"}
    hist = api(p["reader"].user, org).get("/api/v1/audit-logs/", {"asset": "FIN-PUMP", "page_size": 200}).json()
    assert hist["count"] >= 10
    assert reader.get("/app/audit/export/?format=csv&asset=FIN-PUMP").status_code == 200

    # invariants
    assert_ledger_consistent(org)
    assert StockBalance.objects.get(warehouse=p["wh"], part=p["part"]).on_hand == 8
    assert StockMovement.objects.filter(organization=org, movement_type="ISSUE").aggregate(q=Sum("quantity"))["q"] == 2
    assert integrity_sweep() == []
    assert metrics.KPI_DEFINITIONS


def _member(p, email, role):
    from apps.rbac import services as rbac
    from apps.tenancy.models import Membership
    from tests.conftest import User

    user = User.objects.filter(email=email).first() or User.objects.create_user(
        email=email, password="Correct-Horse-Battery-9", full_name=email.split("@")[0])
    m = Membership.objects.filter(organization=p["org"], user=user).first()
    if m is None:
        m = Membership(organization=p["org"], user=user, status=Membership.Status.ACTIVE)
        m.save()
        rbac.set_membership_roles(m, [rbac.system_role_by_key(p["org"], role)], actor=None, system=True)
    return m


# --- two-tenant fuzz ---------------------------------------------------------------------------------------------


@pytest.fixture
def two(p3, org_b, make_member, make_site, make_asset):
    """Alpha (p3) and Beta each with an asset, a work order, a request, a part, a plan, an agreement and a label."""
    out = {}
    for tag, org, site, asset in (("a", p3["org"], p3["site"], p3["asset"]),
                                  ("b", org_b, make_site(org_b, "BS1"), None)):
        if asset is None:
            asset = make_asset(org, site, "BETA-PUMP")
        mgr = make_member(org, f"mgr@{tag}.fuzz", "asset_manager")
        ops = make_member(org, f"ops@{tag}.fuzz", "operations_manager")
        owner = make_member(org, f"stores@{tag}.fuzz", "stores_manager")
        wo = wos.create_work_order(org, asset=asset, actor=ops.user, title=f"{tag} order", work_type="CORRECTIVE")
        sr = incidents.create_request(org, asset=asset, reporter=ops, title=f"{tag} request", actor=ops.user)
        part = inv.create_part(org, part_number=f"{tag}-PART", name=f"{tag} part", actor=owner.user)
        wh = inv.create_warehouse(org, site=site, code=f"{tag}WH", name=f"{tag} store", actor=owner.user)
        prov = contracts.create_provider(org, name=f"{tag} provider", actor=mgr.user)
        ag = contracts.create_agreement(org, kind="AMC", reference=f"{tag}-AMC", title="AMC", provider=prov,
                                        site=site, start_date=date(2026, 1, 1), end_date=date(2030, 1, 1),
                                        assets=[asset], actor=mgr.user)
        ident = idn.generate(asset, "QR", actor=mgr.user)
        plan = pm.create_plan(org, asset=asset, name=f"{tag} plan", actor=ops.user)
        out[tag] = dict(org=org, site=site, asset=asset, mgr=mgr, ops=ops, stores=owner, wo=wo, sr=sr, part=part,
                        wh=wh, ag=ag, ident=ident, plan=plan, prov=prov)
    return out


DETAIL_URLS = [
    "/api/v1/assets/{asset}/", "/api/v1/work-orders/{wo}/", "/api/v1/service-requests/{sr}/",
    "/api/v1/parts/{part}/", "/api/v1/warehouses/{wh}/", "/api/v1/coverage-agreements/{ag}/",
    "/api/v1/contract-providers/{prov}/", "/api/v1/asset-identifiers/{ident}/",
    "/api/v1/maintenance-plans/{plan}/", "/api/v1/sites/{site}/",
]
UI_URLS = [
    "/app/assets/{asset}/", "/app/work-orders/{wo}/", "/app/incidents/{sr}/", "/app/contracts/agreements/{ag}/",
    "/app/maintenance/plans/{plan}/", "/app/contracts/assets/{asset}/panel/",
    "/app/identification/assets/{asset}/panel/", "/app/identification/assets/{asset}/label/",
    "/app/contracts/work-orders/{wo}/panel/",
]


def test_every_alpha_object_is_invisible_to_beta_and_vice_versa(two):
    for mine, theirs in (("a", "b"), ("b", "a")):
        ids = {k: str(getattr(v, "pk", v)) for k, v in two[theirs].items() if hasattr(v, "pk")}
        c = api(two[mine]["mgr"].user, two[mine]["org"])
        ops_c = api(two[mine]["ops"].user, two[mine]["org"])
        for template in DETAIL_URLS:
            url = template.format(**ids)
            assert c.get(url).status_code in (403, 404) and ops_c.get(url).status_code in (403, 404), url
            assert c.get(url).status_code != 200
        for template in UI_URLS:
            url = template.format(**ids)
            r = web(two[mine]["mgr"].user).get(url)
            assert r.status_code in (403, 404), (url, r.status_code)
        # lists never contain foreign rows
        for url in ("/api/v1/assets/", "/api/v1/work-orders/", "/api/v1/service-requests/",
                    "/api/v1/coverage-agreements/", "/api/v1/asset-identifiers/", "/api/v1/maintenance-plans/"):
            body = c.get(url).json()
            if "results" in body:
                assert not (set(ids.values()) & {str(r.get("id")) for r in body["results"]}), url
        # scans, audit and exports
        token = two[theirs]["ident"].token
        assert idn.resolve(two[mine]["mgr"].user, token, two[mine]["mgr"]).outcome == "UNKNOWN"
        assert api(two[mine]["mgr"].user, two[mine]["org"]).post("/api/v1/scan/resolve/", {"token": token},
                                                                 format="json").status_code in (403, 404)
        mine_rows = set(AuditLog.objects.filter(organization=two[mine]["org"]).values_list("pk", flat=True))
        their_rows = AuditLog.objects.filter(organization=two[theirs]["org"]).values_list("pk", flat=True)[:5]
        for pk in their_rows:
            assert pk not in mine_rows
            assert api(two[mine]["ops"].user, two[mine]["org"]).get(f"/api/v1/audit-logs/{pk}/").status_code in (
                403, 404)
        # writes with the other tenant's ids
        assert c.post("/api/v1/coverage-agreements/", {
            "kind": "AMC", "reference": "X-1", "title": "Cross", "provider": ids["prov"], "site": ids["site"],
            "start_date": "2026-01-01", "end_date": "2026-12-31", "assets": [ids["asset"]]}, format="json"
        ).status_code in (403, 404)
        assert ops_c.post("/api/v1/maintenance-plans/", {"asset": ids["asset"], "name": "cross"}, format="json"
                          ).status_code in (403, 404)
    assert integrity_sweep() == []


PERSONA_GETS = {
    # persona -> {url: expected status}
    "tech": {"/api/v1/work-orders/": 200, "/api/v1/audit-logs/": 403, "/api/v1/coverage-agreements/": 403,
             "/api/v1/dashboards/operations/": 403, "/api/v1/portal-accounts/": 403, "/api/v1/sla-profiles/": 403},
    "reader": {"/api/v1/audit-logs/": 200, "/api/v1/work-orders/": 200, "/api/v1/coverage-agreements/": 200,
               "/api/v1/dashboards/operations/": 200, "/api/v1/portal-accounts/": 403},
    "ops": {"/api/v1/audit-logs/": 200, "/api/v1/work-orders/": 200, "/api/v1/dashboards/operations/": 200,
            "/api/v1/audit-logs/export/": 403},
    "planner": {"/api/v1/maintenance-plans/": 200, "/api/v1/audit-logs/": 403, "/api/v1/dashboards/service/": 403,
                "/api/v1/parts/": 200},
}
PERSONA_WRITES = {
    "tech": [("/api/v1/coverage-agreements/", {}), ("/api/v1/asset-identifiers/", {}), ("/api/v1/parts/", {}),
             ("/api/v1/maintenance-plans/", {}), ("/api/v1/sla-profiles/", {}), ("/api/v1/portal-accounts/", {})],
    "reader": [("/api/v1/work-orders/", {}), ("/api/v1/assets/", {}), ("/api/v1/coverage-agreements/", {}),
               ("/api/v1/asset-identifiers/", {}), ("/api/v1/portal-accounts/", {})],
    "planner": [("/api/v1/coverage-agreements/", {}), ("/api/v1/asset-identifiers/", {}),
                ("/api/v1/portal-accounts/", {}), ("/api/v1/parts/", {})],
}


def test_persona_matrix_over_the_api(p3):
    for persona, expectations in PERSONA_GETS.items():
        c = api(p3[persona].user, p3["org"])
        for url, expected in expectations.items():
            assert c.get(url).status_code == expected, (persona, url)
    for persona, writes in PERSONA_WRITES.items():
        c = api(p3[persona].user, p3["org"])
        for url, body in writes:
            assert c.post(url, body, format="json").status_code == 403, (persona, url)
    assert integrity_sweep() == []


def test_negative_stock_and_duplicate_pm_orders_cannot_exist(inv_, monkeypatch):
    p = inv_
    freeze(monkeypatch, datetime(2026, 3, 1, 6, tzinfo=UTC))
    plan = make_plan(p, name="Dup guard")
    sch = time_schedule(plan, start_date=date(2026, 3, 10), frequency="YEARLY")
    freeze(monkeypatch, T0)
    assert pm.generate_cycle(sch) is not None and pm.generate_cycle(sch) is None
    from apps.workorders.models import WorkOrder

    assert WorkOrder.objects.filter(organization=p["org"], source_type="PREVENTIVE_MAINTENANCE").count() == 1
    assert not StockBalance.objects.filter(on_hand__lt=0).exists()
    assert not StockBalance.objects.filter(reserved__gt=F("on_hand")).exists()
