"""M02 Asset Registry: lifecycle state machine, services, API, documents, meters, RBAC, tenant isolation."""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets import services
from apps.assets.models import Asset, AssetLocationHistory, AssetStatusHistory
from apps.assets.workflow import ASSET_STATUS, STATES
from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, InvalidTransition, ValidationFailed

pytestmark = pytest.mark.django_db

ALLOWED = {
    ("ACTIVE", "start_maintenance"): "UNDER_MAINTENANCE",
    ("UNDER_MAINTENANCE", "complete_maintenance"): "ACTIVE",
    ("UNDER_MAINTENANCE", "mark_out_of_service"): "OUT_OF_SERVICE",
    ("OUT_OF_SERVICE", "return_to_service"): "ACTIVE",
    ("OUT_OF_SERVICE", "retire"): "RETIRED",
    ("OUT_OF_SERVICE", "dispose"): "DISPOSED",
}
ACTIONS = sorted({a for _, a in ALLOWED})


def actions(org):
    return list(AuditLog.objects.filter(organization=org).values_list("action", flat=True))


def png():
    return SimpleUploadedFile("manual.txt", b"Pump manual v1\n", content_type="text/plain")


# --- state machine -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("action", ACTIONS)
def test_state_machine_matrix(state, action):
    class Obj:
        status = state

    if (state, action) in ALLOWED:
        assert ASSET_STATUS.apply(Obj, action) == (state, ALLOWED[(state, action)])
    else:
        with pytest.raises(InvalidTransition):
            ASSET_STATUS.apply(Obj, action)


def test_terminal_states_have_no_exits():
    assert ASSET_STATUS.available("RETIRED") == [] and ASSET_STATUS.available("DISPOSED") == []


# --- services ------------------------------------------------------------------------------------------------


def test_create_asset_writes_history_and_audit(org_a, site_a1, make_zone, make_category, owner_a):
    zone = make_zone(site_a1, "Hall")
    asset = services.create_asset(org_a, site=site_a1, zone=zone, category=make_category(org_a), actor=owner_a,
                                  asset_tag="PMP-001", name="Feed pump", serial_number="S1", manufacturer="Acme")
    assert asset.status == "ACTIVE" and asset.organization_id == org_a.pk
    h = AssetStatusHistory.objects.get(asset=asset)
    assert (h.from_status, h.to_status, h.action, h.changed_by_id) == ("", "ACTIVE", "register", owner_a.pk)
    assert AssetLocationHistory.objects.filter(asset=asset, to_zone=zone).count() == 1
    assert "asset.created" in actions(org_a)


def test_uniqueness_tag_and_serial_rules(org_a, org_b, site_a1, site_b1, make_asset):
    make_asset(org_a, site_a1, "T-1", manufacturer="Acme", serial_number="SN1")
    with pytest.raises(Conflict) as exc:
        make_asset(org_a, site_a1, "t-1")
    assert exc.value.code == "duplicate_asset_tag"
    with pytest.raises(Conflict) as exc:
        make_asset(org_a, site_a1, "T-2", manufacturer="ACME", serial_number="sn1")
    assert exc.value.code == "duplicate_serial_number"
    make_asset(org_a, site_a1, "T-3", manufacturer="Other", serial_number="SN1")  # serials are per manufacturer
    make_asset(org_a, site_a1, "T-4")  # blank serials never collide
    make_asset(org_a, site_a1, "T-5")
    make_asset(org_b, site_b1, "T-1", manufacturer="Acme", serial_number="SN1")  # other tenant: allowed


def test_database_constraints_on_asset(org_a, site_a1, make_asset, make_category):
    make_asset(org_a, site_a1, "C-1")
    cat = make_category(org_a)
    with pytest.raises(IntegrityError), transaction.atomic():
        Asset(organization=org_a, site=site_a1, category=cat, asset_tag="c-1", name="x").save()
    with pytest.raises(IntegrityError), transaction.atomic():
        Asset(organization=org_a, site=site_a1, category=cat, asset_tag="C-2", name="x",
              purchase_date=datetime.date(2026, 2, 1), commission_date=datetime.date(2026, 1, 1)).save()


