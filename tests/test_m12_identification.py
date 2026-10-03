"""M12 QR / barcode: opaque identifiers, uniqueness, replace / revoke, scan resolution that authorizes AFTER the
lookup (unknown, modified, cross-tenant, revoked, inactive asset, unauthorized, site-scoped, client), label
rendering, API, UI and scan-to-service-event."""
import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from rest_framework.test import APIClient

from apps.assets.models import Asset
from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, ValidationFailed
from apps.identification import services as idn
from apps.identification.models import AssetIdentifier, ScanEvent
from apps.incidents.models import ServiceRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def q_(p3, make_member, org_b, make_site, make_asset):
    am = make_member(p3["org"], "am@alpha.test", "asset_manager")
    client = make_member(p3["org"], "client@alpha.test", "client_requester")
    b_am = make_member(org_b, "am@beta.test", "asset_manager")
    b_asset = make_asset(org_b, make_site(org_b, "B9"), "B-PUMP")
    return {**p3, "am": am, "client": client, "org_b": org_b, "b_am": b_am, "b_asset": b_asset}


def api(user, org):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


def web(user):
    c = Client()
    c.force_login(user)
    return c


def gen(q, kind="QR", asset=None):
    return idn.generate(asset or q["asset"], kind, actor=q["am"].user)


# --- identifiers -------------------------------------------------------------------------------------------------


def test_token_is_opaque_unique_and_persisted(q_):
    a, b = gen(q_), gen(q_, asset=q_["asset2"])
    assert a.token != b.token and len(a.token) >= 20
    for secret in (str(q_["asset"].pk), q_["org"].slug, q_["asset"].asset_tag, str(q_["org"].pk)):
        assert secret.lower() not in a.token.lower()
    bc = gen(q_, "BARCODE")
    assert len(bc.token) == 12 and bc.token.isupper() and not set(bc.token) & set("01OI")
    assert AssetIdentifier.objects.for_organization(q_["org"]).count() == 3
    assert AuditLog.objects.filter(action="qr.generated", organization=q_["org"]).count() == 3


def test_duplicate_generation_is_rejected_and_db_enforced(q_):
    gen(q_)
    with pytest.raises(Conflict) as e:
        gen(q_)
    assert e.value.code == "identifier_exists"
    gen(q_, "BARCODE")  # a different kind is a separate, explicit label
    with pytest.raises(IntegrityError), transaction.atomic():  # even bypassing the service
        AssetIdentifier(organization=q_["org"], asset=q_["asset"], kind="QR", token="X" * 20).save()
    with pytest.raises(ValidationFailed):
        gen(q_, "RFID")


def test_replace_and_revoke(q_):
    old = gen(q_)
    new = idn.regenerate(old, reason="Label torn", actor=q_["am"].user)
    old.refresh_from_db()
    assert not old.is_active and old.revoked_reason == "Label torn" and new.is_active and new.token != old.token
    assert AssetIdentifier.objects.for_organization(q_["org"]).filter(asset=q_["asset"], is_active=True).count() == 1
    with pytest.raises(ValidationFailed):
        idn.revoke(new, reason=" ", actor=q_["am"].user)
    idn.revoke(new, reason="Asset moved", actor=q_["am"].user)
    with pytest.raises(Conflict):
        idn.revoke(new, reason="again", actor=q_["am"].user)
    assert {a.action for a in AuditLog.objects.filter(organization=q_["org"], action__startswith="qr.")} >= {
        "qr.generated", "qr.replaced", "qr.revoked"}


def test_terminal_assets_cannot_get_labels(q_):
    Asset.objects.filter(pk=q_["asset"].pk).update(status="RETIRED")
    q_["asset"].refresh_from_db()
    with pytest.raises(Conflict) as e:
        gen(q_)
    assert e.value.code == "asset_terminal"


def test_label_rendering(q_):
    ident = gen(q_)
    url = idn.scan_url(ident.token, "https://ops.example.test")
    assert url == f"https://ops.example.test/app/s/{ident.token}/"
    svg = idn.qr_svg(url)
    assert svg.startswith("<svg") and idn.qr_png(url)[:4] == b"\x89PNG"
    bc = gen(q_, "BARCODE")
    assert "<svg" in idn.barcode_svg(bc.token)
    assert idn.extract_token(url) == ident.token and idn.extract_token(f"  {ident.token}  ") == ident.token


