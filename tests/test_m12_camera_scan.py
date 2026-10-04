"""M12 camera scanner: the scan page ships the real scanner (script, bundled decoder, markup, camera headers), and the
server side of a camera scan (``/app/s/<token>/?open=asset``) opens the asset only after the normal resolution:
authenticated, same organization, site access, not revoked; every scan is recorded once; failures never reveal
whether a label exists."""
import pytest
from django.contrib.staticfiles import finders
from django.test import Client

from apps.audit.models import AuditLog
from apps.identification import services as idn
from apps.identification.models import ScanEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def q_(p3, make_member, org_b, make_site, make_asset):
    am = make_member(p3["org"], "am@alpha.test", "asset_manager")
    b_am = make_member(org_b, "am@beta.test", "asset_manager")
    b_asset = make_asset(org_b, make_site(org_b, "B9"), "B-PUMP")
    return {**p3, "am": am, "b_am": b_am, "b_asset": b_asset, "org_b": org_b}


def web(user):
    c = Client()
    c.force_login(user)
    return c


def label(q, asset=None, kind="QR"):
    return idn.generate(asset or q["asset"], kind, actor=q["am"].user)


# --- the page ships a real scanner --------------------------------------------------------------------------------


def test_scan_page_contains_the_camera_scanner(q_):
    r = web(q_["tech"].user).get("/app/identification/scan/")
    html = r.content.decode()
    assert r.status_code == 200
    for needle in ('id="scan-video"', 'id="scan-viewport"', 'class="fx-scan-frame"', 'id="scan-retry"',
                   'id="scan-switch"', 'data-zxing-src="/static/lib/zxing.min.js"',
                   'data-resolve-url="/app/s/__TOKEN__/"', "js/qr_scan.js", 'id="scan-form"', 'id="scan-token"'):
        assert needle in html, needle
    assert "not available in this browser" not in html  # the old "fallback only" page is gone


def test_scanner_assets_exist_and_are_collectable():
    for path in ("js/qr_scan.js", "lib/zxing.min.js", "css/app.css"):
        assert finders.find(path), path
    js = open(finders.find("js/qr_scan.js"), encoding="utf-8").read()
    assert "getUserMedia" in js and "BarcodeDetector" in js and "ZXing" in js  # native + bundled fallback
    assert "facingMode" in js and "enumerateDevices" in js  # rear camera preference + camera switching
    zx = open(finders.find("lib/zxing.min.js"), encoding="utf-8").read()
    assert "MultiFormatReader" in zx and "sourceMappingURL" not in zx


def test_camera_is_allowed_for_our_pages_only_and_csp_stays_strict(q_):
    r = web(q_["tech"].user).get("/app/identification/scan/")
    assert "camera=(self)" in r["Permissions-Policy"]
    csp = r["Content-Security-Policy"]
    assert "script-src 'self' 'nonce-" in csp and "unsafe-eval" not in csp and "cdn" not in csp


# --- server side of a camera scan ---------------------------------------------------------------------------------


def test_camera_scan_opens_the_asset_and_records_one_scan(q_):
    ident = label(q_)
    c = web(q_["tech"].user)
    for _ in range(3):  # the browser may repeat the request: still one recorded scan
        r = c.get(f"/app/s/{ident.token}/?open=asset")
        assert r.status_code == 302 and r["Location"] == f"/app/assets/{q_['asset'].pk}/"
    assert ScanEvent.objects.for_organization(q_["org"]).filter(identifier=ident).count() == 1
    assert AuditLog.objects.filter(action="qr.scanned", organization=q_["org"]).count() == 1


def test_scanned_full_url_text_resolves_to_the_same_asset(q_):
    ident = label(q_)
    assert idn.extract_token(idn.scan_url(ident.token, "https://fieldops.example")) == ident.token
    r = web(q_["tech"].user).get(f"/app/s/{ident.token}/?open=asset")
    assert r["Location"].endswith(f"/app/assets/{q_['asset'].pk}/")


def test_camera_scan_denials_look_the_same_and_open_nothing(q_, make_member, make_scoped_member):
    ident = label(q_)
    other_site = label(q_, q_["asset2"])
    c = web(q_["tech"].user)
    unknown = c.get("/app/s/Zk3pQ9vLm2XcRt7YbN4HwA/?open=asset")
    # cross-tenant: the label of another organization
    foreign = idn.generate(q_["b_asset"], "QR", actor=q_["b_am"].user)
    cross = c.get(f"/app/s/{foreign.token}/?open=asset")
    # unauthorized: a user scoped to site 2 scans the label of an asset at site 1
    scoped = make_scoped_member(q_["org"], "scoped@alpha.test", "technician", [q_["site2"]])
    denied = web(scoped.user).get(f"/app/s/{ident.token}/?open=asset")
    assert {unknown.status_code, cross.status_code, denied.status_code} == {404}
    for r in (unknown, cross, denied):  # the same not-found page: nothing tells "no such label" from "not yours"
        assert "identification/not_found.html" in [t.name for t in r.templates]
        assert b"Boiler" not in r.content and q_["asset"].asset_tag.encode() not in r.content
    assert web(scoped.user).get(f"/app/s/{other_site.token}/?open=asset").status_code == 302
    assert not ScanEvent.objects.for_organization(q_["org"]).filter(scanned_by=scoped.user, identifier=ident).exists()
    assert AuditLog.objects.filter(action="qr.scan_unknown").count() >= 2
    assert AuditLog.objects.filter(action="qr.scan_denied", organization=q_["org"]).exists()


def test_revoked_label_is_not_opened_by_a_camera_scan(q_):
    ident = label(q_)
    idn.revoke(ident, reason="label damaged", actor=q_["am"].user)
    r = web(q_["tech"].user).get(f"/app/s/{ident.token}/?open=asset")
    assert r.status_code == 200 and b"revoked" in r.content.lower()  # shown as revoked, never redirected


def test_unauthenticated_camera_scan_goes_to_login(q_):
    ident = label(q_)
    r = Client().get(f"/app/s/{ident.token}/?open=asset")
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_plain_resolution_page_and_report_button_still_work(q_):
    ident = label(q_)
    c = web(q_["ops"].user)
    page = c.get(f"/app/s/{ident.token}/")
    assert page.status_code == 200 and b"Report a problem with this asset" in page.content
    detail = c.get(f"/app/assets/{q_['asset'].pk}/").content.decode()
    assert 'id="report-problem"' in detail and f"/app/incidents/new/?asset={q_['asset'].pk}" in detail
