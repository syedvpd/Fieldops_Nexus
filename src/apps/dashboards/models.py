from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.core.models import TenantOwnedModel


class ReportSnapshot(TenantOwnedModel):
    """HPE 8.2 ``ReportSnapshot``: the organization-wide dashboard figures of one section for one trailing window,
    frozen by the daily Celery job so trends can be compared later without recomputing history. The figures come
    from the same ``dashboards.metrics`` queries as the live pages (no second formula). One row per organization,
    section and window end; once written it is never changed."""

    kind = models.CharField(max_length=20)  # a key of dashboards.metrics.SECTIONS
    period_from = models.DateField()
    period_to = models.DateField()
    payload = models.JSONField(encoder=DjangoJSONEncoder)
    taken_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_to", "kind"]
        constraints = [models.UniqueConstraint(fields=["organization", "kind", "period_to"],
                                               name="uniq_report_snapshot_per_org_kind_day")]
        indexes = [models.Index(fields=["organization", "kind", "-period_to"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Report snapshots are immutable.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.kind} {self.period_from}..{self.period_to}"