def test_dates_validated(org_a, site_a1, make_asset):
    with pytest.raises(ValidationFailed):
        make_asset(org_a, site_a1, "D-1", purchase_date=datetime.date(2026, 2, 1),
                   commission_date=datetime.date(2026, 1, 1))


def test_cross_tenant_references_rejected(org_a, org_b, site_a1, site_b1, make_zone, make_category, make_member):
    zone_b = make_zone(site_b1, "Z")
    cat_b = make_category(org_b)
    owner_b = make_member(org_b, "o@beta.test", "technician")
    cat_a = make_category(org_a)
    with pytest.raises(ValidationFailed) as exc:
        services.create_asset(org_a, site=site_b1, category=cat_a, actor=None, asset_tag="X-1", name="x")
    assert exc.value.code == "cross_tenant_site"
    with pytest.raises(ValidationFailed) as exc:
        services.create_asset(org_a, site=site_a1, zone=zone_b, category=cat_a, actor=None, asset_tag="X-2", name="x")
    assert exc.value.code == "cross_tenant_zone"
    with pytest.raises(ValidationFailed) as exc:
        services.create_asset(org_a, site=site_a1, category=cat_b, actor=None, asset_tag="X-3", name="x")
    assert exc.value.code == "cross_tenant_category"
    with pytest.raises(ValidationFailed) as exc:
        services.create_asset(org_a, site=site_a1, category=cat_a, owner=owner_b, actor=None, asset_tag="X-4",
                              name="x")
    assert exc.value.code == "cross_tenant_owner"
    assert not Asset.objects.unscoped().filter(asset_tag__startswith="X-").exists()


def test_zone_must_belong_to_site_and_be_active(org_a, site_a1, site_a2, make_zone, make_category, owner_a):
    from apps.sites import services as site_services

    z2 = make_zone(site_a2, "Elsewhere")
    with pytest.raises(ValidationFailed) as exc:
        services.create_asset(org_a, site=site_a1, zone=z2, category=make_category(org_a), actor=None,
                              asset_tag="Z-1", name="x")
    assert exc.value.code == "zone_site_mismatch"
    z1 = make_zone(site_a1, "Idle")
    site_services.deactivate_zone(z1, reason="x", actor=owner_a)
    with pytest.raises(Conflict):
        services.create_asset(org_a, site=site_a1, zone=z1, category=make_category(org_a), actor=None,
                              asset_tag="Z-2", name="x")


def test_full_lifecycle_records_history_and_audit(org_a, site_a1, make_asset, owner_a):
    asset = make_asset(org_a, site_a1, "L-1")
    for action in ("start_maintenance", "mark_out_of_service", "return_to_service", "start_maintenance",
                   "complete_maintenance", "start_maintenance", "mark_out_of_service", "dispose"):
        services.change_status(asset, action=action, reason=f"because {action}", actor=owner_a)
    asset.refresh_from_db()
    assert asset.status == "DISPOSED"
    rows = list(AssetStatusHistory.objects.filter(asset=asset).order_by("created_at", "id"))
    assert [r.to_status for r in rows][-1] == "DISPOSED" and len(rows) == 9
    assert all(r.changed_by_id == owner_a.pk for r in rows[1:])
    assert actions(org_a).count("asset.status_changed") == 8


def test_invalid_transition_and_reason_required(org_a, site_a1, make_asset, owner_a):
    asset = make_asset(org_a, site_a1, "I-1")
    with pytest.raises(InvalidTransition):
        services.change_status(asset, action="retire", reason="nope", actor=owner_a)
    with pytest.raises(ValidationFailed):
        services.change_status(asset, action="start_maintenance", reason=" ", actor=owner_a)
    asset.refresh_from_db()
    assert asset.status == "ACTIVE" and AssetStatusHistory.objects.filter(asset=asset).count() == 1


def test_history_is_append_only(org_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "H-1")
    row = AssetStatusHistory.objects.get(asset=asset)
    row.reason = "tampered"
    with pytest.raises(ValueError):
        row.save()
    with pytest.raises(ValueError):
        row.delete()


