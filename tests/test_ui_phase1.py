"""Phase 1 HTML UI: pages render, every state-changing control posts to a real endpoint that persists and
audits, forbidden roles are refused, foreign objects are 404, CSRF is enforced."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.assets import hierarchy, services
from apps.assets.models import Asset, AssetComponent, AssetMeter
from apps.audit.models import AuditLog
from apps.sites import services as site_services
from apps.sites.models import CalendarHoliday, OperatingCalendar, Site, SiteContact, Zone
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def audited(org, action):
    return AuditLog.objects.filter(organization=org, action=action).exists()


@pytest.fixture
def owner_client(client, owner_a, org_a):
    client.force_login(owner_a)
    return client


def site_data(**over):
    return {"code": "pune-1", "name": "Pune Plant", "timezone": "Asia/Kolkata", "city": "Pune", "country": "in",
            **over}


# --- rendering ------------------------------------------------------------------------------------------------


def test_pages_render_for_owner(owner_client, org_a, site_a1, make_asset, make_zone):
    zone = make_zone(site_a1, "Hall")
    asset = make_asset(org_a, site_a1, "UI-1", zone=zone)
    child = make_asset(org_a, site_a1, "UI-2")
    hierarchy.add_component(asset, child, actor=None)
    urls = ["/app/sites/", "/app/sites/new/", f"/app/sites/{site_a1.pk}/", f"/app/sites/{site_a1.pk}/edit/",
            f"/app/sites/{site_a1.pk}/locations/new/", f"/app/locations/{zone.pk}/edit/",
            f"/app/sites/{site_a1.pk}/calendars/new/", f"/app/sites/{site_a1.pk}/contacts/new/",
            "/app/assets/", "/app/assets/new/", f"/app/assets/new/?parent={asset.pk}", "/app/assets/categories/",
            f"/app/assets/{asset.pk}/", f"/app/assets/{asset.pk}/edit/", f"/app/assets/{asset.pk}/tree/",
            f"/app/assets/{child.pk}/?tab=hierarchy"]
    urls += [f"/app/sites/{site_a1.pk}/?tab={t}" for t in ("overview", "locations", "calendars", "contacts", "assets")]
    urls += [f"/app/assets/{asset.pk}/?tab={t}" for t in ("overview", "documents", "meters", "history", "hierarchy")]
    for url in urls:
        r = owner_client.get(url)
        assert r.status_code == 200, url
    detail = owner_client.get(f"/app/assets/{asset.pk}/").content.decode()
    assert "{#" not in detail and "{%" not in detail  # no template syntax leaking into the page
    assert "Start maintenance" in detail
    body = owner_client.get(f"/app/assets/{asset.pk}/tree/").content.decode()
    assert "UI-1" in body and "UI-2" in body
    assert "Sites &amp; Locations" in owner_client.get("/app/").content.decode()


def test_technician_sees_read_only_pages_and_cannot_create(client, tech_a, org_a, site_a1, make_asset):
    asset = make_asset(org_a, site_a1, "RO-1")
    client.force_login(tech_a)
    for url in ("/app/sites/", f"/app/sites/{site_a1.pk}/", "/app/assets/", f"/app/assets/{asset.pk}/",
                f"/app/assets/{asset.pk}/?tab=meters", f"/app/assets/{asset.pk}/?tab=hierarchy"):
        assert client.get(url).status_code == 200, url
    page = client.get(f"/app/assets/{asset.pk}/").content.decode()
    assert "Start maintenance" not in page and "/edit/" not in page  # actions are hidden, and enforced below
    forbidden_get = ["/app/sites/new/", f"/app/sites/{site_a1.pk}/edit/", "/app/assets/new/",
                     f"/app/assets/{asset.pk}/edit/", f"/app/sites/{site_a1.pk}/locations/new/"]
    for url in forbidden_get:
        assert client.get(url).status_code == 403, url
    forbidden_post = [
        ("/app/sites/new/", site_data()), (f"/app/assets/{asset.pk}/transition/start_maintenance/", {"reason": "go"}),
        (f"/app/assets/{asset.pk}/documents/", {"file": SimpleUploadedFile("a.txt", b"x")}),
        (f"/app/assets/{asset.pk}/meters/new/", {"name": "H", "unit": "h"}),
        (f"/app/sites/{site_a1.pk}/", {"action": "deactivate", "reason": "x"}),
        (f"/app/assets/{asset.pk}/components/add/", {}), ("/app/assets/categories/", {"name": "Hack"})]
    for url, data in forbidden_post:
        assert client.post(url, data).status_code == 403, url
    asset.refresh_from_db()
    assert asset.status == "ACTIVE" and not Site.objects.filter(code="PUNE-1").exists()


def test_anonymous_is_redirected_to_login(client, site_a1):
    for url in ("/app/sites/", f"/app/sites/{site_a1.pk}/", "/app/assets/", "/app/assets/new/"):
        r = client.get(url)
        assert r.status_code == 302 and "/accounts/login/" in r["Location"], url


# --- M01 actions ------------------------------------------------------------------------------------------------


def test_site_create_edit_deactivate_reactivate_persist_and_audit(owner_client, org_a):
    r = owner_client.post("/app/sites/new/", site_data())
    assert r.status_code == 302
    site = Site.objects.get(code="PUNE-1")
    assert site.name == "Pune Plant" and site.country == "IN" and audited(org_a, "site.created")
    r = owner_client.post(f"/app/sites/{site.pk}/edit/", site_data(name="Pune Works"))
    assert r.status_code == 302
    site.refresh_from_db()
    assert site.name == "Pune Works" and audited(org_a, "site.updated")
    r = owner_client.post(f"/app/sites/{site.pk}/", {"action": "deactivate", "reason": ""})
    site.refresh_from_db()
    assert site.status == "ACTIVE"  # reason is mandatory
    owner_client.post(f"/app/sites/{site.pk}/", {"action": "deactivate", "reason": "Closed for good"})
    site.refresh_from_db()
    assert site.status == "INACTIVE" and audited(org_a, "site.deactivated")
    assert "Closed for good" in owner_client.get(f"/app/sites/{site.pk}/").content.decode()
    owner_client.post(f"/app/sites/{site.pk}/", {"action": "reactivate"})
    site.refresh_from_db()
    assert site.status == "ACTIVE" and audited(org_a, "site.reactivated")


def test_site_form_validation_errors_do_not_persist(owner_client, site_a1):
    r = owner_client.post("/app/sites/new/", site_data(code="a1"))  # duplicate
    assert r.status_code == 400 and "already exists" in r.content.decode()
    r = owner_client.post("/app/sites/new/", site_data(name="", code="NEW"))
    assert r.status_code == 400
    r = owner_client.post("/app/sites/new/", site_data(code="TZ", timezone="Nope/Zone"))
    assert r.status_code == 400
    assert Site.objects.filter(organization=site_a1.organization).count() == 1


def test_site_deactivation_blocked_by_active_assets_shows_message(owner_client, org_a, site_a1, make_asset):
    make_asset(org_a, site_a1, "BLK-1")
    r = owner_client.post(f"/app/sites/{site_a1.pk}/", {"action": "deactivate", "reason": "x"}, follow=True)
    assert "active asset" in r.content.decode()
    site_a1.refresh_from_db()
    assert site_a1.status == "ACTIVE"


def test_location_calendar_contact_actions(owner_client, org_a, site_a1):
    r = owner_client.post(f"/app/sites/{site_a1.pk}/locations/new/", {
        "name": "Main block", "zone_type": "BUILDING", "code": "MB", "parent": "", "description": ""})
    assert r.status_code == 302
    block = Zone.objects.get(name="Main block")
    r = owner_client.post(f"/app/sites/{site_a1.pk}/locations/new/", {
        "name": "Bay 1", "zone_type": "ZONE", "parent": block.pk, "code": "", "description": ""})
    bay = Zone.objects.get(name="Bay 1")
    assert bay.parent_id == block.pk and audited(org_a, "zone.created")
    page = owner_client.get(f"/app/sites/{site_a1.pk}/?tab=locations").content.decode()
    assert "Main block" in page and "Bay 1" in page
    # cannot move the block under its own child (not even offered) -> server rejects a crafted post as well
    r = owner_client.post(f"/app/locations/{block.pk}/edit/", {
        "name": "Main block", "zone_type": "ZONE", "parent": bay.pk, "code": "MB", "description": ""})
    assert r.status_code == 400
    block.refresh_from_db()
    assert block.parent_id is None
    r = owner_client.post(f"/app/locations/{bay.pk}/edit/", {
        "name": "Bay One", "zone_type": "ZONE", "parent": block.pk, "code": "", "description": ""})
    bay.refresh_from_db()
    assert bay.name == "Bay One" and audited(org_a, "zone.updated")
    owner_client.post(f"/app/locations/{block.pk}/status/", {"action": "deactivate", "reason": "x"})
    block.refresh_from_db()
    assert block.status == "ACTIVE"  # has an active child
    owner_client.post(f"/app/locations/{bay.pk}/status/", {"action": "deactivate", "reason": "unused"})
    bay.refresh_from_db()
    assert bay.status == "INACTIVE" and audited(org_a, "zone.deactivated")
    owner_client.post(f"/app/locations/{bay.pk}/status/", {"action": "reactivate"})
    bay.refresh_from_db()
    assert bay.status == "ACTIVE"

    # calendars + holidays
    r = owner_client.post(f"/app/sites/{site_a1.pk}/calendars/new/", {
        "name": "Weekday shift", "working_days": ["1", "2", "3", "4", "5"], "start_time": "08:00",
        "end_time": "17:00", "notes": ""})
    assert r.status_code == 302
    cal = OperatingCalendar.objects.get(name="Weekday shift")
    assert cal.working_days == [1, 2, 3, 4, 5] and cal.is_default
    assert owner_client.post(f"/app/sites/{site_a1.pk}/calendars/new/", {
        "name": "Bad", "working_days": ["1"], "start_time": "09:00", "end_time": "08:00"}).status_code == 400
    owner_client.post(f"/app/calendars/{cal.pk}/holidays/", {"action": "add", "date": "2026-12-25", "name": "Christmas"})
    h = CalendarHoliday.objects.get(calendar=cal)
    assert audited(org_a, "calendar.holiday_added")
    assert "Christmas" in owner_client.get(f"/app/sites/{site_a1.pk}/?tab=calendars").content.decode()
    owner_client.post(f"/app/calendars/{cal.pk}/holidays/", {"action": "remove", "holiday": h.pk})
    assert not CalendarHoliday.objects.filter(calendar=cal).exists()
    r = owner_client.post(f"/app/calendars/{cal.pk}/edit/", {
        "name": "Weekday shift", "working_days": ["1", "2"], "start_time": "07:00", "end_time": "15:00",
        "is_default": "on"})
    cal.refresh_from_db()
    assert cal.working_days == [1, 2] and audited(org_a, "calendar.updated")
    owner_client.post(f"/app/calendars/{cal.pk}/delete/")
    assert not OperatingCalendar.objects.filter(pk=cal.pk).exists() and audited(org_a, "calendar.deleted")

    # contacts
    owner_client.post(f"/app/sites/{site_a1.pk}/contacts/new/", {"name": "Site Manager", "phone": "+91 1"})
    c = SiteContact.objects.get(name="Site Manager")
    assert c.escalation_order == 1 and audited(org_a, "site.contact_added")
    owner_client.post(f"/app/contacts/{c.pk}/edit/", {"name": "Site Manager", "phone": "+91 2",
                                                       "escalation_order": 3})
    c.refresh_from_db()
    assert (c.phone, c.escalation_order) == ("+91 2", 3)
    owner_client.post(f"/app/contacts/{c.pk}/edit/", {"action": "delete"})
    assert not SiteContact.objects.filter(pk=c.pk).exists() and audited(org_a, "site.contact_removed")


# --- M02 actions -----------------------------------------------------------------------------------------------


def asset_form(site, category, **over):
    return {"asset_tag": "PMP-9", "name": "Cooling pump", "category": category.pk, "site": site.pk,
            "manufacturer": "Acme", "model": "C1", "serial_number": "SN-1", **over}


def test_zone_filter_script_uses_site_code_not_label(owner_client):
    """Regression (found in the real-browser pass): option labels are 'CODE · Name'; the script must compare the code."""
    html = owner_client.get("/app/assets/new/").content.decode()
    assert 'o.text.split(" ·")[0]' in html or "o.text.split(\" ·\")[0]" in html or 'split(" ·")[0]' in html


def test_asset_register_edit_and_move(owner_client, org_a, site_a1, site_a2, make_zone, make_category):
    zone, cat = make_zone(site_a1, "Hall"), make_category(org_a)
    r = owner_client.post("/app/assets/new/", asset_form(site_a1, cat, zone=zone.pk))
    assert r.status_code == 302
    a = Asset.objects.get(asset_tag="PMP-9")
    assert a.status == "ACTIVE" and a.zone_id == zone.pk and audited(org_a, "asset.created")
    r = owner_client.post("/app/assets/new/", asset_form(site_a1, cat))  # duplicate tag
    assert r.status_code == 400 and "already exists" in r.content.decode()
    r = owner_client.post("/app/assets/new/", asset_form(site_a2, cat, asset_tag="X-2", zone=zone.pk))
    assert r.status_code == 400  # zone belongs to another site
    r = owner_client.post(f"/app/assets/{a.pk}/edit/", {**asset_form(site_a2, cat), "name": "Cooling pump 2",
                                                       "reason": "Moved to annex"})
    assert r.status_code == 302
    a.refresh_from_db()
    assert a.name == "Cooling pump 2" and a.site_id == site_a2.pk and a.zone_id is None
    assert audited(org_a, "asset.location_changed")
    page = owner_client.get(f"/app/assets/{a.pk}/?tab=history").content.decode()
    assert "Moved to annex" in page and "asset.updated" in page and "location-history" in page


def test_status_buttons_persist_audit_and_reject_invalid(owner_client, org_a, site_a1, make_asset):
    a = make_asset(org_a, site_a1, "ST-1")
    page = owner_client.get(f"/app/assets/{a.pk}/").content.decode()
    assert "Start maintenance" in page and "Retire" not in page  # only valid transitions are offered
    r = owner_client.post(f"/app/assets/{a.pk}/transition/start_maintenance/", {"reason": "Quarterly service"})
    assert r.status_code == 302
    a.refresh_from_db()
    assert a.status == "UNDER_MAINTENANCE" and audited(org_a, "asset.status_changed")
    assert a.status_history.count() == 2
    r = owner_client.post(f"/app/assets/{a.pk}/transition/retire/", {"reason": "illegal jump"}, follow=True)
    a.refresh_from_db()
    assert a.status == "UNDER_MAINTENANCE" and "not allowed" in r.content.decode()
    owner_client.post(f"/app/assets/{a.pk}/transition/mark_out_of_service/", {"reason": ""})
    a.refresh_from_db()
    assert a.status == "UNDER_MAINTENANCE"  # reason required
    owner_client.post(f"/app/assets/{a.pk}/transition/mark_out_of_service/", {"reason": "Beyond repair"})
    owner_client.post(f"/app/assets/{a.pk}/transition/dispose/", {"reason": "Scrapped"})
    a.refresh_from_db()
    assert a.status == "DISPOSED"
    page = owner_client.get(f"/app/assets/{a.pk}/").content.decode()
    assert "read-only" in page and "Edit" not in page.split("fx-tabs")[0]
    assert owner_client.get(f"/app/assets/{a.pk}/edit/").status_code in (200, 302)
    assert owner_client.post(f"/app/assets/{a.pk}/edit/", asset_form(a.site, a.category, asset_tag="ST-1",
                                                                      name="renamed")).status_code == 400
    a.refresh_from_db()
    assert a.name != "renamed"


def test_document_upload_download_meter_actions(owner_client, org_a, site_a1, make_asset):
    a = make_asset(org_a, site_a1, "DM-1")
    r = owner_client.post(f"/app/assets/{a.pk}/documents/", {
        "file": SimpleUploadedFile("spec.txt", b"specification", content_type="text/plain"), "title": "Spec",
        "doc_type": "DATASHEET"})
    assert r.status_code == 302
    doc = a.documents.get()
    assert doc.attachment.original_name == "spec.txt" and audited(org_a, "asset.document_added")
    page = owner_client.get(f"/app/assets/{a.pk}/?tab=documents").content.decode()
    assert "Spec" in page and f"/app/files/{doc.attachment_id}/download/" in page
    assert owner_client.get(f"/app/files/{doc.attachment_id}/download/").status_code == 200
    owner_client.post(f"/app/assets/{a.pk}/documents/", {"file": SimpleUploadedFile("x.exe", b"MZ")})
    assert a.documents.count() == 1
    # meters
    owner_client.post(f"/app/assets/{a.pk}/meters/new/", {"name": "Run hours", "unit": "h"})
    m = AssetMeter.objects.get(asset=a)
    owner_client.post(f"/app/meters/{m.pk}/reading/", {"value": "120.5", "notes": "first"})
    assert m.readings.count() == 1 and audited(org_a, "asset.meter_reading_recorded")
    r = owner_client.post(f"/app/meters/{m.pk}/reading/", {"value": "100"}, follow=True)
    assert m.readings.count() == 1 and "lower than the previous reading" in r.content.decode()
    page = owner_client.get(f"/app/assets/{a.pk}/?tab=meters").content.decode()
    assert "120.5" in page and "Run hours" in page
    owner_client.post(f"/app/meters/{m.pk}/toggle/", {"action": "deactivate"})
    m.refresh_from_db()
    assert not m.is_active
    owner_client.post(f"/app/meters/{m.pk}/reading/", {"value": "130"})
    assert m.readings.count() == 1  # inactive meter refuses readings


def test_hierarchy_actions(owner_client, org_a, site_a1, make_asset):
    gen, eng, pump = (make_asset(org_a, site_a1, t) for t in ("H-GEN", "H-ENG", "H-PMP"))
    owner_client.post(f"/app/assets/{gen.pk}/components/add/", {
        "child": eng.pk, "relationship_type": "ASSEMBLY", "quantity": 1})
    assert AssetComponent.objects.get(child=eng).parent_id == gen.pk and audited(org_a, "asset.component_added")
    # register a brand-new child in one step
    r = owner_client.post("/app/assets/new/", {
        **asset_form(site_a1, gen.category, asset_tag="H-NEW", serial_number="", manufacturer=""),
        "parent": gen.pk, "relationship_type": "REPLACEABLE_PART", "quantity": 2, "part_number": "PN-7"})
    assert r.status_code == 302
    new = Asset.objects.get(asset_tag="H-NEW")
    link = AssetComponent.objects.get(child=new)
    assert (link.parent_id, link.quantity, link.part_number) == (gen.pk, 2, "PN-7")
    # a cycle cannot be created by posting a crafted form
    owner_client.post(f"/app/assets/{eng.pk}/components/add/", {"child": gen.pk, "relationship_type": "COMPONENT",
                                                                 "quantity": 1})
    assert not AssetComponent.objects.filter(child=gen).exists()
    # move + detach
    eng_link = AssetComponent.objects.get(child=eng)
    owner_client.post(f"/app/components/{eng_link.pk}/move/", {"parent": pump.pk})
    eng_link.refresh_from_db()
    assert eng_link.parent_id == pump.pk and audited(org_a, "asset.component_moved")
    owner_client.post(f"/app/components/{eng_link.pk}/move/", {"parent": eng.pk})  # onto itself
    eng_link.refresh_from_db()
    assert eng_link.parent_id == pump.pk
    owner_client.post(f"/app/components/{eng_link.pk}/remove/", {"next_asset": "child"})
    assert not AssetComponent.objects.filter(pk=eng_link.pk).exists() and audited(org_a, "asset.component_removed")
    body = owner_client.get(f"/app/assets/{new.pk}/tree/").content.decode()
    assert "H-GEN" in body and "H-NEW" in body and "Replaceable part" in body


def test_category_management(owner_client, org_a):
    owner_client.post("/app/assets/categories/", {"name": "Generator", "description": "Gensets", "is_active": "on"})
    from apps.assets.models import AssetCategory

    cat = AssetCategory.objects.get(name="Generator")
    owner_client.post("/app/assets/categories/", {"category": cat.pk, "name": "Generators", "description": "x"})
    cat.refresh_from_db()
    assert cat.name == "Generators" and not cat.is_active and audited(org_a, "asset.category_updated")
    page = owner_client.get("/app/assets/categories/").content.decode()
    assert "Generators" in page


def test_asset_list_filters_and_pagination(owner_client, org_a, site_a1, site_a2, make_asset, make_category):
    cat = make_category(org_a, "Fan")
    for i in range(23):
        make_asset(org_a, site_a1, f"PG-{i:02d}")
    make_asset(org_a, site_a2, "OTHER-1", category=cat, serial_number="Z9")
    page = owner_client.get("/app/assets/").content.decode()
    assert "Page 1 of 2" in page
    assert "OTHER-1" not in owner_client.get(f"/app/assets/?site={site_a1.pk}").content.decode()
    only = owner_client.get(f"/app/assets/?category={cat.pk}").content.decode()
    assert "OTHER-1" in only and "PG-00" not in only
    assert "OTHER-1" in owner_client.get("/app/assets/?q=z9").content.decode()
    assert "No assets match" in owner_client.get("/app/assets/?status=RETIRED").content.decode()


def test_asset_list_query_count(owner_client, org_a, site_a1, make_asset, django_assert_max_num_queries):
    for i in range(15):
        make_asset(org_a, site_a1, f"NQ-{i}")
    with django_assert_max_num_queries(25):
        assert owner_client.get("/app/assets/").status_code == 200


# --- tenant isolation (HTML) -------------------------------------------------------------------------------------


def test_foreign_objects_are_404_on_every_html_route(owner_client, org_b, owner_b, site_b1, make_asset, make_zone):
    zone_b = make_zone(site_b1, "Hall")
    foreign = make_asset(org_b, site_b1, "FX-1")
    child = make_asset(org_b, site_b1, "FX-2")
    link = hierarchy.add_component(foreign, child, actor=owner_b)
    meter = services.create_meter(foreign, name="Hours", unit="h", actor=owner_b)
    cal = site_services.create_calendar(site_b1, actor=owner_b, name="Std", is_24x7=True)
    contact = site_services.add_contact(site_b1, actor=owner_b, name="Boss", phone="1")
    gets = [f"/app/sites/{site_b1.pk}/", f"/app/sites/{site_b1.pk}/edit/", f"/app/sites/{site_b1.pk}/locations/new/",
            f"/app/sites/{site_b1.pk}/calendars/new/", f"/app/sites/{site_b1.pk}/contacts/new/",
            f"/app/locations/{zone_b.pk}/edit/", f"/app/calendars/{cal.pk}/edit/", f"/app/contacts/{contact.pk}/edit/",
            f"/app/assets/{foreign.pk}/", f"/app/assets/{foreign.pk}/edit/", f"/app/assets/{foreign.pk}/tree/",
            f"/app/assets/{foreign.pk}/?tab=history", f"/app/assets/new/?parent={foreign.pk}"]
    posts = [
        (f"/app/sites/{site_b1.pk}/", {"action": "deactivate", "reason": "x"}),
        (f"/app/locations/{zone_b.pk}/status/", {"action": "deactivate", "reason": "x"}),
        (f"/app/calendars/{cal.pk}/delete/", {}), (f"/app/calendars/{cal.pk}/holidays/", {"action": "add"}),
        (f"/app/contacts/{contact.pk}/edit/", {"action": "delete"}),
        (f"/app/assets/{foreign.pk}/transition/start_maintenance/", {"reason": "pwn"}),
        (f"/app/assets/{foreign.pk}/documents/", {"file": SimpleUploadedFile("a.txt", b"x")}),
        (f"/app/assets/{foreign.pk}/meters/new/", {"name": "x", "unit": "h"}),
        (f"/app/assets/{foreign.pk}/components/add/", {"child": child.pk}),
        (f"/app/meters/{meter.pk}/reading/", {"value": 9}), (f"/app/meters/{meter.pk}/toggle/", {"action": "deactivate"}),
        (f"/app/components/{link.pk}/move/", {"parent": foreign.pk}), (f"/app/components/{link.pk}/remove/", {})]
    for url in gets:
        assert owner_client.get(url).status_code == 404, url
    for url, data in posts:
        assert owner_client.post(url, data).status_code == 404, url
    foreign.refresh_from_db()
    assert foreign.status == "ACTIVE" and AssetComponent.objects.unscoped().filter(pk=link.pk).exists()
    assert "FX-1" not in owner_client.get("/app/assets/").content.decode()
    assert "B1" not in owner_client.get("/app/sites/").content.decode().replace("Beta", "")


def test_foreign_ids_in_form_fields_are_rejected(owner_client, org_a, org_b, site_a1, site_b1, make_category,
                                                 make_zone):
    cat_a, cat_b = make_category(org_a), make_category(org_b)
    zone_b = make_zone(site_b1, "Hall")
    for data in (asset_form(site_b1, cat_a), asset_form(site_a1, cat_b), asset_form(site_a1, cat_a, zone=zone_b.pk)):
        assert owner_client.post("/app/assets/new/", data).status_code == 400
    assert not Asset.objects.unscoped().filter(asset_tag="PMP-9").exists()


# --- CSRF / real login ------------------------------------------------------------------------------------------------


def test_csrf_is_enforced_and_works_after_real_login(owner_a, org_a):
    c = Client(enforce_csrf_checks=True)
    login_url = "/accounts/login/"
    token = c.get(login_url).cookies["csrftoken"].value
    r = c.post(login_url, {"username": owner_a.email, "password": PASSWORD, "csrfmiddlewaretoken": token},
               HTTP_ORIGIN="http://testserver")
    assert r.status_code == 302
    # a state-changing POST without the token is refused and does nothing
    assert c.post("/app/sites/new/", site_data()).status_code == 403
    assert not Site.objects.filter(code="PUNE-1").exists()
    token = c.get("/app/sites/new/").cookies["csrftoken"].value
    r = c.post("/app/sites/new/", {**site_data(), "csrfmiddlewaretoken": token}, HTTP_ORIGIN="http://testserver")
    assert r.status_code == 302 and Site.objects.filter(code="PUNE-1").exists()
