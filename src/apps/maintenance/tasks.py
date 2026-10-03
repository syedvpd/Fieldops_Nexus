"""Celery tasks for M04. Idempotent (running them again changes nothing until the next occurrence is due),
retry-safe (each schedule generates in its own transaction under a row lock), tenant-safe (one organization at a
time inside ``tenant_context``; suspended organizations are skipped) and observable (structured result + log +
``MaintenanceSchedule.last_run_at / last_error``)."""
import logging

from celery import shared_task
from django.db import OperationalError

log = logging.getLogger(__name__)


@shared_task(name="apps.maintenance.tasks.generate_due_maintenance")
def generate_due_maintenance() -> dict:
    from apps.tenancy.models import Organization

    from . import services

    total = {"organizations": 0, "generated": 0, "errors": 0, "reminders": 0}
    for org in Organization.objects.filter(status=Organization.Status.ACTIVE):
        total["organizations"] += 1
        result = services.run_for_organization(org)
        for key in ("generated", "errors", "reminders"):
            total[key] += result[key]
    log.info("PM scheduler finished", extra={"pm_result": total})
    return total


@shared_task(name="apps.maintenance.tasks.generate_schedule", bind=True, autoretry_for=(OperationalError,),
             retry_backoff=True, max_retries=5)
def generate_schedule(self, organization_id: str, schedule_id: str) -> str | None:
    """Generates one schedule of one organization (safe to retry: a second run finds nothing due, returns None)."""
    from apps.core.tenant import tenant_context
    from apps.tenancy.models import Organization

    from . import services
    from .models import MaintenanceSchedule

    org = Organization.objects.get(pk=organization_id, status=Organization.Status.ACTIVE)
    with tenant_context(org):
        cycle = services.generate_cycle(MaintenanceSchedule.objects.get(pk=schedule_id))
    return str(cycle.pk) if cycle else None
