"""M13 service layer. Every client action re-checks, server-side: ACTIVE membership of the organization, an
ENABLED portal account, request OWNERSHIP (the client reported it) and the M05 state rules. Requests are created
and changed only through ``incidents.services`` (M05 stays authoritative); M13 never edits work orders, stock or
SLAs."""
from __future__ import annotations

from django.db import transaction

from apps.audit import services as audit
from apps.core.exceptions import Conflict, NotFound, PermissionDenied, ValidationFailed
from apps.incidents import services as incidents
from apps.incidents.models import ServiceRequest
from apps.notifications import services as notifications
from apps.rbac import services as rbac

from .models import PortalAccount, PortalAssetGrant

URGENCIES = ("LOW", "MEDIUM", "HIGH")  # clients cannot declare CRITICAL; staff re-rate at triage
KINDS = ("INCIDENT", "SERVICE_REQUEST")
MAX_FILES = 5


# --- accounts (staff, portal.manage) ---------------------------------------------------------------------------------


def _is_client_only(membership) -> bool:
    perms = rbac.membership_permissions(membership)
    return bool(perms) and all(p.startswith("portal.request.") for p in perms) and not rbac.site_permissions(
        membership)


@transaction.atomic
def enable_account(org, membership, *, company="", actor, request=None) -> PortalAccount:
    if membership.organization_id != org.pk or not membership.is_active:
        raise ValidationFailed("Choose an active member of this organization.", code="membership_invalid")
    if not _is_client_only(membership):
        raise Conflict("Only members whose role is Client / Requester can be portal clients; ERP staff keep their "
                       "own screens.", code="not_client_role")
    acct = PortalAccount.objects.for_organization(org).filter(membership=membership).first()
    if acct is not None:
        raise Conflict("This member is already a portal client.", code="account_exists")
    acct = PortalAccount(organization=org, membership=membership, company=(company or "").strip()[:150],
                         created_by=actor)
    acct.save()
    audit.record("portal.account_enabled", actor=actor, organization=org, target=acct,
                 target_repr=f"portal client {membership.user.email}", after={"company": acct.company},
                 request=request)
    return acct


@transaction.atomic
def set_account_active(acct, active: bool, *, actor, request=None) -> PortalAccount:
    acct = PortalAccount.objects.select_for_update(of=("self",)).get(pk=acct.pk)
    if acct.is_active == active:
        return acct
    acct.is_active = active
    acct.save(update_fields=["is_active", "updated_at"])
    audit.record("portal.account_enabled" if active else "portal.account_disabled", actor=actor,
                 organization=acct.organization, target=acct, before={"is_active": not active},
                 after={"is_active": active}, request=request)
    return acct


@transaction.atomic
def grant_asset(acct, asset, *, actor, request=None) -> PortalAssetGrant:
    if asset.organization_id != acct.organization_id:
        raise NotFound("Asset not found.")
    if asset.status in ("RETIRED", "DISPOSED"):
        raise Conflict("Retired or disposed assets cannot be granted.", code="asset_terminal")
    if PortalAssetGrant.objects.for_organization(acct.organization).filter(account=acct, asset=asset).exists():
        raise Conflict("The client already has this asset.", code="grant_exists")
    g = PortalAssetGrant(organization=acct.organization, account=acct, asset=asset, granted_by=actor)
    g.save()
    audit.record("portal.asset_granted", actor=actor, organization=acct.organization, target=acct,
                 after={"asset": asset.asset_tag}, request=request)
    return g


@transaction.atomic
def revoke_asset(acct, asset, *, actor, request=None):
    qs = PortalAssetGrant.objects.for_organization(acct.organization).filter(account=acct, asset=asset)
    if not qs.exists():
        raise ValidationFailed("The client does not have this asset.", code="grant_missing")
    qs.delete()
    audit.record("portal.asset_revoked", actor=actor, organization=acct.organization, target=acct,
                 before={"asset": asset.asset_tag}, request=request)


# --- client actions --------------------------------------------------------------------------------------------------


def active_account(membership) -> PortalAccount:
    acct = PortalAccount.objects.for_organization(membership.organization).filter(
        membership=membership, is_active=True).first()
    if acct is None:
        raise PermissionDenied("Your portal access is not enabled. Contact your service provider.")
    return acct


