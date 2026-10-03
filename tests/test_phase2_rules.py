"""Phase 2 negative / RBAC / tenant / site-scope / state-machine tests for M05 (incidents) and M06 (work orders)."""
import uuid
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, InvalidTransition, PermissionDenied, ValidationFailed
from apps.core.sequences import next_number
from apps.incidents import services as incidents
from apps.incidents.models import ServiceRequest
from apps.incidents.workflow import REQUEST_STATUS
from apps.workorders import services as wos
from apps.workorders.models import WorkOrder
from apps.workorders.workflow import WORK_ORDER_STATUS

pytestmark = pytest.mark.django_db

NOW = timezone.now


@pytest.fixture
def w(org_a, site_a1, site_a2, make_asset, make_member):
    return {
        "org": org_a, "site": site_a1, "site2": site_a2,
        "asset": make_asset(org_a, site_a1, "P-1"), "asset2": make_asset(org_a, site_a2, "P-2"),
        "tech": make_member(org_a, "tech@alpha.test", "technician"),
        "tech2": make_member(org_a, "tech2@alpha.test", "technician"),
        "ops": make_member(org_a, "ops@alpha.test", "operations_manager"),
        "planner": make_member(org_a, "planner@alpha.test", "maintenance_planner"),
        "sup": make_member(org_a, "sup@alpha.test", "supervisor"),
        "reader": make_member(org_a, "reader@alpha.test", "auditor"),
    }


def new_request(w, asset=None, who="ops", **kw):
    m = w[who]
    return incidents.create_request(w["org"], asset=asset or w["asset"], reporter=m, actor=m.user,
                                    title=kw.pop("title", "Pump leaking"), **kw)


def approved_request(w, **kw):
    sr = new_request(w, **kw)
    for a in ("triage", "approve"):
        sr = incidents.transition(sr, action=a, actor=w["ops"].user)
    return sr


def new_wo(w, asset=None, **kw):
    kw.setdefault("work_type", "CORRECTIVE")
    return wos.create_work_order(w["org"], asset=asset or w["asset"], actor=w["planner"].user, title="Fix pump", **kw)


def step(wo, action, who, w, **data):
    return wos.transition(wo, action=action, actor=w[who].user, membership=w[who], **data)


def to_state(wo, w, target, tech="tech", **kw):
    """Drives a work order forward to ``target`` through the real service transitions (from its current state)."""
    t0 = NOW() + timedelta(days=1)
    order = ["DRAFT", "PLANNED", "ASSIGNED", "DISPATCHED", "IN_PROGRESS", "COMPLETED", "SUPERVISOR_REVIEW", "CLOSED"]
    path = ["plan", "assign", "dispatch", "start", "complete", "start_review", "close"]
    for i, act in enumerate(path, start=1):
        if i > order.index(target):
            break
        if i <= order.index(wo.status):
            continue
        who = {"plan": "planner", "assign": "planner", "dispatch": "planner", "start": tech, "complete": tech,
               "start_review": "sup", "close": "sup"}[act]
        data = {}
        if act == "plan":
            data = {"planned_start": t0, "planned_end": t0 + timedelta(hours=2), **kw}
        elif act == "assign":
            data = {"technician": w[tech]}
        elif act == "complete":
            data = {"resolution_notes": "Replaced the seal and tested for leaks."}
            if wo.work_type in wos.EVIDENCE_REQUIRED_TYPES:
                wos.add_evidence(wo, SimpleUploadedFile("done.txt", b"evidence of the repair work"),
                                 actor=w[tech].user, membership=w[tech])
        if act == "close":
            wos.record_labor(wo, technician=w[tech], work_date=timezone.localdate(), hours="1", actor=w[tech].user,
                             membership=w[tech])
        wo = step(wo, act, who, w, **data)
    return wo


# --- state machines ------------------------------------------------------------------------------------------------


def test_work_order_machine_has_no_shortcuts():
    for state in ("DRAFT", "PLANNED", "ASSIGNED", "DISPATCHED"):
        with pytest.raises(InvalidTransition):
            WORK_ORDER_STATUS.get(state, "close")
    assert [t.action for t in WORK_ORDER_STATUS.available("DRAFT")] == ["plan", "cancel"]
    assert [t.action for t in WORK_ORDER_STATUS.available("ON_HOLD")] == ["resume"]
    assert WORK_ORDER_STATUS.available("CLOSED") == [] and WORK_ORDER_STATUS.available("CANCELLED") == []