# --- resolution (authorization after lookup) ---------------------------------------------------------------------


def test_valid_scan_resolves_and_is_recorded(q_):
    ident = gen(q_)
    res = idn.resolve(q_["tech"].user, ident.token, q_["tech"])
    assert res.outcome == "RESOLVED" and res.asset == q_["asset"] and not res.asset_inactive
    assert ScanEvent.objects.for_organization(q_["org"]).filter(identifier=ident, scanned_by=q_["tech"].user).count() == 1
    assert AuditLog.objects.filter(action="qr.scanned", organization=q_["org"]).count() == 1
    bc = gen(q_, "BARCODE")
    assert idn.resolve(q_["tech"].user, bc.token.lower(), q_["tech"]).outcome == "RESOLVED"  # barcode readers vary in case
    assert idn.resolve(q_["tech"].user, idn.scan_url(ident.token, "http://x"), q_["tech"]).outcome == "RESOLVED"


def test_unknown_and_modified_tokens_do_not_resolve(q_):
    ident = gen(q_)
    flipped = ident.token[:-1] + ("A" if ident.token[-1] != "A" else "B")
    for bad in (flipped, "nope", "", "x" * 200, "../../etc/passwd", ident.token + "x", "AAAAAAAAAAAAAAAAAAAAAA"):
        res = idn.resolve(q_["tech"].user, bad, q_["tech"])
        assert res.outcome == "UNKNOWN" and res.asset is None, bad
    assert not ScanEvent.objects.for_organization(q_["org"]).exists()
    assert AuditLog.objects.filter(action="qr.scan_unknown", organization=q_["org"]).count() >= 5
    assert not AuditLog.objects.filter(action="qr.scan_unknown", metadata__fingerprint=flipped).exists()  # never raw


def test_cross_tenant_token_is_indistinguishable_from_unknown(q_):
    theirs = idn.generate(q_["b_asset"], "QR", actor=q_["b_am"].user)
    res = idn.resolve(q_["tech"].user, theirs.token, q_["tech"])
    assert res.outcome == "UNKNOWN" and res.asset is None
    res = idn.resolve(q_["b_am"].user, theirs.token, q_["b_am"])
    assert res.outcome == "RESOLVED" and res.asset == q_["b_asset"]
    mine = gen(q_)
    assert idn.resolve(q_["b_am"].user, mine.token, q_["b_am"]).outcome == "UNKNOWN"


def test_user_in_two_organizations_resolves_into_the_right_one(q_, make_member):
    make_member(q_["org_b"], "tech@alpha.test", "technician")  # same person, second membership
    theirs = idn.generate(q_["b_asset"], "QR", actor=q_["b_am"].user)
    res = idn.resolve(q_["tech"].user, theirs.token, q_["tech"])
    assert res.outcome == "RESOLVED" and res.other_org and res.membership.organization == q_["org_b"]


def test_revoked_token_does_not_resolve_as_valid(q_):
    ident = gen(q_)
    idn.revoke(ident, reason="Replaced", actor=q_["am"].user)
    res = idn.resolve(q_["tech"].user, ident.token, q_["tech"])
    assert res.outcome == "REVOKED"
    assert not ScanEvent.objects.for_organization(q_["org"]).exists()
    with pytest.raises(Conflict):
        idn.report_from_scan(res, title="Leak", actor=q_["tech"].user)


def test_valid_qr_does_not_bypass_authorization(q_, make_scoped_member):
    ident = gen(q_)
    client = idn.resolve(q_["client"].user, ident.token, q_["client"])  # client role: no asset.view
    assert client.outcome == "FORBIDDEN" and client.asset is None
    scoped = make_scoped_member(q_["org"], "tech2s@alpha.test", "technician", [q_["site2"]])  # other site only
    assert idn.resolve(scoped.user, ident.token, scoped).outcome == "FORBIDDEN"
    ok = make_scoped_member(q_["org"], "tech1s@alpha.test", "technician", [q_["site"]])
    assert idn.resolve(ok.user, ident.token, ok).outcome == "RESOLVED"
    assert AuditLog.objects.filter(action="qr.scan_denied", organization=q_["org"]).count() == 2
    ScanEvent.objects.for_organization(q_["org"]).get()  # only the authorized scan was recorded


