"""M02 per-category custom attributes: definitions, value validation, UI (reload + create + edit + detail), API."""
import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.assets import attributes as attrs
from apps.assets import services as asset_services
from apps.assets.models import Asset
from apps.audit.models import AuditLog
from apps.core.exceptions import ValidationFailed

pytestmark = pytest.mark.django_db


@pytest.fixture
def p3(p3, make_member):
    """Phase 3 organization where ``ops`` is an asset manager (owns the registry, documents and hierarchy)."""
    return {**p3, "ops": make_member(p3["org"], "am@alpha.test", "asset_manager")}

DEFS = "Voltage | number | required\nInstalled on | date\nPhase | choice | | single, three\nNotes"


def web(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def motors(p3):
    return asset_services.create_category(p3["org"], name="Motors", attribute_definitions=attrs.parse_text(DEFS),
                                          actor=p3["ops"].user)


def test_definition_text_round_trip_and_validation():
    defs = attrs.parse_text(DEFS)
    assert [d["key"] for d in defs] == ["voltage", "installed_on", "phase", "notes"]
    assert defs[0]["required"] and defs[2]["choices"] == ["single", "three"]
    assert attrs.parse_text(attrs.to_text(defs)) == defs
    for bad in ("A | colour", "A\nA", "Phase | choice | | onlyone", "|||", "\n".join(f"A{i}" for i in range(21))):
        with pytest.raises(ValidationFailed):
            attrs.parse_text(bad)


def test_values_are_validated_and_normalized(motors):
    defs = motors.attribute_definitions
    ok = attrs.clean_values(defs, {"voltage": "230.50", "installed_on": "2026-01-02", "phase": "THREE"})
    assert ok == {"voltage": "230.50", "installed_on": "2026-01-02", "phase": "three"}
    for bad in ({}, {"voltage": "high"}, {"voltage": "5", "installed_on": "02/01/2026"},
                {"voltage": "5", "phase": "dual"}, {"voltage": "5", "colour": "red"}, {"voltage": "NaN"}):
        with pytest.raises(ValidationFailed):
            attrs.clean_values(defs, bad)


def test_service_stores_attributes_audits_and_resets_on_category_change(p3, motors):
    a = asset_services.create_asset(p3["org"], site=p3["site"], category=motors, actor=p3["ops"].user,
                                    asset_tag="MOT-1", name="Pump motor", attributes={"voltage": "400"})
    assert a.attributes == {"voltage": "400"}
    row = AuditLog.objects.filter(action="asset.created", target_id=str(a.pk)).first()
    assert row.after["attributes"] == {"voltage": "400"}
    a = asset_services.update_asset(a, actor=p3["ops"].user, attributes={"voltage": "415", "phase": "three"})
    assert a.attributes == {"voltage": "415", "phase": "three"}
    assert AuditLog.objects.filter(action="asset.updated", target_id=str(a.pk)).exists()
    plain = p3["asset"].category
    a = asset_services.update_asset(a, actor=p3["ops"].user, category=plain)
    assert a.attributes == {}  # attributes of the old category do not carry over
    with pytest.raises(ValidationFailed):
        asset_services.create_asset(p3["org"], site=p3["site"], category=motors, actor=p3["ops"].user,
                                    asset_tag="MOT-2", name="No voltage")


def test_ui_create_with_category_attributes(p3, motors):
    c = web(p3["ops"].user)
    page = c.get(f"/app/assets/new/?category={motors.pk}&name=Fan").content.decode()
    assert 'name="attr_voltage"' in page and 'name="attr_installed_on"' in page and 'value="Fan"' in page
    assert "data-category-reload" in page
    data = {"asset_tag": "MOT-UI", "name": "UI motor", "category": str(motors.pk), "site": str(p3["site"].pk),
            "attr_voltage": "230", "attr_installed_on": "2026-02-03", "attr_phase": "single", "attr_notes": "spare"}
    r = c.post("/app/assets/new/", data)
    assert r.status_code == 302
    a = Asset.objects.for_organization(p3["org"]).get(asset_tag="MOT-UI")
    assert a.attributes == {"voltage": "230", "installed_on": "2026-02-03", "phase": "single", "notes": "spare"}
    detail = c.get(f"/app/assets/{a.pk}/").content.decode()
    assert 'id="custom-attributes"' in detail and "Voltage" in detail and "230" in detail
    bad = c.post("/app/assets/new/", {**data, "asset_tag": "MOT-BAD", "attr_voltage": ""})
    assert bad.status_code == 400 and not Asset.objects.filter(asset_tag="MOT-BAD").exists()


def test_ui_edit_changes_attributes(p3, motors):
    a = asset_services.create_asset(p3["org"], site=p3["site"], category=motors, actor=p3["ops"].user,
                                    asset_tag="MOT-E", name="Edit me", attributes={"voltage": "100"})
    c = web(p3["ops"].user)
    assert 'value="100"' in c.get(f"/app/assets/{a.pk}/edit/").content.decode()
    data = {"asset_tag": "MOT-E", "name": "Edit me", "category": str(motors.pk), "site": str(p3["site"].pk),
            "attr_voltage": "110"}
    assert c.post(f"/app/assets/{a.pk}/edit/", data).status_code == 302
    a.refresh_from_db()
    assert a.attributes == {"voltage": "110"}


def test_category_screen_saves_definitions(p3):
    c = web(p3["ops"].user)
    r = c.post("/app/assets/categories/", {"name": "Vehicles", "description": "", "is_active": "on",
                                            "attribute_text": "Plate | text | required\nFuel | choice | | diesel, petrol"})
    assert r.status_code == 302
    cat = asset_services.AssetCategory.objects.for_organization(p3["org"]).get(name="Vehicles")
    assert [d["key"] for d in cat.attribute_definitions] == ["plate", "fuel"]
    c.post("/app/assets/categories/", {"category": str(cat.pk), "name": "Vehicles", "description": "",
                                        "is_active": "on", "attribute_text": "Plate | text | required"})
    cat.refresh_from_db()
    assert [d["key"] for d in cat.attribute_definitions] == ["plate"]
    c.post("/app/assets/categories/", {"name": "Broken", "attribute_text": "X | colour"})
    assert not asset_services.AssetCategory.objects.filter(name="Broken").exists()


def test_api_category_and_asset_attributes_and_tenant(p3, motors, org_b, make_member):
    api = APIClient()
    api.force_authenticate(user=p3["ops"].user)
    api.credentials(HTTP_X_ORGANIZATION=p3["org"].slug)
    body = {"asset_tag": "MOT-API", "name": "API motor", "category": str(motors.pk), "site": str(p3["site"].pk),
            "attributes": {"voltage": "12"}}
    r = api.post("/api/v1/assets/", body, format="json")
    assert r.status_code == 201 and r.json()["attributes"] == {"voltage": "12"}
    bad = api.post("/api/v1/assets/", {**body, "asset_tag": "MOT-API2", "attributes": {"voltage": "x"}}, format="json")
    assert bad.status_code == 400
    r = api.patch(f"/api/v1/assets/{r.json()['id']}/", {"attributes": {"voltage": "24", "phase": "single"}},
                  format="json")
    assert r.status_code == 200 and r.json()["attributes"]["phase"] == "single"
    r = api.patch(f"/api/v1/asset-categories/{motors.pk}/",
                  {"attribute_definitions": [{"label": "Voltage", "type": "number", "required": True}]},
                  format="json")
    assert r.status_code == 200 and r.json()["attribute_definitions"][0]["key"] == "voltage"
    other = APIClient()
    stranger = make_member(org_b, "am@beta.test", "asset_manager")
    other.force_authenticate(user=stranger.user)
    other.credentials(HTTP_X_ORGANIZATION=org_b.slug)
    assert other.patch(f"/api/v1/asset-categories/{motors.pk}/", {"attribute_definitions": []},
                       format="json").status_code == 404