def test_request_machine_terminal_and_system_steps():
    assert REQUEST_STATUS.available("REJECTED") == [] and REQUEST_STATUS.available("CLOSED") == []
    with pytest.raises(InvalidTransition):
        REQUEST_STATUS.get("NEW", "approve")  # triage first
    with pytest.raises(InvalidTransition):
        REQUEST_STATUS.get("APPROVED", "resolve")


# --- M05 rules -----------------------------------------------------------------------------------------------------


def test_request_numbers_are_sequential_per_org(w, org_b):
    nums = [new_request(w, title=f"Request {i}").number for i in range(3)]
    assert nums == ["INC-000001", "INC-000002", "INC-000003"]
    assert next_number(org_b, "request.incident", "INC") == "INC-000001"


def test_reject_needs_reason_and_is_terminal(w):
    sr = new_request(w)
    sr = incidents.transition(sr, action="triage", actor=w["ops"].user)
    with pytest.raises(ValidationFailed):
        incidents.transition(sr, action="reject", reason=" ", actor=w["ops"].user)
    sr = incidents.transition(sr, action="reject", reason="Duplicate of INC-1", actor=w["ops"].user)
    assert sr.status == "REJECTED" and sr.decision_reason == "Duplicate of INC-1"
    for act in ("approve", "triage", "close"):
        with pytest.raises(InvalidTransition):
            incidents.transition(sr, action=act, actor=w["ops"].user)


def test_system_actions_are_not_callable_by_hand(w):
    sr = approved_request(w)
    for act in ("link_work_order", "start_service", "resolve", "work_order_cancelled"):
        with pytest.raises(ValidationFailed) as exc:
            incidents.transition(sr, action=act, actor=w["ops"].user)
        assert exc.value.code == "system_action"


def test_request_validation_and_terminal_asset(w, as_user):
    api = as_user(w["tech"].user, w["org"])
    base = {"asset": str(w["asset"].pk), "title": "x" * 3}
    assert api.post("/api/v1/service-requests/", {**base, "title": " "}, format="json").status_code == 400
    assert api.post("/api/v1/service-requests/", {**base, "severity": "NOPE"}, format="json").status_code == 400
    future = (NOW() + timedelta(days=2)).isoformat()
    assert api.post("/api/v1/service-requests/", {**base, "occurred_at": future}, format="json").status_code == 400
    assert api.post("/api/v1/service-requests/", {**base, "downtime_started_at": future}, format="json").status_code == 400
    assert api.post("/api/v1/service-requests/", {}, format="json").status_code == 400
    assert not ServiceRequest.objects.filter(organization=w["org"]).exists()
    # retired asset
    from apps.assets import services as assets
    asset = w["asset"]
    for a in ("start_maintenance", "mark_out_of_service", "retire"):
        assets.change_status(asset, action=a, reason="end of life", actor=None)
    r = api.post("/api/v1/service-requests/", base, format="json")
    assert r.status_code == 409 and r.json()["error"]["code"] == "asset_terminal"


def test_edit_only_before_approval_and_status_not_patchable(w, as_user):
    sr = new_request(w)
    api = as_user(w["ops"].user, w["org"])
    r = api.patch(f"/api/v1/service-requests/{sr.pk}/", {"status": "CLOSED"}, format="json")
    assert r.status_code == 400
    assert api.patch(f"/api/v1/service-requests/{sr.pk}/", {"asset": str(w["asset2"].pk)}, format="json").status_code == 400
    assert api.patch(f"/api/v1/service-requests/{sr.pk}/", {"title": "New title", "severity": "CRITICAL"},
                     format="json").status_code == 200
    sr.refresh_from_db()
    assert sr.title == "New title" and sr.status == "NEW"
    assert AuditLog.objects.filter(action="incident.updated", target_id=str(sr.pk)).count() == 1
    sr = incidents.transition(sr, action="triage", actor=w["ops"].user)
    sr = incidents.transition(sr, action="approve", actor=w["ops"].user)
    assert api.patch(f"/api/v1/service-requests/{sr.pk}/", {"title": "late"}, format="json").status_code == 409


