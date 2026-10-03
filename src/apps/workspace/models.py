from django.conf import settings
from django.db import models

from apps.core.models import TenantOwnedModel


class WorkNote(TenantOwnedModel):
    """M07: a technician's progress note on a work order. Append-only (a correction is a new note)."""

    work_order = models.ForeignKey("workorders.WorkOrder", on_delete=models.PROTECT, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["organization", "work_order"])]
        constraints = [models.CheckConstraint(condition=~models.Q(body=""), name="work_note_body_not_empty")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("WorkNote is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("WorkNote is append-only.")
