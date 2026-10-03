"""Celery tasks for M11. Idempotent (a warning / breach / escalation is persisted once under a unique key, a second
run finds it and does nothing), retry-safe (one transaction and row lock per tracking), tenant-safe (one organization
at a time inside ``tenant_context``; suspended organizations are skipped)."""
import logging

from celery import shared_task
from django.db import OperationalError

log = logging.getLogger(__name__)


@shared_task(name="apps.sla.tasks.monitor_sla", bind=True, autoretry_for=(OperationalError,), retry_backoff=True,
             max_retries=5)
def monitor_sla(self) -> dict:
    from apps.tenancy.models import Organization

    from . import services

    total = {"organizations": 0, "checked": 0, "warnings": 0, "breaches": 0, "escalations": 0, "errors": 0}
    for org in Organization.objects.filter(status=Organization.Status.ACTIVE):
        total["organizations"] += 1
        res = services.process_organization(org)
        for key in ("checked", "warnings", "breaches", "escalations", "errors"):
            total[key] += res[key]
    log.info("SLA monitor finished", extra={"sla_result": total})
    return total
