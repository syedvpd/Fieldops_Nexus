"""M11 concurrency: several real workers (threads, own PostgreSQL connections) running the monitor on the same
overdue tracking must record exactly one breach, one event per kind and one notification per recipient."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection

from apps.incidents import services as incidents
from apps.notifications.models import Notification
from apps.sla import services as sla
from apps.sla.models import SLABreach, SLAEvent, SLATracking
from tests.pm_support import T0, freeze
from tests.test_m11_sla import at

pytestmark = pytest.mark.django_db(transaction=True)


def race(calls):
    barrier = Barrier(len(calls))

    def worker(fn):
        try:
            barrier.wait(timeout=30)
            return fn()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(worker, calls))


def test_concurrent_monitors_record_one_breach_and_one_notification(sla_, monkeypatch):
    s = sla_
    freeze(monkeypatch, T0)
    incidents.create_request(s["org"], asset=s["asset"], reporter=s["tech"], title="Leak", severity="HIGH",
                             actor=s["tech"].user)
    freeze(monkeypatch, at(200))
    tracking = SLATracking.objects.get()
    race([lambda: sla.process_tracking(SLATracking.objects.get(pk=tracking.pk), at(200)) for _ in range(6)])
    assert SLABreach.objects.filter(tracking=tracking).count() == 2  # response + resolution, once each
    kinds = list(SLAEvent.objects.filter(tracking=tracking).values_list("event_type", flat=True))
    assert kinds.count("BREACHED") == 2 and kinds.count("ESCALATED") == 1 and kinds.count("WARNING") <= 2
    sent = Notification.objects.filter(source="sla")
    assert sent.filter(recipient=s["ops"].user, title__contains="breached").count() == 2
    assert sent.filter(recipient=s["svc"].user, title__contains="escalation").count() == 1


def test_concurrent_acknowledge_succeeds_once(sla_, monkeypatch):
    s = sla_
    freeze(monkeypatch, T0)
    incidents.create_request(s["org"], asset=s["asset"], reporter=s["tech"], title="Leak", severity="HIGH",
                             actor=s["tech"].user)
    freeze(monkeypatch, at(40))
    sla.process_organization(s["org"])
    breach = SLABreach.objects.get()

    def ack():
        try:
            sla.acknowledge_breach(SLABreach.objects.get(pk=breach.pk), actor=s["ops"].user)
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return type(exc).__name__

    results = race([ack for _ in range(5)])
    assert results.count("ok") == 1 and results.count("Conflict") == 4
