"""M07 site / route card: real M01 data (address, location path, contacts, hours, map link), assignment scoped."""
from datetime import time

import pytest
from django.test import Client

from apps.assets import services as asset_services
from apps.sites import services as site_services
from tests.phase3_support import wo_in_progress

pytestmark = pytest.mark.django_db


def get(user, wo):
    c = Client()
    c.force_login(user)
    return c.get(f"/app/workspace/{wo.pk}/")


@pytest.fixture
def located(p3):
    ops = p3["ops"].user
    site = p3["site"]
    site_services.update_site(site, actor=ops, address="12 Harbour Road", city="Pune", state_region="MH",
                              postal_code="411001", country="IN", contact_name="Gate desk", contact_phone="+91 20 555")
    bld = site_services.create_zone(site, actor=ops, name="Block A", zone_type="BUILDING")
    area = site_services.create_zone(site, actor=ops, name="Utilities", zone_type="SERVICE_AREA", parent=bld)
    room = site_services.create_zone(site, actor=ops, name="Boiler room", zone_type="ZONE", parent=area)
    asset_services.update_asset(p3["asset"], actor=ops, zone=room, reason="place")
    site_services.add_contact(site, actor=ops, name="Priya Shah", role_title="Site engineer", phone="+91 99 111")
    site_services.add_contact(site, actor=ops, name="Mohan Rao", email="mohan@plant.test")
    site_services.create_calendar(site, actor=ops, name="Plant hours", working_days=[1, 2, 3, 4, 5],
                                  start_time=time(8), end_time=time(17), is_default=True)
    return p3


def test_route_card_shows_real_site_data(located):
    wo = wo_in_progress(located, work_type="PREVENTIVE")
    r = get(located["tech"].user, wo)
    assert r.status_code == 200
    html = r.content.decode()
    assert "12 Harbour Road, Pune, MH, 411001, IN" in html
    assert "Block A › Utilities › Boiler room" in html
    assert "Priya Shah" in html and "tel:+91 99 111" in html and "mailto:mohan@plant.test" in html
    assert "Mon, Tue, Wed, Thu, Fri" in html and "08:00-17:00" in html
    assert "Utilities" in html  # service-area context
    assert "https://www.google.com/maps/search/?api=1&amp;query=12+Harbour+Road" in html
    assert html.index("Priya Shah") < html.index("Mohan Rao")  # escalation order


def test_route_card_without_address_or_location_degrades_cleanly(p3):
    wo = wo_in_progress(p3, work_type="PREVENTIVE")
    html = get(p3["tech"].user, wo).content.decode()
    assert "No address recorded for this site" in html
    assert "Site level (no building / zone recorded)" in html
    assert "No site contacts recorded." in html
    assert 'id="route-map"' not in html


def test_route_card_keeps_assignment_and_tenant_scope(located, org_b, make_member):
    wo = wo_in_progress(located, work_type="PREVENTIVE")
    assert get(located["tech2"].user, wo).status_code == 404  # not their job
    stranger = make_member(org_b, "tech@beta.test", "technician")
    assert get(stranger.user, wo).status_code == 404  # other tenant