def test_inactive_asset_resolves_read_only_and_refuses_requests(q_):
    ident = gen(q_)
    Asset.objects.filter(pk=q_["asset"].pk).update(status="RETIRED")
    res = idn.resolve(q_["tech"].user, ident.token, q_["tech"])
    assert res.outcome == "RESOLVED" and res.asset_inactive
    with pytest.raises(Conflict):
        idn.report_from_scan(res, title="Still broken", actor=q_["tech"].user)
    assert not ServiceRequest.objects.for_organization(q_["org"]).exists()


def test_scan_to_service_event_links_request_and_audits(q_):
    ident = gen(q_)
    res = idn.resolve(q_["tech"].user, ident.token, q_["tech"])
    sr = idn.report_from_scan(res, title="Pump leaking", description="Seal weeping", severity="HIGH",
                              actor=q_["tech"].user)
    assert sr.asset == q_["asset"] and sr.reported_by == q_["tech"] and sr.status == "NEW"
    ev = ScanEvent.objects.for_organization(q_["org"]).get()
    assert ev.service_request == sr and ev.identifier == ident
    assert ServiceRequest.objects.for_organization(q_["org"]).count() == 1
    assert Asset.objects.for_organization(q_["org"]).count() == 2  # scanning never creates assets
    assert AuditLog.objects.filter(action="qr.service_event_created", target_id=str(sr.pk)).exists()


def test_reporting_requires_incident_create(q_):
    ident = gen(q_)
    res = idn.resolve(q_["reader"].user, ident.token, q_["reader"])  # auditor: asset.view but no incident.create
    assert res.outcome == "RESOLVED"
    from apps.core.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        idn.report_from_scan(res, title="Not allowed", actor=q_["reader"].user)


# --- API ---------------------------------------------------------------------------------------------------------


def test_api_label_management_rbac(q_):
    am, tech, ops = (api(q_[k].user, q_["org"]) for k in ("am", "tech", "ops"))
    body = {"asset": str(q_["asset"].pk), "kind": "QR"}
    assert APIClient().post("/api/v1/asset-identifiers/", body, format="json").status_code in (401, 403)
    assert tech.post("/api/v1/asset-identifiers/", body, format="json").status_code == 403
    assert ops.post("/api/v1/asset-identifiers/", body, format="json").status_code == 403  # *.view only
    r = am.post("/api/v1/asset-identifiers/", body, format="json")
    assert r.status_code == 201 and r.json()["scan_url"].endswith(f"/app/s/{r.json()['token']}/")
    assert am.post("/api/v1/asset-identifiers/", body, format="json").status_code == 409
    assert ops.get(f"/api/v1/asset-identifiers/{r.json()['id']}/").status_code == 200
    assert tech.get("/api/v1/asset-identifiers/").status_code == 403
    assert ops.post(f"/api/v1/asset-identifiers/{r.json()['id']}/revoke/", {"reason": "x"}, format="json"
                    ).status_code == 403
    assert am.post(f"/api/v1/asset-identifiers/{r.json()['id']}/revoke/", {}, format="json").status_code == 400
    new = am.post(f"/api/v1/asset-identifiers/{r.json()['id']}/replace/", {"reason": "Torn"}, format="json")
    assert new.status_code == 201 and new.json()["token"] != r.json()["token"]
    assert len(am.get("/api/v1/asset-identifiers/", {"asset": str(q_["asset"].pk), "active": "1"}).json()["results"]) == 1


