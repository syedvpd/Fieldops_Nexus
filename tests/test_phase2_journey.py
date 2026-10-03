"""Phase 2 reactive-breakdown journey over the real API and PostgreSQL:
Organization > Site > Asset > Incident (NEW) > triage > approve > Work Order created (DRAFT) > plan > assign >
dispatch > start > hold > resume > labor / material / evidence > complete > supervisor review > close >
request RESOLVED > confirm > close. Every step is checked in the database and the audit trail."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.incidents.models import Downtime, ServiceRequest, ServiceRequestHistory
from apps.workorders.models import WorkOrder, WorkOrderEvent, WorkOrderLabor, WorkOrderMaterial

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(org_a, site_a1, make_asset, make_member):
    asset = make_asset(org_a, site_a1, "GEN-1", name="Generator 1")
    return {
        "org": org_a, "site": site_a1, "asset": asset,
        "tech": make_member(org_a, "tech@alpha.test", "technician"),
        "ops": make_member(org_a, "ops@alpha.test", "operations_manager"),
        "planner": make_member(org_a, "planner@alpha.test", "maintenance_planner"),
        "sup": make_member(org_a, "sup@alpha.test", "supervisor"),
    }


def actions(org, action):
    return AuditLog.objects.filter(organization=org, action=action).count()


def test_reactive_breakdown_end_to_end(world, as_user):
    org, asset = world["org"], world["asset"]
    tech, ops, planner, sup = (as_user(world[k].user, org) for k in ("tech", "ops", "planner", "sup"))
    start = (timezone.now() - timezone.timedelta(hours=1)).isoformat()

    # 1. technician reports the breakdown with a downtime start
    r = tech.post("/api/v1/service-requests/", {
        "asset": str(asset.pk), "title": "Generator tripped", "description": "Overheat alarm", "severity": "HIGH",
        "service_impact": "FULL_OUTAGE", "downtime_started_at": start}, format="json")
    assert r.status_code == 201, r.content
    req = r.json()
    assert req["status"] == "NEW" and req["number"].startswith("INC-") and req["site_code"] == "A1"
    sr = ServiceRequest.objects.get(pk=req["id"])
    assert sr.reported_by_id == world["tech"].pk and sr.site_id == world["site"].pk
    assert Downtime.objects.get(request=sr).ended_at is None

    # 2. technician cannot triage / approve; ops can, in order
    assert tech.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "triage"}, format="json").status_code == 403
    assert ops.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "approve"}, format="json").status_code == 409
    for act, expect in (("triage", "TRIAGED"), ("approve", "APPROVED")):
        r = ops.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": act}, format="json")
        assert r.status_code == 200 and r.json()["status"] == expect

    # 3. planner turns the approved request into a real work order (DRAFT)
    r = planner.post(f"/api/v1/service-requests/{sr.pk}/create-work-order/", {}, format="json")
    assert r.status_code == 201, r.content
    wo = WorkOrder.objects.get(pk=r.json()["id"])
    assert wo.status == "DRAFT" and wo.source_request_id == sr.pk and wo.priority == "HIGH"
    assert wo.number.startswith("WO-") and wo.asset_id == asset.pk and wo.site_id == sr.site_id
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"
    # never DRAFT -> CLOSED, and a second work order for the same request is refused
    assert planner.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "close"}, format="json").status_code == 403
    assert ops.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "close"}, format="json").status_code == 409
    assert planner.post(f"/api/v1/service-requests/{sr.pk}/create-work-order/", {}, format="json").status_code == 409

    # 4. plan -> assign -> dispatch
    t0 = timezone.now() + timezone.timedelta(hours=1)
    plan = {"action": "plan", "planned_start": t0.isoformat(), "planned_end": (t0 + timezone.timedelta(hours=4)).isoformat(),
            "estimated_hours": "3.5"}
    assert planner.post(f"/api/v1/work-orders/{wo.pk}/transition/", plan, format="json").json()["status"] == "PLANNED"
    r = planner.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "assign", "technician": str(world["tech"].pk)},
                     format="json")
    assert r.status_code == 200 and r.json()["assigned_to"] == str(world["tech"].pk)
    assert planner.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "dispatch"}, format="json").json()["status"] == "DISPATCHED"

    # 5. technician starts -> work order IN_PROGRESS and request IN_SERVICE (M06 -> M05)
    r = tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "start"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "IN_PROGRESS"
    sr.refresh_from_db()
    assert sr.status == "IN_SERVICE"

    # 6. hold needs a reason; resume
    assert tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "hold"}, format="json").status_code == 400
    r = tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "hold", "reason": "Waiting for filter"}, format="json")
    assert r.json()["status"] == "ON_HOLD" and r.json()["hold_reason"] == "Waiting for filter"
    assert tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "resume"}, format="json").json()["status"] == "IN_PROGRESS"

    # 7. completion is blocked without notes / evidence, then succeeds with them
    r = tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "complete"}, format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "resolution_notes_required"
    notes = {"action": "complete", "resolution_notes": "Replaced the coolant hose and bled the system."}
    r = tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", notes, format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "evidence_required"
    r = tech.post(f"/api/v1/work-orders/{wo.pk}/evidence/", {"file": SimpleUploadedFile("after.txt", b"hose replaced photo note"),
                  "description": "after repair"}, format="multipart")
    assert r.status_code == 201, r.content
    today = timezone.localdate().isoformat()
    assert tech.post(f"/api/v1/work-orders/{wo.pk}/labor/", {"work_date": today, "hours": "2.5", "notes": "repair"},
                     format="json").status_code == 201
    assert tech.post(f"/api/v1/work-orders/{wo.pk}/materials/", {"description": "Coolant hose", "quantity": "2", "unit": "pcs",
                     "part_number": "CH-10"}, format="json").status_code == 201
    r = tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", notes, format="json")
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    sr.refresh_from_db()
    assert sr.status == "RESOLVED" and sr.resolved_at is not None
    dt = Downtime.objects.get(request=sr)
    assert dt.ended_at is not None and dt.end_source == "work_order" and dt.duration.total_seconds() > 0

    # 8. supervisor review -> close
    assert sup.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "close"}, format="json").status_code == 409
    assert sup.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "start_review"}, format="json").json()["status"] == "SUPERVISOR_REVIEW"
    r = sup.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "close"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "CLOSED"
    wo.refresh_from_db()
    assert wo.closed_at is not None and wo.closed_by_id == world["sup"].user_id

    # 9. the requester side: confirm and close
    assert ops.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "close"}, format="json").status_code == 409
    assert ops.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "confirm"}, format="json").json()["status"] == "CONFIRMED"
    assert ops.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "close"}, format="json").json()["status"] == "CLOSED"

    # PostgreSQL / history / audit evidence
    assert list(ServiceRequestHistory.objects.filter(request=sr).order_by("created_at").values_list("to_status", flat=True)) == [
        "NEW", "TRIAGED", "APPROVED", "WORK_ORDER_CREATED", "IN_SERVICE", "RESOLVED", "CONFIRMED", "CLOSED"]
    assert list(WorkOrderEvent.objects.filter(work_order=wo).order_by("created_at").values_list("action", flat=True)) == [
        "create", "plan", "assign", "dispatch", "start", "hold", "resume", "complete", "start_review", "close"]
    assert WorkOrderLabor.objects.filter(work_order=wo).count() == 1 and WorkOrderMaterial.objects.filter(work_order=wo).count() == 1
    for action, n in (("incident.created", 1), ("incident.status_changed", 7), ("incident.downtime_recorded", 1),
                      ("incident.downtime_updated", 1), ("work_order.created", 1), ("work_order.status_changed", 9),
                      ("work_order.labor_recorded", 1), ("work_order.material_recorded", 1),
                      ("work_order.evidence_added", 1)):
        assert actions(org, action) == n, action
    row = AuditLog.objects.filter(organization=org, action="work_order.status_changed", metadata__action="assign").get()
    assert row.actor_email == "planner@alpha.test" and row.before["status"] == "PLANNED" and row.after["status"] == "ASSIGNED"
