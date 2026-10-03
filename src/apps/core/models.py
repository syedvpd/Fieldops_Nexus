import uuid

from django.db import models

from .tenant import TenantManager, get_current_org


class BaseModel(models.Model):
    """UUID primary keys: opaque identifiers, no enumerable sequential IDs in URLs/APIs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantOwnedModel(BaseModel):
    """Every tenant-owned record links directly to an Organization (docs/DECISIONS.md D-004)."""

    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="+", editable=False
    )

    objects = TenantManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        ctx = get_current_org()
        if self._state.adding and not self.organization_id and ctx is not None:
            self.organization = ctx
        if not self.organization_id:
            raise ValueError(f"{type(self).__name__} requires an organization.")
        if ctx is not None and self.organization_id != ctx.pk:
            raise ValueError("Cross-tenant write blocked: object organization differs from active tenant.")
        super().save(*args, **kwargs)