def test_downtime_rules(w, as_user):
    sr = new_request(w)
    ops, tech = as_user(w["ops"].user, w["org"]), as_user(w["tech"].user, w["org"])
    start, end = NOW() - timedelta(hours=3), NOW() - timedelta(hours=1)
    url = f"/api/v1/service-requests/{sr.pk}/downtime/"
    assert tech.put(url, {"started_at": start.isoformat()}, format="json").status_code == 403
    assert ops.put(url, {"started_at": end.isoformat(), "ended_at": start.isoformat()}, format="json").status_code == 400
    assert ops.put(url, {"started_at": (NOW() + timedelta(days=1)).isoformat()}, format="json").status_code == 400
    r = ops.put(url, {"started_at": start.isoformat(), "ended_at": end.isoformat()}, format="json")
    assert r.status_code == 200 and r.json()["duration_seconds"] == 7200
    assert ops.get(url).json()["end_source"] == "manual"
    assert AuditLog.objects.filter(action="incident.downtime_recorded", target_id=str(sr.pk)).count() == 1


def test_evidence_validation_and_download_scope(w, as_user, make_scoped_member, org_b, make_member):
    sr = new_request(w)
    api = as_user(w["tech"].user, w["org"])
    url = f"/api/v1/service-requests/{sr.pk}/evidence/"
    bad = SimpleUploadedFile("run.exe", b"MZ\x90\x00 not allowed")
    assert api.post(url, {"file": bad}, format="multipart").status_code == 400
    ok = SimpleUploadedFile("leak.txt", b"photo of the leak at the pump")
    r = api.post(url, {"file": ok, "description": "leak"}, format="multipart")
    assert r.status_code == 201, r.content
    att_id = r.json()["id"]
    assert api.get(url).json()["count"] == 1

    def download(user):
        c = Client()
        c.force_login(user)
        return c.get(f"/app/files/{att_id}/download/").status_code

    assert download(w["ops"].user) == 200
    scoped_other = make_scoped_member(w["org"], "other@alpha.test", "operations_manager", [w["site2"]])
    assert download(scoped_other.user) == 404  # a different site's user cannot fetch it
    stranger = make_member(org_b, "ops@beta.test", "operations_manager")
    assert download(stranger.user) == 404


# --- M05 / M06 integration ---------------------------------------------------------------------------------------------


def test_create_work_order_requires_approved_request_and_permission(w, as_user):
    sr = new_request(w)
    planner = as_user(w["planner"].user, w["org"])
    r = planner.post(f"/api/v1/service-requests/{sr.pk}/create-work-order/", {}, format="json")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
    assert not WorkOrder.objects.filter(organization=w["org"]).exists()
    sr = incidents.transition(incidents.transition(sr, action="triage", actor=None), action="approve", actor=None)
    # technician lacks work_order.create
    assert as_user(w["tech"].user, w["org"]).post(f"/api/v1/service-requests/{sr.pk}/create-work-order/", {},
                                                  format="json").status_code == 403
    assert planner.post(f"/api/v1/service-requests/{sr.pk}/create-work-order/",
                        {"title": "Custom WO title", "priority": "URGENT"}, format="json").status_code == 201
    wo = WorkOrder.objects.get(source_request=sr)
    assert wo.title == "Custom WO title" and wo.priority == "URGENT"


def test_one_live_work_order_per_request_db_constraint(w):
    sr = approved_request(w)
    incidents.create_work_order_for_request(sr, actor=None, membership=w["planner"])
    with pytest.raises(IntegrityError), transaction.atomic():
        WorkOrder(organization=w["org"], number="WO-X1", title="dup", asset=w["asset"], site=w["site"],
                  source_request=sr).save()


def test_cancel_returns_request_to_approved_and_allows_new_work_order(w):
    sr = approved_request(w)
    wo = incidents.create_work_order_for_request(sr, actor=None, membership=w["planner"])
    with pytest.raises(ValidationFailed):
        step(wo, "cancel", "ops", w)  # reason required
    wo = step(wo, "cancel", "ops", w, reason="Created by mistake")
    assert wo.status == "CANCELLED"
    sr.refresh_from_db()
    assert sr.status == "APPROVED"
    wo2 = incidents.create_work_order_for_request(sr, actor=None, membership=w["planner"])
    assert wo2.pk != wo.pk
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"