def test_terminal_assets_are_read_only(org_a, site_a1, make_asset, owner_a):
    asset = make_asset(org_a, site_a1, "R-1")
    for a in ("start_maintenance", "mark_out_of_service", "retire"):
        services.change_status(asset, action=a, reason="end of life", actor=owner_a)
    with pytest.raises(Conflict) as exc:
        services.update_asset(asset, actor=owner_a, name="renamed")
    assert exc.value.code == "asset_terminal"
    with pytest.raises(Conflict):
        services.create_meter(asset, name="Hours", unit="h", actor=owner_a)


def test_update_and_move_tracks_location_history(org_a, site_a1, site_a2, make_zone, make_asset, owner_a):
    z = make_zone(site_a1, "Hall")
    asset = make_asset(org_a, site_a1, "M-1", zone=z)
    services.update_asset(asset, actor=owner_a, name="New name", site=site_a2, reason="Relocated")
    asset.refresh_from_db()
    assert asset.name == "New name" and asset.site_id == site_a2.pk and asset.zone_id is None
    h = AssetLocationHistory.objects.filter(asset=asset).order_by("-created_at").first()
    assert (h.from_site_id, h.from_zone_id, h.to_site_id, h.reason) == (site_a1.pk, z.pk, site_a2.pk, "Relocated")
    assert {"asset.updated", "asset.location_changed"} <= set(actions(org_a))


def test_categories(org_a, org_b, make_category, owner_a):
    cat = make_category(org_a, "Pump")
    with pytest.raises(Conflict):
        services.create_category(org_a, name="pump", actor=owner_a)
    make_category(org_b, "Pump")
    services.update_category(cat, actor=owner_a, is_active=False)
    with pytest.raises(Conflict):
        services.create_asset(org_a, site=None, category=cat, actor=None, asset_tag="K-1", name="x")


# --- meters --------------------------------------------------------------------------------------------------


def test_meter_readings_are_monotonic(org_a, site_a1, make_asset, owner_a):
    asset = make_asset(org_a, site_a1, "MT-1")
    meter = services.create_meter(asset, name="Run hours", unit="h", actor=owner_a)
    t0 = timezone.now() - datetime.timedelta(hours=3)
    services.record_reading(meter, value=Decimal("100"), read_at=t0, actor=owner_a)
    services.record_reading(meter, value=Decimal("100"), read_at=t0 + datetime.timedelta(hours=1), actor=owner_a)
    services.record_reading(meter, value="150.5", read_at=t0 + datetime.timedelta(hours=2), actor=owner_a)
    with pytest.raises(ValidationFailed) as exc:
        services.record_reading(meter, value=120, actor=owner_a)
    assert exc.value.code == "meter_not_monotonic"
    with pytest.raises(ValidationFailed) as exc:
        services.record_reading(meter, value=200, read_at=t0, actor=owner_a)
    assert exc.value.code == "meter_time_not_monotonic"
    with pytest.raises(ValidationFailed) as exc:
        services.record_reading(meter, value=200, read_at=timezone.now() + datetime.timedelta(days=1), actor=owner_a)
    assert exc.value.code == "reading_in_future"
    for bad in (-1, "abc", "NaN", "Infinity"):
        with pytest.raises(ValidationFailed):
            services.record_reading(meter, value=bad, actor=owner_a)
    assert meter.readings.count() == 3
    assert "asset.meter_reading_recorded" in actions(org_a)


def test_meter_rules(org_a, site_a1, make_asset, owner_a):
    asset = make_asset(org_a, site_a1, "MT-2")
    meter = services.create_meter(asset, name="Odometer", unit="km", actor=owner_a)
    with pytest.raises(Conflict):
        services.create_meter(asset, name="odometer", unit="km", actor=owner_a)
    services.set_meter_active(meter, active=False, actor=owner_a)
    with pytest.raises(Conflict) as exc:
        services.record_reading(meter, value=1, actor=owner_a)
    assert exc.value.code == "meter_inactive"


