"""Celery task for M10: renewal alerts. Idempotent (an agreement alerts once per end date), tenant-safe (one
organization at a time inside ``tenant_context``)."""
import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(name="apps.contracts.tasks.send_renewal_alerts")
def send_renewal_alerts() -> dict:
    from apps.core.tenant import tenant_context
    from apps.tenancy.models import Organization

    from . import services

    total = {"organizations": 0, "alerts": 0}
    for org in Organization.objects.filter(status=Organization.Status.ACTIVE):
        total["organizations"] += 1
        with tenant_context(org):
            total["alerts"] += services.run_alerts(org)
    log.info("Contract renewal alerts finished", extra={"contract_result": total})
    return total
