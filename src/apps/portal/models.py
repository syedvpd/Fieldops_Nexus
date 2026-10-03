"""M13 Client / Requester Portal models.

The portal is an interface over M05: a client's request IS an M05 ``ServiceRequest`` (no second request model).
What M13 owns is WHO a client is and WHICH assets they may raise requests about:

* ``PortalAccount``: marks one organization membership as a portal client (enabled / disabled by staff holding
  ``portal.manage``). A client has only the ``portal.request.*`` permissions, so ordinary ERP screens and APIs
  refuse them.
* ``PortalAssetGrant``: an explicit asset the client may report on. No grant, no request (no arbitrary assets).
"""
from django.conf import settings
from django.db import models

from apps.core.models import TenantOwnedModel


class PortalAccount(TenantOwnedModel):
    membership = models.OneToOneField("tenancy.Membership", on_delete=models.PROTECT, related_name="portal_account")
    company = models.CharField(max_length=150, blank=True, help_text="Client company / department, for staff.")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["membership__user__email"]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self):
        return f"portal:{self.membership_id}"


class PortalAssetGrant(TenantOwnedModel):
    account = models.ForeignKey(PortalAccount, on_delete=models.CASCADE, related_name="grants")
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="portal_grants")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "asset"], name="uniq_portal_grant")]
        indexes = [models.Index(fields=["organization", "asset"])]
