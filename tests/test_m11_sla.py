"""M11 service tests with a controllable clock: tracking start, warning / breach / escalation, notifications,
pause / resume, idempotency, Celery task, hooks into M05 / M06, configuration rules and audit evidence."""
from datetime import timedelta

import pytest

from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, ValidationFailed
from apps.incidents import services as incidents
from apps.incidents.models import ServiceRequest
from apps.notifications.models import Notification
from apps.sla import services as sla
from apps.sla import tasks
from apps.sla.models import EscalationRule, SLABreach, SLAEvent, SLATracking
from apps.tenancy.models import Membership
from apps.workorders import services as wos
from apps.workorders.models import WorkOrder
from tests.pm_support import T0, freeze

pytestmark = pytest.mark.django_db


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def report(s, monkeypatch, *, severity="HIGH", asset=None):
    freeze(monkeypatch, T0)
    return incidents.create_request(s["org"], asset=asset or s["asset"], reporter=s["tech"], title="Pump is leaking",
                                    severity=severity, actor=s["tech"].user)


def tracking(sr):
    return SLATracking.objects.get(request=sr)


def monitor(s, monkeypatch, minutes):
    freeze(monkeypatch, at(minutes))
    return sla.process_organization(s["org"])


def events(t):
    return list(SLAEvent.objects.filter(tracking=t).values_list("event_type", flat=True))


def notes():
    return Notification.objects.filter(source="sla")


# --- start ------------------------------------------------------------------------------------------------------------


def test_tracking_starts_from_persisted_created_at_with_absolute_due_times(sla_, monkeypatch):
    sr = report(sla_, monkeypatch)
    t = tracking(sr)
    assert t.started_at == sr.created_at == T0
    assert t.response_due_at == at(30) and t.resolution_due_at == at(120)
    assert (t.status, t.response_state, t.resolution_state) == ("ACTIVE", "PENDING", "PENDING")
    assert events(t) == ["STARTED"]
    assert AuditLog.objects.filter(action="sla.tracking_started").count() == 1


def test_no_profile_or_no_target_for_the_priority_means_no_tracking(sla_, monkeypatch):
    sr = report(sla_, monkeypatch, severity="LOW")  # the profile has no LOW target
    assert not SLATracking.objects.filter(request=sr).exists()


def test_due_times_survive_a_profile_edit(sla_, monkeypatch):
    sr = report(sla_, monkeypatch)
    sla.set_target(sla_["profile"], priority="HIGH", response_minutes=5, resolution_minutes=10, actor=sla_["svc"].user)
    t = tracking(sr)
    assert t.response_due_at == at(30) and t.resolution_due_at == at(120)


def test_site_profile_wins_over_the_organization_profile(sla_, monkeypatch):
    site_profile = sla.create_profile(sla_["org"], name="Site A1 incidents", applies_to="REQUEST", site=sla_["site"],
                                      actor=sla_["svc"].user)
    sla.set_target(site_profile, priority="HIGH", response_minutes=10, resolution_minutes=20, actor=sla_["svc"].user)
    sr = report(sla_, monkeypatch)
    assert tracking(sr).profile_id == site_profile.pk and tracking(sr).response_due_at == at(10)


# --- the T0..T4 journey --------------------------------------------------------------------------------------------------


def test_high_priority_request_journey_warning_breach_escalation_resolution(sla_, monkeypatch):
    s = sla_
    sr = report(s, monkeypatch)
    t = tracking(sr)

    assert monitor(s, monkeypatch, 10) == {"checked": 1, "warnings": 0, "breaches": 0, "escalations": 0, "errors": 0}

    r = monitor(s, monkeypatch, 25)  # T1: 83 % of the response target elapsed -> warning
    assert r["warnings"] == 1 and r["breaches"] == 0
    assert notes().filter(level="WARNING", recipient=s["ops"].user).count() == 1

    r = monitor(s, monkeypatch, 31)  # T2: response breached, operations manager notified
    assert r["breaches"] == 1
    b = SLABreach.objects.get(tracking=t, target_kind="RESPONSE")
    assert b.status == "OPEN" and b.breached_at == at(30) and b.detected_at == at(31) and b.priority == "HIGH"
    assert notes().filter(level="CRITICAL", recipient=s["ops"].user).count() == 1
    assert SLATracking.objects.get(pk=t.pk).response_state == "BREACHED"

    incidents.transition(sr, action="triage", actor=s["ops"].user)  # the (late) response
    t.refresh_from_db()
    assert t.response_state == "MET_LATE" and t.response_met_at == at(31)
    b.refresh_from_db()
    assert b.status == "CLOSED" and b.closed_reason == "target met late"

    r = monitor(s, monkeypatch, 121)  # T3: resolution breached
    assert r["breaches"] == 1
    assert SLABreach.objects.filter(tracking=t, target_kind="RESOLUTION", status="OPEN").count() == 1

    r = monitor(s, monkeypatch, 182)  # T4: 61 minutes after the breach -> service manager escalation
    assert r["escalations"] == 1
    rb = SLABreach.objects.get(tracking=t, target_kind="RESOLUTION")
    assert rb.escalation_level == 2 and rb.escalated_at == at(182)
    assert notes().filter(recipient=s["svc"].user, title__contains="escalation").count() == 1
    assert events(t).count("ESCALATED") == 1 and events(t).count("BREACHED") == 2

    # database evidence: breach rows, events and audit entries all exist exactly once
    assert SLABreach.objects.filter(tracking=t).count() == 2
    assert AuditLog.objects.filter(action="sla.breach_detected").count() == 2
    assert AuditLog.objects.filter(action="sla.escalated").count() == 1