def test_cancel_not_allowed_once_started(w):
    wo = to_state(new_wo(w), w, "IN_PROGRESS")
    with pytest.raises(InvalidTransition):
        step(wo, "cancel", "ops", w, reason="too late")


def test_rework_loop_and_reopen(w):
    sr = approved_request(w)
    wo = incidents.create_work_order_for_request(sr, actor=None, membership=w["planner"])
    wo = to_state(wo, w, "SUPERVISOR_REVIEW")
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"
    with pytest.raises(ValidationFailed):
        step(wo, "reject_review", "sup", w)
    wo = step(wo, "reject_review", "sup", w, reason="Leak still visible")
    sr.refresh_from_db()
    assert wo.status == "IN_PROGRESS" and wo.completed_at is None and sr.status == "IN_SERVICE"
    # finish again; requester says not fixed -> request reopened, a NEW work order is possible after this one closes
    wo = step(wo, "complete", "tech", w, resolution_notes="Re-seated the gasket, no leak now.")
    wo = step(wo, "start_review", "sup", w)
    wos.record_labor(wo, technician=w["tech"], work_date=timezone.localdate(), hours="2", actor=None, membership=w["tech"])
    wo = step(wo, "close", "sup", w)
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"
    sr = incidents.transition(sr, action="reopen", reason="Leaks again", actor=w["ops"].user)
    assert sr.status == "APPROVED" and sr.resolved_at is None
    incidents.create_work_order_for_request(sr, actor=None, membership=w["planner"])
    assert WorkOrder.objects.filter(source_request=sr).count() == 2


# --- M06 rules -----------------------------------------------------------------------------------------------------------


def test_plan_requires_window_and_edit_locks_after_assignment(w, as_user):
    wo = new_wo(w)
    with pytest.raises(ValidationFailed) as exc:
        step(wo, "plan", "planner", w)
    assert exc.value.code == "plan_incomplete"
    t0 = NOW() + timedelta(days=1)
    with pytest.raises(ValidationFailed):
        step(wo, "plan", "planner", w, planned_start=t0, planned_end=t0 - timedelta(hours=1))
    wo = step(wo, "plan", "planner", w, planned_start=t0, planned_end=t0 + timedelta(hours=2), priority="HIGH")
    assert wo.priority == "HIGH"
    api = as_user(w["planner"].user, w["org"])
    assert api.patch(f"/api/v1/work-orders/{wo.pk}/", {"status": "CLOSED"}, format="json").status_code == 400
    assert api.patch(f"/api/v1/work-orders/{wo.pk}/", {"title": "Renamed"}, format="json").status_code == 200
    wo = step(wo, "assign", "planner", w, technician=w["tech"])
    assert api.patch(f"/api/v1/work-orders/{wo.pk}/", {"title": "Too late"}, format="json").status_code == 409


def test_assignment_validation(w, org_b, make_member):
    wo = to_state(new_wo(w), w, "PLANNED")
    ben = make_member(org_b, "tech@beta.test", "technician")
    with pytest.raises(ValidationFailed) as exc:
        step(wo, "assign", "planner", w, technician=ben)
    assert exc.value.code == "cross_tenant_technician"
    with pytest.raises(ValidationFailed):
        step(wo, "assign", "planner", w, technician=None)
    with pytest.raises(Conflict) as exc:
        step(wo, "assign", "planner", w, technician=w["reader"])  # cannot execute work orders
    assert exc.value.code == "technician_not_allowed"
    inactive = make_member(w["org"], "gone@alpha.test", "technician", active=False)
    with pytest.raises(Conflict) as exc:
        step(wo, "assign", "planner", w, technician=inactive)
    assert exc.value.code == "technician_inactive"
    wo.refresh_from_db()
    assert wo.status == "PLANNED" and wo.assigned_to_id is None