# --- API: CRUD, filters, status ----------------------------------------------------------------------------------


def asset_payload(site, category, **over):
    return {"asset_tag": "PMP-100", "name": "Booster pump", "category": str(category.pk), "site": str(site.pk),
            "manufacturer": "Acme", "model": "X1", "serial_number": "SN-9", **over}


def test_api_create_retrieve_update_asset(as_user, owner_a, org_a, site_a1, make_zone, make_category):
    zone = make_zone(site_a1, "Hall")
    cat = make_category(org_a)
    c = as_user(owner_a, org_a)
    r = c.post("/api/v1/assets/", asset_payload(site_a1, cat, zone=str(zone.pk)), format="json")
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["status"] == "ACTIVE" and body["zone_name"] == "Hall" and body["site_code"] == "A1"
    assert "start_maintenance" in body["available_actions"]
    aid = body["id"]
    assert Asset.objects.unscoped().get(pk=aid).serial_number == "SN-9"
    r = c.patch(f"/api/v1/assets/{aid}/", {"name": "Booster pump 2", "warranty_ref": "WR-1"}, format="json")
    assert r.status_code == 200 and r.json()["warranty_ref"] == "WR-1"
    assert c.get(f"/api/v1/assets/{aid}/").json()["name"] == "Booster pump 2"
    assert {"asset.created", "asset.updated"} <= set(actions(org_a))


