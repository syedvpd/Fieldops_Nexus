"""Report snapshots (HPE 8.4 "report snapshots" Celery family). Organization-wide: computed with the organization's
Owner membership (all sites) through the SAME metric functions the dashboards use."""
from __future__ import annotations

import datetime
import json
import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.core.tenant import tenant_context

from . import metrics
from .models import ReportSnapshot

log = logging.getLogger(__name__)
WINDOW_DAYS = 30


def _owner_membership(org):
    from apps.tenancy.models import Membership

    return (Membership.objects.for_organization(org)
            .filter(status=Membership.Status.ACTIVE, membership_roles__role__is_owner=True,
                    membership_roles__site__isnull=True).select_related("user").first())


def snapshot_organization(org, day: datetime.date | None = None) -> dict:
    """Takes (idempotently) one snapshot per dashboard section for ``org``; a section already stored for ``day`` is
    left untouched. Returns {"created": n, "existing": n, "skipped": reason|None}."""
    day = day or timezone.now().date()
    result = {"created": 0, "existing": 0, "skipped": None}
    with tenant_context(org):
        owner = _owner_membership(org)
        if owner is None:
            result["skipped"] = "no active owner"
            return result
        params = {"from": (day - datetime.timedelta(days=WINDOW_DAYS - 1)).isoformat(), "to": day.isoformat()}
        f = metrics.parse_filters(params, owner, org)
        for kind, (_label, fn, _codes) in metrics.SECTIONS.items():
            if ReportSnapshot.objects.for_organization(org).filter(kind=kind, period_to=day).exists():
                result["existing"] += 1
                continue
            data = json.loads(json.dumps(fn(owner, org, f), cls=DjangoJSONEncoder))
            try:
                with transaction.atomic():
                    ReportSnapshot(organization=org, kind=kind, period_from=f.from_date, period_to=f.to_date,
                                   payload=data).save()
            except IntegrityError:  # a concurrent run stored it first
                result["existing"] += 1
                continue
            result["created"] += 1
        if result["created"]:
            audit.record("report.snapshot_taken", organization=org, target_repr=f"{result['created']} sections {day}",
                         after={"day": day.isoformat(), "created": result["created"]})
    return result