def test_technician_overlap_is_refused_but_other_windows_and_people_are_fine(w):
    first = to_state(new_wo(w), w, "ASSIGNED")  # tech busy from tomorrow, 2h
    second = new_wo(w)
    # overlapping window with the same technician
    second = step(second, "plan", "planner", w, planned_start=first.planned_start + timedelta(minutes=30),
                  planned_end=first.planned_end + timedelta(hours=1))
    with pytest.raises(Conflict) as exc:
        step(second, "assign", "planner", w, technician=w["tech"])
    assert exc.value.code == "technician_conflict"
    # another technician is fine
    assigned = step(second, "assign", "planner", w, technician=w["tech2"])
    assert assigned.assigned_to_id == w["tech2"].pk
    # same technician, adjacent window, is fine
    third = step(new_wo(w), "plan", "planner", w, planned_start=first.planned_end,
                 planned_end=first.planned_end + timedelta(hours=1))
    assert step(third, "assign", "planner", w, technician=w["tech"]).status == "ASSIGNED"


def test_reassign_rules(w, as_user):
    wo = to_state(new_wo(w), w, "ASSIGNED")
    api = as_user(w["planner"].user, w["org"])
    url = f"/api/v1/work-orders/{wo.pk}/reassign/"
    assert api.post(url, {"technician": str(w["tech2"].pk)}, format="json").status_code == 400  # reason required
    assert api.post(url, {"technician": str(w["tech2"].pk), "reason": "Sick leave"}, format="json").status_code == 200
    wo.refresh_from_db()
    assert wo.assigned_to_id == w["tech2"].pk and wo.status == "ASSIGNED"
    assert as_user(w["tech"].user, w["org"]).post(url, {"technician": str(w["tech"].pk), "reason": "mine"},
                                                  format="json").status_code in (403, 404)
    wo = to_state(wo, w, "IN_PROGRESS", tech="tech2")
    r = api.post(url, {"technician": str(w["tech"].pk), "reason": "late change"}, format="json")
    assert r.status_code == 409
    assert AuditLog.objects.filter(action="work_order.reassigned", target_id=str(wo.pk)).count() == 1


def test_only_assignee_or_dispatcher_executes(w):
    wo = to_state(new_wo(w), w, "DISPATCHED")
    with pytest.raises(PermissionDenied) as exc:
        step(wo, "start", "tech2", w)
    assert exc.value.code == "not_assignee"
    wo = step(wo, "start", "tech", w)
    with pytest.raises(PermissionDenied):
        step(wo, "hold", "tech2", w, reason="not mine")
    # a dispatcher (planner has dispatch) may act for the assignee at the service layer
    assert wos.assert_can_execute(wo, w["planner"]) is None


def test_completion_needs_notes_and_evidence_only_for_corrective(w):
    wo = to_state(new_wo(w), w, "IN_PROGRESS")
    with pytest.raises(ValidationFailed) as exc:
        step(wo, "complete", "tech", w, resolution_notes="short")
    assert exc.value.code == "resolution_notes_required"
    with pytest.raises(ValidationFailed) as exc:
        step(wo, "complete", "tech", w, resolution_notes="Long enough notes here.")
    assert exc.value.code == "evidence_required"
    insp = to_state(new_wo(w, work_type="INSPECTION"), w, "IN_PROGRESS", tech="tech2")
    assert step(insp, "complete", "tech2", w, resolution_notes="Inspected, all within limits.").status == "COMPLETED"


