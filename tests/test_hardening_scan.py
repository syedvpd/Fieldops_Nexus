"""M12 abuse protection: failed-scan rate limit and one-scan-one-event (a refresh is not another scan)."""
import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.identification import services as idn
from apps.identification.models import ScanEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def s_(p3, make_member):
    am = make_member(p3["org"], "am@scan.test", "asset_manager")
    ident = idn.generate(p3["asset"], "QR", actor=am.user)
    cache.clear()
    return {**p3, "am": am, "ident": ident}


def web(user):
    c = Client()
    c.force_login(user)
    return c


def api(user, org):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


def events(s):
    return ScanEvent.objects.for_organization(s["org"]).filter(identifier=s["ident"])


def test_refreshing_the_resolve_page_does_not_create_another_scan(s_):
    c = web(s_["tech"].user)
    url = f"/app/s/{s_['ident'].token}/"
    for _ in range(4):
        assert c.get(url).status_code == 200
    assert events(s_).count() == 1
    assert AuditLog.objects.filter(action="qr.scanned", organization=s_["org"]).count() == 1
    assert idn.resolve(s_["tech"].user, s_["ident"].token, s_["tech"]).outcome == "RESOLVED"
    assert events(s_).count() == 1  # API/service resolution inside the window reuses the event


def test_another_user_or_another_label_is_a_separate_scan(s_):
    web(s_["tech"].user).get(f"/app/s/{s_['ident'].token}/")
    web(s_["ops"].user).get(f"/app/s/{s_['ident'].token}/")
    assert events(s_).count() == 2
    bc = idn.generate(s_["asset"], "BARCODE", actor=s_["am"].user)
    web(s_["tech"].user).get(f"/app/s/{bc.token}/")
    assert ScanEvent.objects.for_organization(s_["org"]).count() == 3


def test_scan_after_the_window_is_a_new_scan(s_, settings):
    settings.SCAN_DEDUPE_SECONDS = 0
    c = web(s_["tech"].user)
    c.get(f"/app/s/{s_['ident'].token}/")
    c.get(f"/app/s/{s_['ident'].token}/")
    assert events(s_).count() == 2


def test_reporting_reuses_the_scan_and_each_request_gets_its_own_event(s_):
    c = web(s_["tech"].user)
    url = f"/app/s/{s_['ident'].token}/"
    c.get(url)
    assert c.post(url, {"title": "First problem", "severity": "LOW"}).status_code == 302
    assert events(s_).count() == 1 and events(s_).get().service_request is not None
    assert c.post(url, {"title": "Second problem", "severity": "LOW"}).status_code == 302
    linked = events(s_).filter(service_request__isnull=False)
    assert events(s_).count() == 2 and linked.count() == 2
    assert len({e.service_request_id for e in linked}) == 2  # one request per event


@override_settings(SCAN_FAIL_LIMIT=3, SCAN_FAIL_WINDOW_SECONDS=600)
def test_failed_scans_are_rate_limited_per_user(s_):
    tech = s_["tech"]
    for i in range(3):
        assert idn.resolve(tech.user, f"wrong-token-{i}-xxxxx", tech).outcome == "UNKNOWN"
    assert idn.throttled(tech.user)
    # even the CORRECT code is refused while throttled, and nothing is recorded for it
    res = idn.resolve(tech.user, s_["ident"].token, tech)
    assert res.outcome == "THROTTLED" and res.asset is None
    assert not events(s_).exists()
    for _ in range(5):
        idn.resolve(tech.user, "still-guessing-1234", tech)
    assert AuditLog.objects.filter(action="qr.scan_throttled", organization=s_["org"]).count() == 1  # once per window
    assert AuditLog.objects.filter(action="qr.scan_unknown", organization=s_["org"]).count() == 3  # no log flood
    # other users are not affected
    assert idn.resolve(s_["ops"].user, s_["ident"].token, s_["ops"]).outcome == "RESOLVED"


@override_settings(SCAN_FAIL_LIMIT=2)
def test_throttle_over_http_returns_429_and_recovers(s_):
    tech = s_["tech"]
    cl, a = web(tech.user), api(tech.user, s_["org"])
    assert cl.get("/app/s/nope-token-aaaa1/").status_code == 404
    assert a.post("/api/v1/scan/resolve/", {"token": "nope-token-bbbb2"}, format="json").status_code == 404
    assert cl.get(f"/app/s/{s_['ident'].token}/").status_code == 429
    assert a.post("/api/v1/scan/resolve/", {"token": s_["ident"].token}, format="json").status_code == 429
    assert a.post("/api/v1/scan/report/", {"token": s_["ident"].token, "title": "Blocked"}, format="json"
                  ).status_code == 429
    assert "Too many failed scans" in cl.get(f"/app/s/{s_['ident'].token}/").content.decode()
    cache.clear()  # the window passing
    assert cl.get(f"/app/s/{s_['ident'].token}/").status_code == 200


@override_settings(SCAN_FAIL_LIMIT=2)
def test_valid_scans_never_trip_the_limit(s_):
    c = web(s_["tech"].user)
    for _ in range(10):
        assert c.get(f"/app/s/{s_['ident'].token}/").status_code == 200
    assert not idn.throttled(s_["tech"].user)
