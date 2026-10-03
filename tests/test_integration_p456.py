"""Phase 4+5+6 integration: one preventive-maintenance order runs through M04 -> M06 -> M08 -> M09 -> M11 using only
the real services and hooks (no direct row edits), with the audit trail and the stock ledger checked at the end."""
from datetime import timedelta

import pytest

from apps.audit.models import AuditLog
from apps.checklists import services as cl
from apps.inventory import services as inv
from apps.inventory.models import StockMovement
from apps.maintenance import services as pm
from apps.sla import services as sla
from apps.sla.models import SLABreach, SLATracking
from apps.workorders import services as wos
from apps.workorders.models import WorkOrderMaterial
from tests.phase3_support import finish_work, good_answers, make_template, step
from tests.pm_support import T0, freeze, make_plan, time_schedule
from tests.test_m09_inventory import assert_ledger_consistent

pytestmark = pytest.mark.django_db


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def test_pm_order_flows_through_checklist_inventory_and_sla(inv_, monkeypatch):
    p = inv_
    freeze(monkeypatch, T0)
    svc = p["ops"]
    prof = sla.create_profile(p["org"], name="PM work orders", applies_to="WORK_ORDER", work_type="PREVENTIVE",
                              pause_states=["WORK_ORDER:ON_HOLD"], actor=svc.user)
    sla.set_target(prof, priority="MEDIUM", response_minutes=60, resolution_minutes=480, actor=svc.user)
    template = make_template(p, required=False, name="PM pump inspection")
    inv.receive(p["wh"], p["part"], 10, actor=p["stores"].user)

    # M04 generates the order through the M06 service; M11 starts its clock from the persisted created_at
    cycle = pm.generate_cycle(time_schedule(make_plan(p, checklist_key=str(template.key), priority="MEDIUM")))
    wo = cycle.work_order
    assert wo.source_type == "PREVENTIVE_MAINTENANCE" and wo.status == "PLANNED"
    t = SLATracking.objects.get(work_order=wo)
    assert t.started_at == wo.created_at and t.resolution_due_at == at(480)

    # M06 assignment is the SLA response; M07 / M09: the technician requests a part, stores reserves and issues it
    freeze(monkeypatch, at(20))
    wo = step(wo, "assign", p, "planner", technician=p["tech"])
    t.refresh_from_db()
    assert t.response_state == "MET" and t.response_met_at == at(20)
    wo = step(wo, "dispatch", p, "planner")
    wo = step(wo, "start", p, "tech")
    line = inv.request_part(wo, p["part"], 3, actor=p["tech"].user, membership=p["tech"])
    line = inv.reserve(line, p["wh"], actor=p["stores"].user)
    line = inv.issue(line, p["wh"], 3, actor=p["stores"].user)
    line = inv.consume(line, 3, actor=p["tech"].user, membership=p["tech"])
    assert WorkOrderMaterial.objects.get(part_line=line).quantity == 3  # M09 wrote the M06 material row

    # on hold pauses the SLA only because the profile says so; resuming shifts the due time
    freeze(monkeypatch, at(60))
    wo = step(wo, "hold", p, "tech", reason="Waiting for a lock-out permit")
    t.refresh_from_db()
    assert t.status == "PAUSED"
    freeze(monkeypatch, at(90))
    wo = step(wo, "resume", p, "tech")
    t.refresh_from_db()
    assert t.status == "ACTIVE" and t.resolution_due_at == at(510)

    # M08: the plan's checklist blocks completion until it is done
    with pytest.raises(Exception) as exc:
        step(wo, "complete", p, "tech", resolution_notes="Finished without the checklist.")
    assert getattr(exc.value, "code", "") == "checklist_incomplete"
    insp = cl.start_inspection(p["org"], template=template, membership=p["tech"], actor=p["tech"].user, work_order=wo)
    cl.save_responses(insp, good_answers(template), membership=p["tech"], actor=p["tech"].user)
    cl.complete_inspection(insp, membership=p["tech"], actor=p["tech"].user)
    freeze(monkeypatch, at(200))
    wo = finish_work(wo, p)
    wo = step(wo, "start_review", p, "sup")
    wo = step(wo, "close", p, "sup")
    assert wo.status == "CLOSED"

    # SLA resolved on time, nothing breached, audit and ledger evidence exists
    t.refresh_from_db()
    assert t.status == "COMPLETED" and t.resolution_state == "MET" and not SLABreach.objects.exists()
    assert sla.process_organization(p["org"], at(2000))["checked"] == 0
    for action in ("sla.tracking_started", "sla.response_met", "sla.resolution_met"):
        assert AuditLog.objects.filter(action=action).count() == 1, action
    assert StockMovement.objects.filter(movement_type="ISSUE").count() == 1
    assert_ledger_consistent(p["org"])
    assert wos.closure_blockers(wo) == []


def test_incident_to_work_order_runs_on_the_requests_clock(inv_, monkeypatch):
    from apps.incidents import services as incidents
    from apps.incidents.models import ServiceRequest

    p = inv_
    freeze(monkeypatch, T0)
    svc = p["ops"]
    prof = sla.create_profile(p["org"], name="Incidents", applies_to="REQUEST", actor=svc.user)
    sla.set_target(prof, priority="HIGH", response_minutes=30, resolution_minutes=240, actor=svc.user)
    wo_prof = sla.create_profile(p["org"], name="Work orders", applies_to="WORK_ORDER", actor=svc.user)
    sla.set_target(wo_prof, priority="HIGH", response_minutes=30, resolution_minutes=240, actor=svc.user)
    sr = incidents.create_request(p["org"], asset=p["asset"], reporter=p["tech"], title="Seal failure",
                                  severity="HIGH", actor=p["tech"].user)
    freeze(monkeypatch, at(10))
    incidents.transition(sr, action="triage", actor=p["ops"].user)
    incidents.transition(sr, action="approve", actor=p["ops"].user)
    wo = wos.create_work_order(p["org"], asset=p["asset"], actor=p["planner"].user, title="Fix seal", priority="HIGH",
                               source_request=ServiceRequest.objects.get(pk=sr.pk))
    assert SLATracking.objects.count() == 1  # one clock, owned by the request
    t = SLATracking.objects.get(request=sr)
    assert t.response_state == "MET" and t.response_met_at == at(10)
    freeze(monkeypatch, at(300))
    assert sla.process_organization(p["org"])["breaches"] == 1  # resolution (240 min) is overdue
    assert SLABreach.objects.get().target_kind == "RESOLUTION" and wo.source_request_id == sr.pk