def test_close_blockers_and_labor_rules(w, as_user):
    wo = new_wo(w, work_type="INSPECTION")
    t0 = NOW() + timedelta(days=1)
    wo = step(wo, "plan", "planner", w, planned_start=t0, planned_end=t0 + timedelta(hours=1))
    wo = step(wo, "assign", "planner", w, technician=w["tech"])
    with pytest.raises(Conflict):  # not yet started: nothing to record
        wos.record_labor(wo, technician=w["tech"], work_date=timezone.localdate(), hours="1", actor=None,
                         membership=w["tech"])
    wo = step(wo, "dispatch", "planner", w)
    wo = step(wo, "start", "tech", w)
    tech = as_user(w["tech"].user, w["org"])
    url = f"/api/v1/work-orders/{wo.pk}/labor/"
    today = timezone.localdate().isoformat()
    for hours in ("0", "-1", "25", "abc"):
        assert tech.post(url, {"work_date": today, "hours": hours}, format="json").status_code == 400, hours
    future = (timezone.localdate() + timedelta(days=5)).isoformat()
    assert tech.post(url, {"work_date": future, "hours": "1"}, format="json").status_code == 400
    assert tech.post(url, {"work_date": today, "hours": "1", "technician": str(w["tech2"].pk)},
                     format="json").status_code == 403  # only own time
    wo = step(wo, "complete", "tech", w, resolution_notes="Inspection done, no findings.")
    wo = step(wo, "start_review", "sup", w)
    with pytest.raises(Conflict) as exc:
        step(wo, "close", "sup", w)
    assert exc.value.code == "closure_blocked" and "No labor" in exc.value.details["blockers"][0]
    wos.record_labor(wo, technician=w["tech"], work_date=timezone.localdate(), hours="1.5", actor=w["tech"].user,
                     membership=w["tech"])
    assert step(wo, "close", "sup", w).status == "CLOSED"
    with pytest.raises(Conflict):  # closed: nothing more can be recorded
        wos.record_material(wo, description="x", quantity=1, actor=None, membership=w["tech"])
    assert tech.post(f"/api/v1/work-orders/{wo.pk}/materials/", {"description": "x", "quantity": "1"},
                     format="json").status_code == 409


def test_material_validation(w, as_user):
    wo = to_state(new_wo(w), w, "IN_PROGRESS")
    tech = as_user(w["tech"].user, w["org"])
    url = f"/api/v1/work-orders/{wo.pk}/materials/"
    assert tech.post(url, {"description": "", "quantity": "1"}, format="json").status_code == 400
    assert tech.post(url, {"description": "Seal", "quantity": "0"}, format="json").status_code == 400
    assert tech.post(url, {"description": "Seal", "quantity": "-2"}, format="json").status_code == 400
    assert tech.post(url, {"description": "Seal", "quantity": "2.5", "unit": "m"}, format="json").status_code == 201
    other = as_user(w["tech2"].user, w["org"])
    assert other.post(url, {"description": "Seal", "quantity": "1"}, format="json").status_code == 404  # not visible


# --- RBAC ---------------------------------------------------------------------------------------------------------------------------


def test_unauthenticated_and_reader(w, api, as_user):
    sr = new_request(w)
    wo = new_wo(w)
    for url in ("/api/v1/service-requests/", "/api/v1/work-orders/", f"/api/v1/work-orders/{wo.pk}/"):
        assert api.get(url).status_code == 401
    assert api.post("/api/v1/work-orders/", {}, format="json").status_code == 401
    reader = as_user(w["reader"].user, w["org"])
    assert reader.get("/api/v1/service-requests/").status_code == 200
    assert reader.get(f"/api/v1/service-requests/{sr.pk}/").status_code == 200
    assert reader.get(f"/api/v1/work-orders/{wo.pk}/").status_code == 200
    body = {"asset": str(w["asset"].pk), "title": "nope"}
    assert reader.post("/api/v1/service-requests/", body, format="json").status_code == 403
    assert reader.post("/api/v1/work-orders/", body, format="json").status_code == 403
    assert reader.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "triage"}, format="json").status_code == 403
    assert reader.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "cancel", "reason": "x"},
                       format="json").status_code == 403
    assert reader.patch(f"/api/v1/work-orders/{wo.pk}/", {"title": "zzz"}, format="json").status_code == 403
    assert reader.post(f"/api/v1/work-orders/{wo.pk}/labor/", {"work_date": "2026-01-01", "hours": "1"},
                       format="json").status_code == 403


def test_role_boundaries(w, as_user):
    sr = new_request(w, who="tech")
    wo = to_state(new_wo(w), w, "PLANNED")
    tech, planner, sup = (as_user(w[k].user, w["org"]) for k in ("tech", "planner", "sup"))
    # planner may not approve; supervisor may not plan/assign; technician may not assign or close
    assert planner.post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "triage"}, format="json").status_code == 403
    assert sup.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "assign", "technician": str(w["tech"].pk)},
                    format="json").status_code == 403
    assert tech.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "assign", "technician": str(w["tech"].pk)},
                     format="json").status_code in (403, 404)
    assert tech.post("/api/v1/work-orders/", {"asset": str(w["asset"].pk), "title": "mine"}, format="json").status_code == 403


