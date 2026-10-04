"""M12 QR / barcode identification models.

An ``AssetIdentifier`` is an OPAQUE random token attached to one M02 asset (the asset stays the only authoritative
asset record; scanning never creates assets). The token carries no organization, asset id or secret: it is only a
lookup key. Knowing it grants nothing; authorization (membership, permission, tenant, site scope) happens after the
lookup, in ``identification.services``. At most one ACTIVE identifier per asset and kind (database constraint);
replacing a label revokes the old token. ``ScanEvent`` records each successful resolution and links the service
request it produced (the "scan-to-service-event" entry point into M05).
"""
import secrets

from django.conf import settings
from django.db import models

from apps.core.models import TenantOwnedModel

BARCODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I: safe to read and type


def new_token(kind: str) -> str:
    if kind == AssetIdentifier.Kind.BARCODE:
        return "".join(secrets.choice(BARCODE_ALPHABET) for _ in range(12))
    return secrets.token_urlsafe(16)  # 128 bits, URL-safe


class AssetIdentifier(TenantOwnedModel):
    class Kind(models.TextChoices):
        QR = "QR", "QR code"
        BARCODE = "BARCODE", "Barcode (Code 128)"

    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="identifiers")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    token = models.CharField(max_length=64, editable=False)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    revoked_reason = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # tokens are globally unique: a scan arrives with the token only
            models.UniqueConstraint(fields=["token"], name="uniq_identifier_token"),
            models.UniqueConstraint(fields=["asset", "kind"], condition=models.Q(is_active=True),
                                    name="uniq_active_identifier_per_asset_kind"),
            models.CheckConstraint(
                condition=models.Q(is_active=True, revoked_at__isnull=True)
                | models.Q(is_active=False, revoked_at__isnull=False), name="identifier_revocation_consistent"),
        ]
        indexes = [models.Index(fields=["organization", "asset"])]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.asset_id}"


class ScanEvent(TenantOwnedModel):
    """Append-only record of one resolved scan."""

    identifier = models.ForeignKey(AssetIdentifier, on_delete=models.PROTECT, related_name="scans")
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="scan_events")
    scanned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    service_request = models.ForeignKey("incidents.ServiceRequest", null=True, blank=True, on_delete=models.PROTECT,
                                        related_name="scan_events")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "asset"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            # the only permitted change is attaching the request created from this scan
            if set(kwargs.get("update_fields") or []) - {"service_request", "updated_at"}:
                raise ValueError("ScanEvent is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ScanEvent is append-only.")