def test_api_validation_and_conflicts(as_user, owner_a, org_a, site_a1, make_category, make_asset):
    cat = make_category(org_a)
    c = as_user(owner_a, org_a)
    assert c.post("/api/v1/assets/", {"name": "x"}, format="json").status_code == 400
    make_asset(org_a, site_a1, "DUP-1")
    r = c.post("/api/v1/assets/", asset_payload(site_a1, cat, asset_tag="dup-1"), format="json")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_asset_tag"
    r = c.post("/api/v1/assets/", asset_payload(site_a1, cat, purchase_date="2026-02-01",
                                                commission_date="2026-01-01"), format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_dates"


def test_status_cannot_be_patched(as_user, owner_a, org_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "NP-1")
    r = as_user(owner_a, org_a).patch(f"/api/v1/assets/{asset.pk}/", {"status": "RETIRED"}, format="json")
    assert r.status_code == 400
    asset.refresh_from_db()
    assert asset.status == "ACTIVE"


def test_api_transition_history_and_invalid_state(as_user, owner_a, org_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "TR-1")
    c = as_user(owner_a, org_a)
    url = f"/api/v1/assets/{asset.pk}/transition/"
    assert c.post(url, {"action": "retire", "reason": "skip"}, format="json").status_code == 409
    assert c.post(url, {"action": "start_maintenance"}, format="json").status_code == 400  # reason required
    assert c.post(url, {"action": "fly", "reason": "x"}, format="json").status_code == 400
    r = c.post(url, {"action": "start_maintenance", "reason": "Scheduled service"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "UNDER_MAINTENANCE"
    hist = c.get(f"/api/v1/assets/{asset.pk}/history/").json()
    assert hist["count"] == 2 and hist["results"][0]["to_status"] == "UNDER_MAINTENANCE"
    assert hist["results"][0]["reason"] == "Scheduled service"
    assert c.get(f"/api/v1/assets/{asset.pk}/location-history/").json()["count"] == 1


def test_api_move_between_sites_via_patch(as_user, owner_a, org_a, site_a1, site_a2, make_asset):
    asset = make_asset(org_a, site_a1, "MV-1")
    c = as_user(owner_a, org_a)
    r = c.patch(f"/api/v1/assets/{asset.pk}/", {"site": str(site_a2.pk), "reason": "Transfer"}, format="json")
    assert r.status_code == 200 and r.json()["site_code"] == "A2"
    assert c.get(f"/api/v1/assets/{asset.pk}/location-history/").json()["count"] == 2


def test_api_list_filters_search_ordering_pagination(as_user, owner_a, org_a, site_a1, site_a2, make_asset,
                                                     make_category, make_zone):
    pumps, fans = make_category(org_a, "Pump"), make_category(org_a, "Fan")
    z = make_zone(site_a1, "Hall")
    make_asset(org_a, site_a1, "A-1", category=pumps, zone=z, model="Alpha")
    make_asset(org_a, site_a1, "A-2", category=fans, serial_number="XYZ-77", manufacturer="M")
    make_asset(org_a, site_a2, "A-3", category=pumps)
    a4 = make_asset(org_a, site_a2, "A-4", category=pumps)
    services.change_status(a4, action="start_maintenance", reason="service", actor=owner_a)
    c = as_user(owner_a, org_a)
    assert c.get("/api/v1/assets/").json()["count"] == 4
    assert c.get(f"/api/v1/assets/?site={site_a2.pk}").json()["count"] == 2
    assert c.get(f"/api/v1/assets/?category={fans.pk}").json()["count"] == 1
    assert c.get(f"/api/v1/assets/?zone={z.pk}").json()["count"] == 1
    assert c.get("/api/v1/assets/?status=UNDER_MAINTENANCE").json()["count"] == 1
    assert c.get("/api/v1/assets/?status=BOGUS").json()["count"] == 0
    assert c.get("/api/v1/assets/?q=xyz-77").json()["count"] == 1
    assert c.get("/api/v1/assets/?q=alpha").json()["count"] == 1
    page = c.get("/api/v1/assets/?page_size=2&ordering=-asset_tag").json()
    assert [a["asset_tag"] for a in page["results"]] == ["A-4", "A-3"] and page["next"]
    assert c.get("/api/v1/assets/?site=nope").json()["count"] == 0


def test_asset_list_query_count_is_constant(as_user, owner_a, org_a, site_a1, make_asset, django_assert_max_num_queries):
    for i in range(12):
        make_asset(org_a, site_a1, f"Q-{i}")
    c = as_user(owner_a, org_a)
    with django_assert_max_num_queries(14):
        assert c.get("/api/v1/assets/").json()["count"] == 12


def test_api_rbac_matrix(as_user, api, org_a, owner_a, tech_a, make_member, site_a1, make_asset, make_category):
    asset = make_asset(org_a, site_a1, "RB-1")
    cat = make_category(org_a)
    assert api.get("/api/v1/assets/").status_code == 401
    assert api.post(f"/api/v1/assets/{asset.pk}/transition/", {}, format="json").status_code == 401
    tech = as_user(tech_a, org_a)  # asset.view + asset.meter.record only
    assert tech.get("/api/v1/assets/").status_code == 200
    assert tech.get(f"/api/v1/assets/{asset.pk}/").status_code == 200
    assert tech.post("/api/v1/assets/", asset_payload(site_a1, cat), format="json").status_code == 403
    assert tech.patch(f"/api/v1/assets/{asset.pk}/", {"name": "x"}, format="json").status_code == 403
    assert tech.post(f"/api/v1/assets/{asset.pk}/transition/", {"action": "start_maintenance", "reason": "x"},
                     format="json").status_code == 403
    assert tech.get(f"/api/v1/assets/{asset.pk}/history/").status_code == 403
    assert tech.post(f"/api/v1/assets/{asset.pk}/documents/", {"file": png()}, format="multipart").status_code == 403
    assert tech.post("/api/v1/asset-categories/", {"name": "New"}, format="json").status_code == 403
    assert tech.post("/api/v1/meters/", {"asset": str(asset.pk), "name": "H", "unit": "h"},
                     format="json").status_code == 403
    asset.refresh_from_db()
    assert asset.status == "ACTIVE" and asset.name == "Asset RB-1"
    # roles that exist only to read
    make_member(org_a, "aud@alpha.test", "auditor")
    from tests.conftest import User

    aud = as_user(User.objects.get(email="aud@alpha.test"), org_a)
    assert aud.get(f"/api/v1/assets/{asset.pk}/history/").status_code == 200
    assert aud.post(f"/api/v1/assets/{asset.pk}/transition/", {"action": "start_maintenance", "reason": "x"},
                    format="json").status_code == 403


def test_api_categories(as_user, owner_a, org_a):
    c = as_user(owner_a, org_a)
    r = c.post("/api/v1/asset-categories/", {"name": "Generator"}, format="json")
    assert r.status_code == 201
    assert c.post("/api/v1/asset-categories/", {"name": "generator"}, format="json").status_code == 409
    cid = r.json()["id"]
    assert c.patch(f"/api/v1/asset-categories/{cid}/", {"is_active": False}, format="json").json()["is_active"] is False
    assert c.get("/api/v1/asset-categories/").json()["count"] == 1


# --- API: documents & meters -------------------------------------------------------------------------------------


def test_document_upload_and_secure_download(as_user, client, owner_a, tech_a, org_a, org_b, owner_b, site_a1,
                                             make_asset):
    asset = make_asset(org_a, site_a1, "DOC-1")
    c = as_user(owner_a, org_a)
    r = c.post(f"/api/v1/assets/{asset.pk}/documents/", {"file": png(), "title": "Manual", "doc_type": "MANUAL"},
               format="multipart")
    assert r.status_code == 201, r.content
    doc = r.json()
    assert doc["title"] == "Manual" and doc["original_name"] == "manual.txt"
    assert c.get(f"/api/v1/assets/{asset.pk}/documents/").json()["count"] == 1
    assert "asset.document_added" in actions(org_a)
    url = doc["download_url"]
    client.force_login(tech_a)  # asset.view holder may download
    r = client.get(url)
    assert r.status_code == 200 and b"Pump manual" in b"".join(r.streaming_content)
    assert r["Content-Disposition"].startswith("attachment")
    client.logout()
    assert client.get(url).status_code == 302  # anonymous -> login
    client.force_login(owner_b)  # another tenant: the attachment does not exist for them
    assert client.get(url).status_code == 404


def test_document_rejects_bad_files(as_user, owner_a, org_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "DOC-2")
    c = as_user(owner_a, org_a)
    bad = SimpleUploadedFile("evil.exe", b"MZ\x90\x00", content_type="application/octet-stream")
    r = c.post(f"/api/v1/assets/{asset.pk}/documents/", {"file": bad}, format="multipart")
    assert r.status_code == 400
    assert not asset.documents.exists()
    r = c.post(f"/api/v1/assets/{asset.pk}/documents/", {"title": "no file"}, format="multipart")
    assert r.status_code == 400


def test_api_meters_and_readings(as_user, owner_a, tech_a, org_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "API-M1")
    c = as_user(owner_a, org_a)
    r = c.post("/api/v1/meters/", {"asset": str(asset.pk), "name": "Run hours", "unit": "h"}, format="json")
    assert r.status_code == 201, r.content
    mid = r.json()["id"]
    assert c.post("/api/v1/meters/", {"asset": str(asset.pk), "name": "run hours", "unit": "h"},
                  format="json").status_code == 409
    tech = as_user(tech_a, org_a)  # technicians record readings
    assert tech.post(f"/api/v1/meters/{mid}/readings/", {"value": "10.5"}, format="json").status_code == 201
    assert tech.post(f"/api/v1/meters/{mid}/readings/", {"value": "9"}, format="json").status_code == 400
    assert tech.post(f"/api/v1/meters/{mid}/readings/", {"value": "-1"}, format="json").status_code == 400
    assert tech.post(f"/api/v1/meters/{mid}/readings/", {}, format="json").status_code == 400
    assert tech.post(f"/api/v1/meters/{mid}/deactivate/").status_code == 403
    listing = c.get(f"/api/v1/meters/?asset={asset.pk}").json()
    assert listing["count"] == 1 and Decimal(listing["results"][0]["last_value"]) == Decimal("10.5")
    readings = c.get(f"/api/v1/meters/{mid}/readings/").json()
    assert readings["count"] == 1 and readings["results"][0]["recorded_by"] == "tech@alpha.test"


# --- tenant isolation / IDOR ---------------------------------------------------------------------------------------


def test_cross_tenant_idor_for_every_asset_route(as_user, owner_a, org_a, org_b, owner_b, site_b1, make_asset):
    foreign = make_asset(org_b, site_b1, "FOR-1")
    child = make_asset(org_b, site_b1, "FOR-2")
    from apps.assets import hierarchy

    link = hierarchy.add_component(foreign, child, actor=owner_b)
    meter = services.create_meter(foreign, name="Hours", unit="h", actor=owner_b)
    c = as_user(owner_a, org_a)
    for url in (f"/api/v1/assets/{foreign.pk}/", f"/api/v1/assets/{foreign.pk}/history/",
                f"/api/v1/assets/{foreign.pk}/location-history/", f"/api/v1/assets/{foreign.pk}/documents/",
                f"/api/v1/assets/{foreign.pk}/tree/", f"/api/v1/assets/{foreign.pk}/validate/",
                f"/api/v1/assets/{foreign.pk}/components/", f"/api/v1/meters/{meter.pk}/",
                f"/api/v1/meters/{meter.pk}/readings/", f"/api/v1/asset-components/{link.pk}/"):
        assert c.get(url).status_code == 404, url
    assert c.patch(f"/api/v1/assets/{foreign.pk}/", {"name": "pwn"}, format="json").status_code == 404
    assert c.post(f"/api/v1/assets/{foreign.pk}/transition/", {"action": "start_maintenance", "reason": "x"},
                  format="json").status_code == 404
    assert c.post(f"/api/v1/assets/{foreign.pk}/documents/", {"file": png()}, format="multipart").status_code == 404
    assert c.post(f"/api/v1/meters/{meter.pk}/readings/", {"value": 5}, format="json").status_code == 404
    assert c.post("/api/v1/meters/", {"asset": str(foreign.pk), "name": "x", "unit": "h"},
                  format="json").status_code == 404
    assert c.delete(f"/api/v1/asset-components/{link.pk}/").status_code == 404
    foreign.refresh_from_db()
    assert foreign.status == "ACTIVE" and foreign.name == "Asset FOR-1"
    for url in ("/api/v1/assets/", "/api/v1/meters/", "/api/v1/asset-components/"):
        assert c.get(url).json()["count"] == 0, url


def test_cross_tenant_references_via_api_are_not_found(as_user, owner_a, org_a, org_b, site_a1, site_b1, make_zone,
                                                      make_category):
    zone_b = make_zone(site_b1, "Z")
    cat_b = make_category(org_b)
    cat_a = make_category(org_a)
    c = as_user(owner_a, org_a)
    assert c.post("/api/v1/assets/", asset_payload(site_b1, cat_a), format="json").status_code == 404
    assert c.post("/api/v1/assets/", asset_payload(site_a1, cat_a, zone=str(zone_b.pk)),
                  format="json").status_code == 404
    assert c.post("/api/v1/assets/", asset_payload(site_a1, cat_b), format="json").status_code == 404
    assert not Asset.objects.unscoped().filter(asset_tag="PMP-100").exists()


def test_api_change_log_shows_before_after(as_user, owner_a, tech_a, org_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "CL-1")
    c = as_user(owner_a, org_a)
    c.patch(f"/api/v1/assets/{asset.pk}/", {"name": "Renamed", "warranty_ref": "W-1"}, format="json")
    c.post(f"/api/v1/assets/{asset.pk}/transition/", {"action": "start_maintenance", "reason": "svc"}, format="json")
    data = c.get(f"/api/v1/assets/{asset.pk}/changes/").json()
    by_action = {e["action"]: e for e in data["results"]}
    assert {"asset.created", "asset.updated", "asset.status_changed"} <= set(by_action)
    fields = {ch["field"]: ch for ch in by_action["asset.updated"]["changes"]}
    assert fields["name"]["old"] == "Asset CL-1" and fields["name"]["new"] == "Renamed"
    assert by_action["asset.status_changed"]["changes"][0] == {"field": "status", "old": "ACTIVE",
                                                                 "new": "UNDER_MAINTENANCE"}
    assert as_user(tech_a, org_a).get(f"/api/v1/assets/{asset.pk}/changes/").status_code == 403
