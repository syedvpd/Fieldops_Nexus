"""M12 read side: identifiers are visible only for assets the caller may see (``qr.view`` site scope)."""
from __future__ import annotations

import uuid

from apps.rbac import services as rbac
from apps.sites.selectors import scoped_get

from .models import AssetIdentifier, ScanEvent


def identifiers_for(membership, org):
    scope = rbac.site_scope(membership, "qr.view")
    qs = AssetIdentifier.objects.for_organization(org).select_related("asset")
    return scope.filter(qs, "asset__site_id")


def get_identifier(membership, org, pk) -> AssetIdentifier:
    return scoped_get(identifiers_for(membership, org), pk, "Label")


def for_asset(membership, org, asset):
    return identifiers_for(membership, org).filter(asset=asset)


def active_for_asset(membership, org, asset, kind):
    return for_asset(membership, org, asset).filter(kind=kind, is_active=True).first()


def recent_scans(org, asset, limit=10):
    return ScanEvent.objects.for_organization(org).filter(asset=asset).select_related(
        "scanned_by", "service_request")[:limit]


def uuid_or_none(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