def test_api_tenant_and_site_isolation(q_, make_scoped_member):
    theirs = idn.generate(q_["b_asset"], "QR", actor=q_["b_am"].user)
    mine = gen(q_)
    am = api(q_["am"].user, q_["org"])
    assert am.get(f"/api/v1/asset-identifiers/{theirs.pk}/").status_code == 404
    assert am.post(f"/api/v1/asset-identifiers/{theirs.pk}/revoke/", {"reason": "x"}, format="json").status_code == 404
    assert am.post("/api/v1/asset-identifiers/", {"asset": str(q_["b_asset"].pk), "kind": "QR"}, format="json"
                   ).status_code == 404
    theirs.refresh_from_db()
    assert theirs.is_active
    scoped = api(make_scoped_member(q_["org"], "am2@alpha.test", "asset_manager", [q_["site2"]]).user, q_["org"])
    assert scoped.get(f"/api/v1/asset-identifiers/{mine.pk}/").status_code == 404
    assert scoped.post("/api/v1/asset-identifiers/", {"asset": str(q_["asset"].pk), "kind": "BARCODE"},
                       format="json").status_code == 404


def test_api_scan_resolve_and_report(q_):
    ident = gen(q_)
    theirs = idn.generate(q_["b_asset"], "QR", actor=q_["b_am"].user)
    tech = api(q_["tech"].user, q_["org"])
    r = tech.post("/api/v1/scan/resolve/", {"token": ident.token}, format="json")
    assert r.status_code == 200 and r.json()["asset_tag"] == "P3-PUMP" and r.json()["outcome"] == "RESOLVED"
    assert tech.post("/api/v1/scan/resolve/", {"token": theirs.token}, format="json").status_code == 404
    assert tech.post("/api/v1/scan/resolve/", {"token": "garbage-token-123"}, format="json").status_code == 404
    assert api(q_["client"].user, q_["org"]).post("/api/v1/scan/resolve/", {"token": ident.token}, format="json"
                                                  ).status_code == 403
    assert api(q_["reader"].user, q_["org"]).post("/api/v1/scan/report/", {"token": ident.token, "title": "x" * 5},
                                                  format="json").status_code == 403
    r = tech.post("/api/v1/scan/report/", {"token": ident.token, "title": "Bearing noise", "severity": "LOW"},
                  format="json")
    assert r.status_code == 201 and r.json()["number"].startswith("INC-")
    assert ServiceRequest.objects.for_organization(q_["org"]).get().asset == q_["asset"]
    idn.revoke(ident, reason="done", actor=q_["am"].user)
    assert tech.post("/api/v1/scan/resolve/", {"token": ident.token}, format="json").status_code == 410
    assert tech.post("/api/v1/scan/report/", {"token": ident.token, "title": "After revoke"}, format="json"
                     ).status_code == 409


# --- UI ----------------------------------------------------------------------------------------------------------


def test_ui_label_panel_generate_replace_and_images(q_):
    am = web(q_["am"].user)
    asset = q_["asset"]
    assert am.get(f"/app/assets/{asset.pk}/?tab=labels").status_code == 200
    assert "Generate qr code" in am.get(f"/app/identification/assets/{asset.pk}/panel/").content.decode()
    assert am.post(f"/app/identification/assets/{asset.pk}/panel/generate/", {"kind": "QR"}).status_code == 302
    assert am.post(f"/app/identification/assets/{asset.pk}/panel/generate/", {"kind": "BARCODE"}).status_code == 302
    assert am.post(f"/app/identification/assets/{asset.pk}/panel/generate/", {"kind": "QR"}).status_code == 302  # flash error
    assert AssetIdentifier.objects.for_organization(q_["org"]).filter(asset=asset, is_active=True).count() == 2
    svg = am.get(f"/app/identification/assets/{asset.pk}/qr.svg")
    assert svg.status_code == 200 and svg["Content-Type"] == "image/svg+xml" and svg.content.startswith(b"<svg")
    assert svg["Cache-Control"] == "private, no-store"
    assert am.get(f"/app/identification/assets/{asset.pk}/qr.png").content[:4] == b"\x89PNG"
    assert am.get(f"/app/identification/assets/{asset.pk}/barcode.svg?download=1")["Content-Disposition"].startswith("attachment")
    assert am.get(f"/app/identification/assets/{asset.pk}/barcode.png").status_code == 404
    page = am.get(f"/app/identification/assets/{asset.pk}/label/").content.decode()
    assert "P3-PUMP" in page and "<svg" in page
    qr = AssetIdentifier.objects.for_organization(q_["org"]).get(asset=asset, kind="QR", is_active=True)
    am.post(f"/app/identification/assets/{asset.pk}/panel/replace/", {"identifier": str(qr.pk), "reason": "Faded"})
    qr.refresh_from_db()
    assert not qr.is_active
    am.post(f"/app/identification/assets/{asset.pk}/panel/revoke/", {"identifier": str(qr.pk), "reason": ""})
    assert AssetIdentifier.objects.for_organization(q_["org"]).filter(asset=asset, kind="QR", is_active=True).count() == 1


