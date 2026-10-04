"""M12 service layer: identifier lifecycle, label rendering and scan resolution.

Security model (QR is an identifier, never an authorization): a token is looked up ONLY inside organizations the
caller holds an ACTIVE membership in (one tenant context at a time), so a foreign or unknown token is
indistinguishable from a typo. After the lookup the asset must be visible to the caller's membership (permission +
site scope); only then is the scan recorded and the asset returned. Every denial is audited as a security event.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets import selectors as asset_selectors
from apps.audit import services as audit
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.core.tenant import tenant_context
from apps.rbac import services as rbac

from .models import AssetIdentifier, ScanEvent, new_token

Kind = AssetIdentifier.Kind
TERMINAL = ("RETIRED", "DISPOSED")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _limit(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


# --- abuse protection -----------------------------------------------------------------------------------------------
# Failed resolutions (unknown / foreign / revoked / forbidden tokens) are counted per user in the shared cache; past the
# limit every further attempt is refused until the window passes. A valid scan never resets the counter, so valid
# scans cannot be interleaved with guessing to stay below it. The first refusal is audited once per window.


def _fail_key(user) -> str:
    return f"identification:scanfail:{user.pk}"


def throttled(user) -> bool:
    return int(cache.get(_fail_key(user), 0)) >= _limit("SCAN_FAIL_LIMIT", 15)


def _register_failure(user) -> None:
    key, window = _fail_key(user), _limit("SCAN_FAIL_WINDOW_SECONDS", 600)
    cache.add(key, 0, window)
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, window)
URL_PREFIX = "/app/s/"


def fingerprint(token: str) -> str:
    """Non-reversible reference for audit rows (never store the raw token of a failed scan)."""
    return hashlib.sha256((token or "").encode()).hexdigest()[:12]


def extract_token(text: str) -> str:
    """Accepts a raw token or the full scanned URL (``.../app/s/<token>/``)."""
    text = (text or "").strip()
    if URL_PREFIX in text:
        text = text.split(URL_PREFIX, 1)[1]
    return text.split("?")[0].split("#")[0].strip("/ ")


# --- lifecycle -------------------------------------------------------------------------------------------------------


def _kind(value):
    if value not in Kind.values:
        raise ValidationFailed("Unknown identifier type.", code="invalid_kind")
    return value


def _create(asset, kind, actor, request):
    for _ in range(5):  # a collision of 128 / 60 random bits is practically impossible; retry anyway
        try:
            with transaction.atomic():
                ident = AssetIdentifier(organization=asset.organization, asset=asset, kind=kind,
                                        token=new_token(kind), created_by=actor)
                ident.save()
                return ident
        except IntegrityError as exc:
            if "uniq_active_identifier_per_asset_kind" in str(exc):
                raise Conflict(f"This asset already has an active {kind.lower()} label; revoke or replace it.",
                               code="identifier_exists") from exc
    raise Conflict("Could not allocate a unique token; try again.", code="token_collision")


@transaction.atomic
def generate(asset, kind, *, actor, request=None) -> AssetIdentifier:
    kind = _kind(kind)
    if asset.status in TERMINAL:
        raise Conflict("Retired or disposed assets cannot receive new labels.", code="asset_terminal")
    from apps.assets.models import Asset

    asset = Asset.objects.select_for_update(of=("self",)).get(pk=asset.pk)  # serialises concurrent generation
    if AssetIdentifier.objects.for_organization(asset.organization).filter(asset=asset, kind=kind,
                                                                           is_active=True).exists():
        raise Conflict(f"This asset already has an active {kind.lower()} label; revoke or replace it.",
                       code="identifier_exists")
    ident = _create(asset, kind, actor, request)
    audit.record("qr.generated", actor=actor, organization=asset.organization, target=ident,
                 target_repr=f"{kind} label for {asset.asset_tag}",
                 after={"asset": asset.asset_tag, "kind": kind, "fingerprint": fingerprint(ident.token)},
                 request=request)
    return ident


def _revoke(ident, reason, actor, request, action="qr.revoked"):
    ident.is_active = False
    ident.revoked_at = timezone.now()
    ident.revoked_by = actor
    ident.revoked_reason = reason
    ident.save(update_fields=["is_active", "revoked_at", "revoked_by", "revoked_reason", "updated_at"])
    audit.record(action, actor=actor, organization=ident.organization, target=ident,
                 target_repr=f"{ident.kind} label for {ident.asset.asset_tag}",
                 before={"is_active": True}, after={"is_active": False, "reason": reason,
                                                    "fingerprint": fingerprint(ident.token)}, request=request)


@transaction.atomic
def revoke(ident, *, reason, actor, request=None) -> AssetIdentifier:
    ident = AssetIdentifier.objects.select_for_update(of=("self",)).select_related("asset").get(pk=ident.pk)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationFailed("A reason is required to revoke a label.", code="reason_required")
    if not ident.is_active:
        raise Conflict("This label is already revoked.", code="already_revoked")
    _revoke(ident, reason[:300], actor, request)
    return ident


@transaction.atomic
def regenerate(ident, *, reason, actor, request=None) -> AssetIdentifier:
    """Replaces a lost / damaged label: the old token stops resolving, a new one is issued (one transaction)."""
    ident = AssetIdentifier.objects.select_for_update(of=("self",)).select_related("asset").get(pk=ident.pk)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationFailed("A reason is required to replace a label.", code="reason_required")
    if not ident.is_active:
        raise Conflict("Only an active label can be replaced.", code="already_revoked")
    if ident.asset.status in TERMINAL:
        raise Conflict("Retired or disposed assets cannot receive new labels.", code="asset_terminal")
    _revoke(ident, reason[:300], actor, request, action="qr.replaced")
    return _create(ident.asset, ident.kind, actor, request)


# --- label rendering -------------------------------------------------------------------------------------------------


def scan_url(token: str, base: str = "") -> str:
    return f"{base.rstrip('/')}{URL_PREFIX}{token}/"


def qr_svg(url: str) -> str:
    import segno

    out = io.BytesIO()
    segno.make(url, error="m", micro=False).save(out, kind="svg", scale=4, border=2, xmldecl=False, nl=False)
    return out.getvalue().decode()


def qr_png(url: str) -> bytes:
    import segno

    out = io.BytesIO()
    segno.make(url, error="m", micro=False).save(out, kind="png", scale=8, border=3)
    return out.getvalue()


def barcode_svg(token: str) -> str:
    import barcode
    from barcode.writer import SVGWriter

    out = io.BytesIO()
    barcode.get("code128", token, writer=SVGWriter()).write(out, options={"write_text": True, "module_height": 12})
    svg = out.getvalue().decode()
    return svg[svg.index("<svg"):]


# --- scan resolution -------------------------------------------------------------------------------------------------


@dataclass
class Resolution:
    identifier: AssetIdentifier | None
    asset: object | None
    membership: object | None
    outcome: str  # RESOLVED | UNKNOWN | REVOKED | FORBIDDEN | THROTTLED
    asset_inactive: bool = False
    other_org: bool = False


def _lookup(org, token):
    with tenant_context(org):
        qs = AssetIdentifier.objects.for_organization(org).select_related("asset__site", "asset__zone",
                                                                          "asset__category")
        return qs.filter(token=token).first() or qs.filter(kind=Kind.BARCODE, token=token.upper()).first()


def locate(user, token, current_membership):
    """Finds (membership, identifier) among the caller's own active memberships, current organization first.
    Nothing outside those organizations is ever queried."""
    from apps.tenancy import selectors as tenancy

    if not TOKEN_RE.match(token or ""):
        return None, None
    members = list(tenancy.active_memberships(user))
    members.sort(key=lambda m: m.pk != getattr(current_membership, "pk", None))
    for m in members:
        ident = _lookup(m.organization, token)
        if ident is not None:
            return m, ident
    return None, None


def resolve(user, token, current_membership, *, request=None) -> Resolution:
    """Token -> asset, authorizing the caller AFTER the lookup. Records a ScanEvent on success and an audit
    security event on every failure."""
    token = extract_token(token)
    org = getattr(current_membership, "organization", None)
    if throttled(user):
        if cache.add(f"{_fail_key(user)}:audited", 1, _limit("SCAN_FAIL_WINDOW_SECONDS", 600)):
            audit.record("qr.scan_throttled", actor=user, organization=org, request=request,
                         metadata={"fingerprint": fingerprint(token)})
        return Resolution(None, None, None, "THROTTLED")
    m, ident = locate(user, token, current_membership)
    if ident is None:
        _register_failure(user)
        audit.record("qr.scan_unknown", actor=user, organization=org, request=request,
                     metadata={"fingerprint": fingerprint(token)})
        return Resolution(None, None, None, "UNKNOWN")
    with tenant_context(m.organization):
        try:
            asset = asset_selectors.get_asset(m, m.organization, ident.asset_id)
        except NotFound:
            _register_failure(user)
            audit.record("qr.scan_denied", actor=user, organization=m.organization, request=request,
                         metadata={"fingerprint": fingerprint(token), "reason": "no access to the asset"})
            return Resolution(ident, None, m, "FORBIDDEN")
        inactive = asset.status in TERMINAL
        if not ident.is_active:
            _register_failure(user)
            audit.record("qr.scan_revoked", actor=user, organization=m.organization, target=asset, request=request,
                         metadata={"fingerprint": fingerprint(token)})
            return Resolution(ident, asset, m, "REVOKED", inactive, m.organization_id != getattr(org, "pk", None))
        # one scan = one event: a refresh / the follow-up POST of the same user within the dedupe window reuses it
        since = timezone.now() - timezone.timedelta(seconds=_limit("SCAN_DEDUPE_SECONDS", 600))
        if not ScanEvent.objects.for_organization(m.organization).filter(
                identifier=ident, scanned_by=user, created_at__gte=since).exists():
            with transaction.atomic():
                ScanEvent(organization=m.organization, identifier=ident, asset=asset, scanned_by=user).save()
                audit.record("qr.scanned", actor=user, organization=m.organization, target=asset, request=request,
                             metadata={"kind": ident.kind, "fingerprint": fingerprint(token)})
        return Resolution(ident, asset, m, "RESOLVED", inactive, m.organization_id != getattr(org, "pk", None))


@transaction.atomic
def report_from_scan(res: Resolution, *, title, description="", kind="INCIDENT", severity="MEDIUM", actor,
                     request=None):
    """Scan-to-service-event: creates the M05 request through its service (M05 stays authoritative) and links it to
    the scan. The caller must be allowed to report for the asset's site."""
    from apps.incidents import services as incidents

    if res.outcome != "RESOLVED":
        raise Conflict("Only a valid scan can open a request.", code="scan_not_resolved")
    m = res.membership
    if not rbac.has_permission(m, "incident.create", res.asset.site_id):
        from apps.core.exceptions import PermissionDenied

        raise PermissionDenied("You are not allowed to report incidents for this site.")
    with tenant_context(m.organization):
        sr = incidents.create_request(m.organization, asset=res.asset, reporter=m, title=title,
                                      description=description, kind=kind, severity=severity, actor=actor,
                                      request=request)
        since = timezone.now() - timezone.timedelta(seconds=_limit("SCAN_DEDUPE_SECONDS", 600))
        event = ScanEvent.objects.for_organization(m.organization).filter(
            identifier=res.identifier, scanned_by=actor, service_request__isnull=True,
            created_at__gte=since).order_by("-created_at").first()
        if event is None:  # defensive: the scan was recorded by resolve(); never lose the link
            event = ScanEvent(organization=m.organization, identifier=res.identifier, asset=res.asset,
                              scanned_by=actor)
        event.service_request = sr
        event.save()
        audit.record("qr.service_event_created", actor=actor, organization=m.organization, target=sr,
                     after={"asset": res.asset.asset_tag, "request": sr.number}, request=request)
    return sr