def test_view_implies_view_assigned_but_not_vice_versa(w):
    from apps.rbac import services as rbac
    assert rbac.has_permission(w["planner"], "work_order.view_assigned")  # implied by work_order.view
    assert not rbac.has_permission(w["tech"], "work_order.view")
    assert rbac.has_permission(w["tech"], "work_order.view_assigned")


# --- tenant isolation and site scope ----------------------------------------------------------------------------------------


def test_cross_tenant_isolation_both_directions(w, org_b, site_b1, make_asset, make_member, as_user):
    sr = new_request(w)
    wo = to_state(new_wo(w), w, "ASSIGNED")
    bob = make_member(org_b, "ops@beta.test", "operations_manager")
    b_asset = make_asset(org_b, site_b1, "B-1")
    b_sr = incidents.create_request(org_b, asset=b_asset, reporter=bob, actor=bob.user, title="Beta problem")
    b_wo = wos.create_work_order(org_b, asset=b_asset, actor=bob.user, title="Beta work")
    bapi, aapi = as_user(bob.user, org_b), as_user(w["ops"].user, w["org"])
    # Beta sees none of Alpha's records
    assert bapi.get("/api/v1/service-requests/").json()["count"] == 1
    assert bapi.get("/api/v1/work-orders/").json()["count"] == 1
    for url in (f"/api/v1/service-requests/{sr.pk}/", f"/api/v1/service-requests/{sr.pk}/history/",
                f"/api/v1/work-orders/{wo.pk}/", f"/api/v1/work-orders/{wo.pk}/events/",
                f"/api/v1/work-orders/{wo.pk}/labor/", f"/api/v1/work-orders/{wo.pk}/closure/"):
        assert bapi.get(url).status_code == 404, url
    for url, body in ((f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "triage"}),
                      (f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "dispatch"}),
                      (f"/api/v1/work-orders/{wo.pk}/reassign/", {"technician": str(w["tech2"].pk), "reason": "xx"}),
                      (f"/api/v1/service-requests/{sr.pk}/create-work-order/", {})):
        assert bapi.post(url, body, format="json").status_code == 404, url
    # ... and cannot reference Alpha's asset or technician
    assert bapi.post("/api/v1/service-requests/", {"asset": str(w["asset"].pk), "title": "sneaky"}, format="json").status_code == 404
    assert bapi.post("/api/v1/work-orders/", {"asset": str(w["asset"].pk), "title": "sneaky"}, format="json").status_code == 404
    b_plan = wos.transition(b_wo, action="plan", actor=bob.user, membership=bob, planned_start=NOW(),
                            planned_end=NOW() + timedelta(hours=1))
    r = bapi.post(f"/api/v1/work-orders/{b_plan.pk}/transition/", {"action": "assign", "technician": str(w["tech"].pk)},
                  format="json")
    assert r.status_code == 404
    # Alpha cannot touch Beta's either, and cannot borrow Beta's org via the header
    assert aapi.get(f"/api/v1/service-requests/{b_sr.pk}/").status_code == 404
    assert aapi.get(f"/api/v1/work-orders/{b_wo.pk}/").status_code == 404
    forged = as_user(w["ops"].user)
    forged.credentials(HTTP_X_ORGANIZATION=org_b.slug)
    assert forged.get("/api/v1/work-orders/").status_code == 403
    assert not WorkOrder.objects.filter(organization=org_b, title="sneaky").exists()
    assert not ServiceRequest.objects.filter(organization=org_b, title="sneaky").exists()


def test_site_scoped_user_sees_only_their_site(w, make_scoped_member, as_user):
    a1_req, a2_req = new_request(w), new_request(w, asset=w["asset2"], title="other site")
    a1_wo, a2_wo = new_wo(w), new_wo(w, asset=w["asset2"])
    sam = make_scoped_member(w["org"], "sam@alpha.test", "operations_manager", [w["site"]])
    api = as_user(sam.user, w["org"])
    assert {x["id"] for x in api.get("/api/v1/service-requests/").json()["results"]} == {str(a1_req.pk)}
    assert {x["id"] for x in api.get("/api/v1/work-orders/").json()["results"]} == {str(a1_wo.pk)}
    assert api.get(f"/api/v1/service-requests/{a2_req.pk}/").status_code == 404
    assert api.get(f"/api/v1/work-orders/{a2_wo.pk}/").status_code == 404
    assert api.get(f"/api/v1/service-requests/{a2_req.pk}/history/").status_code == 404
    assert api.post(f"/api/v1/work-orders/{a2_wo.pk}/transition/", {"action": "cancel", "reason": "no"},
                    format="json").status_code == 404
    assert api.post("/api/v1/service-requests/", {"asset": str(w["asset2"].pk), "title": "x1x"}, format="json").status_code == 404
    assert api.get(f"/api/v1/service-requests/?site={w['site2'].pk}").json()["count"] == 0
    assert api.get("/api/v1/work-orders/?q=P-2").json()["count"] == 0
    a2_wo.refresh_from_db()
    assert a2_wo.status == "DRAFT"


