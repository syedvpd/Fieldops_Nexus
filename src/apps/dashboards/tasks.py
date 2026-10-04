"""Celery for M14: daily report snapshots. One independent, idempotent task per active organization."""
import logging

from celery import shared_task
from django.db import OperationalError

log = logging.getLogger(__name__)


@shared_task(name="apps.dashboards.tasks.snapshot_organization", bind=True, autoretry_for=(OperationalError,),
             retry_backoff=True, max_retries=5)
def snapshot_organization(self, organization_id: str) -> dict:
    from apps.tenancy.models import Organization

    from . import services

    org = Organization.objects.filter(pk=organization_id, status=Organization.Status.ACTIVE).first()
    if org is None:
        return {"organization": organization_id, "skipped": "inactive or unknown"}
    return {"organization": organization_id, **services.snapshot_organization(org)}


@shared_task(name="apps.dashboards.tasks.fan_out_report_snapshots")
def fan_out_report_snapshots() -> dict:
    from apps.tenancy.models import Organization

    ids = [str(pk) for pk in Organization.objects.filter(status=Organization.Status.ACTIVE).values_list("pk", flat=True)]
    for pk in ids:
        snapshot_organization.delay(pk)
    return {"dispatched": len(ids)}