def test_ui_forbidden_and_cross_tenant(q_):
    theirs = idn.generate(q_["b_asset"], "QR", actor=q_["b_am"].user)
    tech, am = web(q_["tech"].user), web(q_["am"].user)
    asset = q_["asset"]
    assert tech.get(f"/app/identification/assets/{asset.pk}/panel/").status_code == 403
    assert tech.post(f"/app/identification/assets/{asset.pk}/panel/generate/", {"kind": "QR"}).status_code == 403
    assert not AssetIdentifier.objects.for_organization(q_["org"]).exists()
    for url in (f"/app/identification/assets/{q_['b_asset'].pk}/panel/", f"/app/identification/assets/{q_['b_asset'].pk}/label/",
                f"/app/identification/assets/{q_['b_asset'].pk}/qr.svg"):
        assert am.get(url).status_code == 404
    assert am.post(f"/app/identification/assets/{asset.pk}/panel/revoke/", {"identifier": str(theirs.pk), "reason": "x"}
                   ).status_code == 404
    theirs.refresh_from_db()
    assert theirs.is_active


def test_ui_scan_and_resolve_flow(q_):
    ident = gen(q_)
    tech = web(q_["tech"].user)
    assert tech.get("/app/identification/scan/").status_code == 200
    r = tech.post("/app/identification/scan/", {"token": f"https://anywhere.example/app/s/{ident.token}/"})
    assert r.status_code == 302 and r["Location"] == f"/app/s/{ident.token}/"
    page = tech.get(r["Location"])
    assert page.status_code == 200 and "P3-PUMP" in page.content.decode()
    assert tech.post("/app/identification/scan/", {"token": "!!"}).status_code == 400
    sent = tech.post(f"/app/s/{ident.token}/", {"title": "Vibration on pump", "severity": "HIGH", "description": "loud"})
    sr = ServiceRequest.objects.for_organization(q_["org"]).get()
    assert sent.status_code == 302 and sent["Location"] == f"/app/incidents/{sr.pk}/"
    assert ScanEvent.objects.for_organization(q_["org"]).filter(service_request=sr).count() == 1
    assert tech.post(f"/app/s/{ident.token}/", {"title": "", "severity": "LOW"}).status_code == 400
    assert ServiceRequest.objects.for_organization(q_["org"]).count() == 1


def test_ui_resolve_denials(q_):
    ident = gen(q_)
    theirs = idn.generate(q_["b_asset"], "QR", actor=q_["b_am"].user)
    assert Client().get(f"/app/s/{ident.token}/").status_code == 302  # login required, no asset information leaked
    tech, client = web(q_["tech"].user), web(q_["client"].user)
    assert tech.get(f"/app/s/{theirs.token}/").status_code == 404
    assert tech.get("/app/s/garbage-token-1234/").status_code == 404
    assert client.get(f"/app/s/{ident.token}/").status_code == 404
    assert "P3-PUMP" not in client.get(f"/app/s/{ident.token}/").content.decode()
    assert client.post(f"/app/s/{ident.token}/", {"title": "Hi there", "severity": "LOW"}).status_code == 404
    assert not ServiceRequest.objects.for_organization(q_["org"]).exists()
    idn.revoke(ident, reason="Replaced", actor=q_["am"].user)
    html = tech.get(f"/app/s/{ident.token}/").content.decode()
    assert "revoked" in html and "report-card" not in html
