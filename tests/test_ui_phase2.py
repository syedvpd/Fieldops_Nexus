"""Phase 2 HTML UI: pages render, every state-changing control posts to a real endpoint that persists and audits,
forbidden roles are refused, foreign objects are 404, CSRF is enforced."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.incidents import services as incidents
from apps.incidents.models import Downtime, ServiceRequest
from apps.workorders import services as wos
from apps.workorders.models import WorkOrder, WorkOrderLabor, WorkOrderMaterial

pytestmark = pytest.mark.django_db


def dtl(delta_hours=0):
    return (timezone.localtime() + timedelta(hours=delta_hours)).strftime("%Y-%m-%dT%H:%M")


@pytest.fixture
def w(org_a, site_a1, make_asset, make_member):
    return {
        "org": org_a, "site": site_a1, "asset": make_asset(org_a, site_a1, "UI-GEN"),
        "tech": make_member(org_a, "tech@alpha.test", "technician"),
        "ops": make_member(org_a, "ops@alpha.test", "operations_manager"),
        "planner": make_member(org_a, "planner@alpha.test", "maintenance_planner"),
        "sup": make_member(org_a, "sup@alpha.test", "supervisor"),
        "reader": make_member(org_a, "reader@alpha.test", "auditor"),
    }


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


def audited(org, action):
    return AuditLog.objects.filter(organization=org, action=action).exists()


def test_reactive_journey_through_the_html_ui(w):
    org = w["org"]
    tech, ops, planner, sup = (client_for(w[k].user) for k in ("tech", "ops", "planner", "sup"))

    # lists and forms render
    for c, url in ((tech, "/app/incidents/"), (tech, "/app/incidents/new/"), (ops, "/app/work-orders/"),
                   (planner, "/app/work-orders/new/")):
        assert c.get(url).status_code == 200, url

    # 1. report (invalid first: nothing stored), then valid
    bad = tech.post("/app/incidents/new/", {"asset": w["asset"].pk, "kind": "INCIDENT", "title": "ab", "severity": "HIGH",
                                            "service_impact": "FULL_OUTAGE"})
    assert bad.status_code == 400 and not ServiceRequest.objects.exists()
    r = tech.post("/app/incidents/new/", {"asset": w["asset"].pk, "kind": "INCIDENT", "title": "Generator tripped",
                                          "description": "Overheat alarm", "severity": "HIGH",
                                          "service_impact": "FULL_OUTAGE", "downtime_started_at": dtl(-2)})
    assert r.status_code == 302
    sr = ServiceRequest.objects.get()
    assert sr.status == "NEW" and Downtime.objects.filter(request=sr).exists() and audited(org, "incident.created")
    page = tech.get(r.url).content.decode()
    assert "Generator tripped" in page and "/transition/triage/" not in page  # no triage button for a technician

    # 2. triage / approve through the buttons
    detail = ops.get(f"/app/incidents/{sr.pk}/").content.decode()
    assert f"/app/incidents/{sr.pk}/transition/triage/" in detail
    assert tech.post(f"/app/incidents/{sr.pk}/transition/triage/").status_code == 403
    for act in ("triage", "approve"):
        assert ops.post(f"/app/incidents/{sr.pk}/transition/{act}/").status_code == 302
    sr.refresh_from_db()
    assert sr.status == "APPROVED"

    # 3. planner creates the work order from the approved request page
    assert "Create work order" in planner.get(f"/app/incidents/{sr.pk}/").content.decode()
    r = planner.post(f"/app/incidents/{sr.pk}/create-work-order/", {"title": "", "priority": ""})
    wo = WorkOrder.objects.get()
    assert r.status_code == 302 and r.url == f"/app/work-orders/{wo.pk}/" and wo.status == "DRAFT"
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"

    # 4. plan -> assign -> dispatch, each through its own form
    page = planner.get(f"/app/work-orders/{wo.pk}/").content.decode()
    assert f"/app/work-orders/{wo.pk}/transition/plan/" in page and "/transition/close/" not in page
    r = planner.post(f"/app/work-orders/{wo.pk}/transition/plan/", {
        "planned_start": dtl(24), "planned_end": dtl(28), "estimated_hours": "3", "priority": "HIGH"})
    assert r.status_code == 302
    wo.refresh_from_db()
    assert wo.status == "PLANNED" and wo.priority == "HIGH"
    page = planner.get(f"/app/work-orders/{wo.pk}/").content.decode()
    assert "tech" in page and "Choose a technician" in page
    planner.post(f"/app/work-orders/{wo.pk}/transition/assign/", {"technician": w["tech"].pk})
    planner.post(f"/app/work-orders/{wo.pk}/transition/dispatch/")
    wo.refresh_from_db()
    assert wo.status == "DISPATCHED" and wo.assigned_to_id == w["tech"].pk

    # 5. the technician executes: start -> hold -> resume
    assert "/transition/start/" in tech.get(f"/app/work-orders/{wo.pk}/").content.decode()
    tech.post(f"/app/work-orders/{wo.pk}/transition/start/")
    sr.refresh_from_db()
    assert WorkOrder.objects.get().status == "IN_PROGRESS" and sr.status == "IN_SERVICE"
    tech.post(f"/app/work-orders/{wo.pk}/transition/hold/", {"reason": ""})  # reason missing: refused
    assert WorkOrder.objects.get().status == "IN_PROGRESS"
    tech.post(f"/app/work-orders/{wo.pk}/transition/hold/", {"reason": "Waiting for part"})
    assert WorkOrder.objects.get().status == "ON_HOLD"
    tech.post(f"/app/work-orders/{wo.pk}/transition/resume/")
    assert WorkOrder.objects.get().status == "IN_PROGRESS"

    # 6. labor, material, evidence, completion
    for tab in ("work", "evidence", "history", "overview"):
        assert tech.get(f"/app/work-orders/{wo.pk}/?tab={tab}").status_code == 200
    tech.post(f"/app/work-orders/{wo.pk}/labor/", {"work_date": timezone.localdate().isoformat(), "hours": "0"})
    assert not WorkOrderLabor.objects.exists()
    tech.post(f"/app/work-orders/{wo.pk}/labor/", {"work_date": timezone.localdate().isoformat(), "hours": "2.5",
                                                   "notes": "hose"})
    tech.post(f"/app/work-orders/{wo.pk}/materials/", {"description": "Coolant hose", "quantity": "2", "unit": "pcs"})
    assert WorkOrderLabor.objects.count() == 1 and WorkOrderMaterial.objects.count() == 1
    tech.post(f"/app/work-orders/{wo.pk}/transition/complete/", {"resolution_notes": "Replaced the hose properly."})
    assert WorkOrder.objects.get().status == "IN_PROGRESS"  # evidence missing
    bad_file = SimpleUploadedFile("x.exe", b"MZ....")
    tech.post(f"/app/work-orders/{wo.pk}/evidence/", {"file": bad_file})
    assert not wos.evidence_for(wo).exists()
    tech.post(f"/app/work-orders/{wo.pk}/evidence/", {"file": SimpleUploadedFile("after.txt", b"hose replaced"),
                                                      "description": "after"})
    assert wos.evidence_for(wo).count() == 1
    tech.post(f"/app/work-orders/{wo.pk}/transition/complete/", {"resolution_notes": "Replaced the hose properly."})
    sr.refresh_from_db()
    assert WorkOrder.objects.get().status == "COMPLETED" and sr.status == "RESOLVED"
    assert Downtime.objects.get().ended_at is not None

    # 7. supervisor review and close; requester side
    sup.post(f"/app/work-orders/{wo.pk}/transition/start_review/")
    sup.post(f"/app/work-orders/{wo.pk}/transition/close/")
    assert WorkOrder.objects.get().status == "CLOSED"
    ops.post(f"/app/incidents/{sr.pk}/transition/confirm/")
    ops.post(f"/app/incidents/{sr.pk}/transition/close/")
    sr.refresh_from_db()
    assert sr.status == "CLOSED"
    assert "Closed" in ops.get(f"/app/incidents/{sr.pk}/?tab=history").content.decode()
    for action in ("incident.created", "incident.status_changed", "work_order.created", "work_order.status_changed",
                   "work_order.labor_recorded", "work_order.material_recorded", "work_order.evidence_added",
                   "incident.downtime_updated"):
        assert audited(org, action), action


def test_forbidden_roles_and_foreign_objects(w, org_b, site_b1, make_asset, make_member):
    sr = incidents.create_request(w["org"], asset=w["asset"], reporter=w["ops"], actor=w["ops"].user, title="Leak")
    wo = wos.create_work_order(w["org"], asset=w["asset"], actor=None, title="Fix leak")
    reader, tech = client_for(w["reader"].user), client_for(w["tech"].user)
    assert reader.get(f"/app/incidents/{sr.pk}/").status_code == 200
    assert reader.get(f"/app/work-orders/{wo.pk}/").status_code == 200
    assert "Report incident" not in reader.get("/app/incidents/").content.decode()
    assert "New work order" not in reader.get("/app/work-orders/").content.decode()
    for url in ("/app/incidents/new/", "/app/work-orders/new/", f"/app/work-orders/{wo.pk}/edit/",
                f"/app/incidents/{sr.pk}/edit/"):
        assert reader.get(url).status_code == 403, url
    for url in (f"/app/incidents/{sr.pk}/transition/triage/", f"/app/work-orders/{wo.pk}/transition/cancel/",
                f"/app/work-orders/{wo.pk}/labor/", f"/app/incidents/{sr.pk}/downtime/",
                f"/app/work-orders/{wo.pk}/reassign/", f"/app/incidents/{sr.pk}/create-work-order/"):
        assert reader.post(url, {"reason": "xxx"}).status_code == 403, url
    # a technician cannot open work that is not assigned to them, and has no create form
    assert tech.get(f"/app/work-orders/{wo.pk}/").status_code == 404
    assert tech.get("/app/work-orders/new/").status_code == 403
    assert tech.post(f"/app/work-orders/{wo.pk}/transition/start/").status_code == 404
    # other organization
    bob = make_member(org_b, "ops@beta.test", "operations_manager")
    b = client_for(bob.user)
    for url in (f"/app/incidents/{sr.pk}/", f"/app/work-orders/{wo.pk}/", f"/app/incidents/{sr.pk}/?tab=history",
                f"/app/work-orders/{wo.pk}/?tab=work"):
        assert b.get(url).status_code == 404, url
    for url in (f"/app/incidents/{sr.pk}/transition/triage/", f"/app/work-orders/{wo.pk}/transition/cancel/"):
        assert b.post(url, {"reason": "xxx"}).status_code == 404
    sr.refresh_from_db()
    wo.refresh_from_db()
    assert sr.status == "NEW" and wo.status == "DRAFT"
    # the beta list never shows Alpha's records
    page = b.get("/app/incidents/").content.decode() + b.get("/app/work-orders/").content.decode()
    assert "Leak" not in page and "Fix leak" not in page


def test_csrf_is_enforced(w):
    sr = incidents.create_request(w["org"], asset=w["asset"], reporter=w["ops"], actor=w["ops"].user, title="Leak")
    c = Client(enforce_csrf_checks=True)
    c.force_login(w["ops"].user)
    assert c.post(f"/app/incidents/{sr.pk}/transition/triage/").status_code == 403
    sr.refresh_from_db()
    assert sr.status == "NEW"


def test_navigation_entries_follow_permissions(w):
    ops, tech, reader = (client_for(w[k].user).get("/app/").content.decode() for k in ("ops", "tech", "reader"))
    assert "Incidents &amp; Requests" in ops and "Work Orders" in ops
    assert "Incidents &amp; Requests" in tech and "Work Orders" in tech  # view_assigned
    assert "Work Orders" in reader


def test_edit_forms_persist_and_lock(w):
    sr = incidents.create_request(w["org"], asset=w["asset"], reporter=w["ops"], actor=w["ops"].user, title="Leak")
    ops, planner = client_for(w["ops"].user), client_for(w["planner"].user)
    r = ops.post(f"/app/incidents/{sr.pk}/edit/", {"title": "Leak at pump", "description": "d", "severity": "CRITICAL",
                                                   "service_impact": "PARTIAL_OUTAGE", "impact_notes": "line 2"})
    assert r.status_code == 302
    sr.refresh_from_db()
    assert sr.title == "Leak at pump" and sr.severity == "CRITICAL"
    assert audited(w["org"], "incident.updated")
    assert ops.post(f"/app/incidents/{sr.pk}/edit/", {"title": "x", "severity": "LOW", "service_impact": "NONE"}).status_code == 400
    wo = wos.create_work_order(w["org"], asset=w["asset"], actor=None, title="Fix leak")
    r = planner.post(f"/app/work-orders/{wo.pk}/edit/", {
        "title": "Fix leak now", "work_type": "CORRECTIVE", "priority": "URGENT", "planned_start": dtl(2),
        "planned_end": dtl(1)})
    assert r.status_code == 400  # end before start
    r = planner.post(f"/app/work-orders/{wo.pk}/edit/", {"title": "Fix leak now", "work_type": "CORRECTIVE",
                                                         "priority": "URGENT"})
    assert r.status_code == 302
    wo.refresh_from_db()
    assert wo.title == "Fix leak now" and wo.priority == "URGENT"