def _owned(membership, sr: ServiceRequest):
    if sr.organization_id != membership.organization_id or sr.reported_by_id != membership.pk:
        raise NotFound("Request not found.")  # same answer as a missing request: no existence leak


def _staff_to_notify(sr):
    from apps.tenancy.models import Membership

    out = []
    for m in Membership.objects.for_organization(sr.organization).filter(
            status=Membership.Status.ACTIVE).select_related("user"):
        if m.pk != sr.reported_by_id and rbac.has_permission(m, "incident.triage", sr.site_id):
            out.append(m.user)
    return out


@transaction.atomic
def submit_request(membership, *, asset, title, description="", kind="INCIDENT", urgency="MEDIUM", uploads=(),
                   request=None) -> ServiceRequest:
    """Creates the M05 request for the client. One transaction: an invalid attachment rejects the whole submission,
    nothing is half-saved."""
    acct = active_account(membership)
    if kind not in KINDS:
        raise ValidationFailed("Unknown request type.", code="invalid_kind")
    if urgency not in URGENCIES:
        raise ValidationFailed("Unknown urgency.", code="invalid_urgency")
    uploads = [u for u in uploads if u]
    if len(uploads) > MAX_FILES:
        raise ValidationFailed(f"At most {MAX_FILES} files can be attached at once.", code="too_many_files")
    if not PortalAssetGrant.objects.for_organization(membership.organization).filter(
            account=acct, asset_id=getattr(asset, "pk", asset)).exists():
        raise NotFound("Asset not found.")  # granted assets only; anything else looks absent
    sr = incidents.create_request(membership.organization, asset=asset, reporter=membership, title=title,
                                  description=description, kind=kind, severity=urgency, actor=membership.user,
                                  request=request)
    for up in uploads:
        incidents.add_evidence(sr, up, actor=membership.user, request=request)
    audit.record("portal.request_submitted", actor=membership.user, organization=membership.organization,
                 target=sr, after={"number": sr.number, "asset": asset.asset_tag, "attachments": len(uploads)},
                 request=request)
    notifications.notify(sr.organization, _staff_to_notify(sr), title=f"New client request {sr.number}",
                         body=f"{sr.title} ({asset.asset_tag})", link=f"/app/incidents/{sr.pk}/",
                         source="portal")
    return sr


@transaction.atomic
def confirm(membership, sr, *, request=None) -> ServiceRequest:
    """Client confirms the resolution (RESOLVED -> CONFIRMED). Closing stays with staff (CONFIRMED -> CLOSED)."""
    active_account(membership)
    if not rbac.has_permission(membership, "portal.request.confirm"):
        raise PermissionDenied("You may not confirm requests.")
    sr = ServiceRequest.objects.select_for_update(of=("self",)).get(pk=sr.pk)
    _owned(membership, sr)
    sr = incidents.transition(sr, action="confirm", actor=membership.user, request=request)
    audit.record("portal.request_confirmed", actor=membership.user, organization=sr.organization, target=sr,
                 after={"number": sr.number}, request=request)
    return sr


@transaction.atomic
def reopen(membership, sr, *, reason, request=None) -> ServiceRequest:
    active_account(membership)
    if not rbac.has_permission(membership, "portal.request.confirm"):
        raise PermissionDenied("You may not reopen requests.")
    sr = ServiceRequest.objects.select_for_update(of=("self",)).get(pk=sr.pk)
    _owned(membership, sr)
    sr = incidents.transition(sr, action="reopen", reason=reason, actor=membership.user, request=request)
    audit.record("portal.request_reopened", actor=membership.user, organization=sr.organization, target=sr,
                 after={"number": sr.number, "reason": (reason or "").strip()[:300]}, request=request)
    return sr


@transaction.atomic
def add_attachment(membership, sr, upload, *, description="", request=None):
    active_account(membership)
    sr = ServiceRequest.objects.select_for_update(of=("self",)).get(pk=sr.pk)
    _owned(membership, sr)
    if sr.status in ("CONFIRMED", "CLOSED", "REJECTED"):
        raise Conflict("Files can no longer be added to this request.", code="request_locked")
    att = incidents.add_evidence(sr, upload, description=description, actor=membership.user, request=request)
    return att