def test_breach_and_escalation_are_emailed_but_warning_is_in_app_only(sla_, monkeypatch,
                                                                       django_capture_on_commit_callbacks):
    from django.core import mail

    s = sla_
    report(s, monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        monitor(s, monkeypatch, 25)  # warning
    assert len(mail.outbox) == 0 and notes().filter(level="WARNING").exists()

    with django_capture_on_commit_callbacks(execute=True):
        monitor(s, monkeypatch, 31)  # response breach
    assert [m.to for m in mail.outbox] == [[s["ops"].user.email]]
    assert "SLA breached" in mail.outbox[0].subject

    with django_capture_on_commit_callbacks(execute=True):
        monitor(s, monkeypatch, 31)  # idempotent re-run: no second email
    assert len(mail.outbox) == 1


def test_met_on_time_never_breaches(sla_, monkeypatch):
    s = sla_
    sr = report(s, monkeypatch)
    freeze(monkeypatch, at(10))
    incidents.transition(sr, action="triage", actor=s["ops"].user)
    t = tracking(sr)
    assert t.response_state == "MET" and t.response_met_at == at(10)
    monitor(s, monkeypatch, 60)
    assert not SLABreach.objects.filter(tracking=t, target_kind="RESPONSE").exists()
    assert tracking(sr).status == "ACTIVE" and tracking(sr).resolution_state == "PENDING"


def test_request_work_order_has_no_second_clock_and_resolution_completes_tracking(sla_, monkeypatch):
    s = sla_
    sr = report(s, monkeypatch)
    freeze(monkeypatch, at(5))
    incidents.transition(sr, action="triage", actor=s["ops"].user)
    incidents.transition(sr, action="approve", actor=s["ops"].user)
    wo = wos.create_work_order(s["org"], asset=s["asset"], actor=s["planner"].user, title="Fix leak",
                               priority="HIGH", source_request=sr)
    assert not SLATracking.objects.filter(work_order=wo).exists()
    ServiceRequest.objects.filter(pk=sr.pk).update(status="RESOLVED")
    sla.on_request_status_changed(ServiceRequest.objects.get(pk=sr.pk), "IN_SERVICE", "RESOLVED")
    t = tracking(sr)
    assert t.status == "COMPLETED" and t.resolution_state == "MET"
    assert monitor(s, monkeypatch, 300)["checked"] == 0  # completed trackings are not evaluated


def test_rejected_request_cancels_the_tracking(sla_, monkeypatch):
    s = sla_
    sr = report(s, monkeypatch)
    monitor(s, monkeypatch, 31)
    incidents.transition(sr, action="triage", actor=s["ops"].user)
    incidents.transition(sr, action="reject", reason="duplicate report", actor=s["ops"].user)
    t = tracking(sr)
    assert t.status == "CANCELLED" and "CANCELLED" in events(t)


# --- idempotency / retry ---------------------------------------------------------------------------------------------------


def test_duplicate_processing_creates_no_duplicates(sla_, monkeypatch):
    s = sla_
    sr = report(s, monkeypatch)
    t = tracking(sr)
    monitor(s, monkeypatch, 25)
    first = (SLAEvent.objects.count(), SLABreach.objects.count(), notes().count())
    for _ in range(3):
        monitor(s, monkeypatch, 25)
    assert (SLAEvent.objects.count(), SLABreach.objects.count(), notes().count()) == first
    monitor(s, monkeypatch, 200)
    after = (SLAEvent.objects.count(), SLABreach.objects.count(), notes().count())
    for _ in range(3):
        monitor(s, monkeypatch, 200)
    assert (SLAEvent.objects.count(), SLABreach.objects.count(), notes().count()) == after
    assert SLABreach.objects.filter(tracking=t).count() == 2
    assert events(t).count("WARNING") == 1


def test_celery_task_is_idempotent(sla_, org_b, monkeypatch):
    report(sla_, monkeypatch)
    freeze(monkeypatch, at(40))
    r1 = tasks.monitor_sla.apply().get()
    r2 = tasks.monitor_sla.apply().get()
    assert r1["breaches"] == 1 and r1["errors"] == 0
    assert r2["breaches"] == 0 and r2["warnings"] == 0
    assert SLABreach.objects.count() == 1


def test_failing_tracking_does_not_stop_the_others(sla_, monkeypatch):
    s = sla_
    report(s, monkeypatch)
    report(s, monkeypatch)
    freeze(monkeypatch, at(40))
    real, calls = sla.process_tracking, []

    def flaky(tracking_, now=None):
        calls.append(tracking_.pk)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return real(tracking_, now)

    monkeypatch.setattr(sla, "process_tracking", flaky)
    res = sla.process_organization(s["org"])
    assert res["errors"] == 1 and res["checked"] == 1
    monkeypatch.setattr(sla, "process_tracking", real)  # the retry picks the failed one up
    assert sla.process_organization(s["org"])["checked"] == 2
    assert SLABreach.objects.count() == 2


# --- pause / resume -----------------------------------------------------------------------------------------------------


def test_pause_only_for_configured_states_and_due_times_shift(sla_, monkeypatch):
    s = sla_
    freeze(monkeypatch, T0)
    wo_profile = sla.create_profile(s["org"], name="WO SLA", applies_to="WORK_ORDER", actor=s["svc"].user,
                                    pause_states=["WORK_ORDER:ON_HOLD"])
    sla.set_target(wo_profile, priority="HIGH", response_minutes=30, resolution_minutes=240, actor=s["svc"].user)
    wo = wos.create_work_order(s["org"], asset=s["asset"], actor=s["planner"].user, title="Fan", priority="HIGH")
    t = SLATracking.objects.get(work_order=wo)
    assert t.resolution_due_at == at(240)
    WorkOrder.objects.filter(pk=wo.pk).update(status="ON_HOLD")
    freeze(monkeypatch, at(20))
    sla.on_work_order_changed(WorkOrder.objects.get(pk=wo.pk), "IN_PROGRESS", "ON_HOLD")
    t.refresh_from_db()
    assert t.status == "PAUSED" and t.paused_at == at(20)
    assert sla.process_organization(s["org"], at(500))["checked"] == 0  # paused trackings are not evaluated
    WorkOrder.objects.filter(pk=wo.pk).update(status="IN_PROGRESS")
    freeze(monkeypatch, at(50))
    sla.on_work_order_changed(WorkOrder.objects.get(pk=wo.pk), "ON_HOLD", "IN_PROGRESS")
    t.refresh_from_db()
    assert t.status == "ACTIVE" and t.paused_seconds == 30 * 60
    assert t.resolution_due_at == at(270) and t.response_due_at == at(60)
    assert t.response_state == "MET"  # restarting work at +50 min beats the shifted +60 due time (30 min paused)
    assert {"PAUSED", "RESUMED"} <= set(events(t))


def test_unconfigured_profile_never_pauses(sla_, monkeypatch):
    s = sla_
    sla.update_profile(s["profile"], actor=s["svc"].user, pause_states=[])
    sr = report(s, monkeypatch)
    ServiceRequest.objects.filter(pk=sr.pk).update(status="IN_SERVICE")
    sla.on_request_status_changed(ServiceRequest.objects.get(pk=sr.pk), "APPROVED", "IN_SERVICE")
    assert tracking(sr).status == "ACTIVE"


# --- work-order SLA ---------------------------------------------------------------------------------------------------------


def test_work_order_response_is_first_assignment_and_resolution_is_completion(sla_, monkeypatch):
    s = sla_
    freeze(monkeypatch, T0)
    prof = sla.create_profile(s["org"], name="WO SLA", applies_to="WORK_ORDER", actor=s["svc"].user)
    sla.set_target(prof, priority="URGENT", response_minutes=15, resolution_minutes=60, actor=s["svc"].user)
    wo = wos.create_work_order(s["org"], asset=s["asset"], actor=s["planner"].user, title="Urgent fix",
                               priority="URGENT")
    t = SLATracking.objects.get(work_order=wo)
    assert t.response_due_at == at(15)
    sla.on_work_order_changed(wo, "PLANNED", "ASSIGNED")
    t.refresh_from_db()
    assert t.response_state == "MET" and t.response_met_at == T0
    freeze(monkeypatch, at(90))
    sla.on_work_order_changed(wo, "IN_PROGRESS", "COMPLETED")
    t.refresh_from_db()
    assert t.resolution_state == "MET_LATE" and t.status == "COMPLETED"
    assert SLABreach.objects.get(tracking=t, target_kind="RESOLUTION").status == "CLOSED"


# --- configuration rules -----------------------------------------------------------------------------------------------------


def test_profile_configuration_validation(sla_):
    s, svc = sla_, sla_["svc"].user
    with pytest.raises(ValidationFailed):
        sla.set_target(s["profile"], priority="HIGH", response_minutes=60, resolution_minutes=30, actor=svc)
    with pytest.raises(ValidationFailed):
        sla.set_target(s["profile"], priority="URGENT", response_minutes=1, resolution_minutes=2, actor=svc)
    with pytest.raises(ValidationFailed):
        sla.set_target(s["profile"], priority="HIGH", response_minutes=0, resolution_minutes=2, actor=svc)
    with pytest.raises(ValidationFailed):
        sla.set_target(s["profile"], priority="HIGH", response_minutes=1, resolution_minutes=2, warning_percent=100,
                       actor=svc)
    with pytest.raises(Conflict):
        sla.create_profile(s["org"], name="incident sla", applies_to="REQUEST", actor=svc)
    with pytest.raises(Conflict):  # a second active profile for the same scope
        sla.create_profile(s["org"], name="Another", applies_to="REQUEST", actor=svc)
    with pytest.raises(ValidationFailed):
        sla.create_rule(s["profile"], target_kind="RESPONSE", trigger="WARNING", actor=svc)  # no recipient
    with pytest.raises(ValidationFailed):
        sla.update_profile(s["profile"], actor=svc, pause_states=["WORK_ORDER:NOPE"])


def test_rule_limits_and_duplicates(sla_):
    s, svc = sla_, sla_["svc"].user
    with pytest.raises(Conflict):
        sla.create_rule(s["profile"], target_kind="RESPONSE", trigger="WARNING", notify_role=s["ops_role"], actor=svc)
    sla.create_rule(s["profile"], target_kind="RESOLUTION", trigger="WARNING", notify_assignee=True, actor=svc)
    sla.create_rule(s["profile"], target_kind="RESOLUTION", trigger="ESCALATION", after_minutes=30,
                    notify_assignee=True, actor=svc)
    with pytest.raises(Conflict):  # 6 is the maximum
        sla.create_rule(s["profile"], target_kind="RESOLUTION", trigger="ESCALATION", after_minutes=45,
                        notify_assignee=True, actor=svc)


def test_no_rule_means_breach_recorded_but_nobody_notified(sla_, monkeypatch):
    s = sla_
    EscalationRule.objects.filter(profile=s["profile"]).delete()
    report(s, monkeypatch)
    assert monitor(s, monkeypatch, 40)["breaches"] == 1
    assert notes().count() == 0 and SLABreach.objects.count() == 1


def test_inactive_recipient_is_not_notified(sla_, monkeypatch):
    s = sla_
    Membership.objects.filter(pk=s["ops"].pk).update(status=Membership.Status.SUSPENDED)
    report(s, monkeypatch)
    monitor(s, monkeypatch, 40)
    assert not notes().filter(recipient=s["ops"].user).exists()


def test_acknowledge_breach(sla_, monkeypatch):
    s = sla_
    report(s, monkeypatch)
    monitor(s, monkeypatch, 40)
    b = SLABreach.objects.get()
    sla.acknowledge_breach(b, actor=s["ops"].user)
    b.refresh_from_db()
    assert b.status == "ACKNOWLEDGED" and b.acknowledged_by_id == s["ops"].user.pk
    with pytest.raises(Conflict):
        sla.acknowledge_breach(b, actor=s["ops"].user)
    assert AuditLog.objects.filter(action="sla.breach_acknowledged").count() == 1


def test_events_are_append_only(sla_, monkeypatch):
    report(sla_, monkeypatch)
    ev = SLAEvent.objects.first()
    ev.detail = "x"
    with pytest.raises(ValueError):
        ev.save()
    with pytest.raises(ValueError):
        ev.delete()