def test_technician_sees_only_assigned_work(w, as_user):
    mine = to_state(new_wo(w), w, "ASSIGNED")
    other = new_wo(w)
    tech = as_user(w["tech"].user, w["org"])
    assert {x["id"] for x in tech.get("/api/v1/work-orders/").json()["results"]} == {str(mine.pk)}
    assert tech.get(f"/api/v1/work-orders/{other.pk}/").status_code == 404
    assert tech.get(f"/api/v1/work-orders/{mine.pk}/").status_code == 200
    assert as_user(w["tech2"].user, w["org"]).get(f"/api/v1/work-orders/{mine.pk}/").status_code == 404
    assert as_user(w["tech2"].user, w["org"]).post(f"/api/v1/work-orders/{mine.pk}/transition/", {"action": "start"},
                                                   format="json").status_code == 404


def test_work_order_file_download_scope(w, as_user):
    wo = to_state(new_wo(w), w, "IN_PROGRESS")
    api = as_user(w["tech"].user, w["org"])
    r = api.post(f"/api/v1/work-orders/{wo.pk}/evidence/", {"file": SimpleUploadedFile("e.txt", b"evidence content")},
                 format="multipart")
    assert r.status_code == 201
    bad = api.post(f"/api/v1/work-orders/{wo.pk}/evidence/", {"file": SimpleUploadedFile("e.exe", b"MZ....")},
                   format="multipart")
    assert bad.status_code == 400
    att = r.json()["id"]
    for user, expected in ((w["tech"].user, 200), (w["tech2"].user, 404), (w["ops"].user, 200),
                           (w["reader"].user, 200)):
        c = Client()
        c.force_login(user)
        assert c.get(f"/app/files/{att}/download/").status_code == expected, user.email
    assert api.get(f"/api/v1/work-orders/{wo.pk}/evidence/").json()["count"] == 1


def test_unknown_ids_and_bad_input_are_clean_errors(w, as_user):
    api = as_user(w["ops"].user, w["org"])
    for url in (f"/api/v1/work-orders/{uuid.uuid4()}/", "/api/v1/work-orders/not-a-uuid/",
                f"/api/v1/service-requests/{uuid.uuid4()}/"):
        assert api.get(url).status_code == 404
    wo = new_wo(w)
    assert api.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "explode"}, format="json").status_code == 400
    assert api.post(f"/api/v1/work-orders/{wo.pk}/transition/", {}, format="json").status_code == 400
    assert api.get("/api/v1/work-orders/?status=BOGUS").json()["count"] == 0
    assert api.get("/api/v1/work-orders/?site=not-a-uuid").json()["count"] == 0


def test_work_order_from_a_request_records_its_source_and_the_backfill_migration_is_idempotent(w):
    import importlib

    from django.apps import apps

    from apps.workorders.models import WorkOrder as WO

    sr = approved_request(w)
    wo = incidents.create_work_order_for_request(sr, actor=None, membership=w["planner"])
    assert (wo.source_type, wo.source_id) == ("SERVICE_REQUEST", sr.pk)
    WO.objects.filter(pk=wo.pk).update(source_type="", source_id=None)  # the state before migration 0003
    migration = importlib.import_module("apps.workorders.migrations.0003_workorder_source")
    migration.backfill_request_source(apps, None)
    migration.backfill_request_source(apps, None)
    wo.refresh_from_db()
    assert (wo.source_type, wo.source_id) == ("SERVICE_REQUEST", sr.pk)
