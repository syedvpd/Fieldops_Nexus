"""M14 drill-down: KPI cards link to the owning module's filtered list, only when the caller may open it; the
filters those links use (open / overdue work orders) return exactly the matching records."""
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from tests.phase3_support import new_wo, step, wo_in_progress

pytestmark = pytest.mark.django_db


def web(user):
    c = Client()
    c.force_login(user)
    return c


def test_operations_kpis_link_to_filtered_lists(p3, make_member):
    auditor = make_member(p3["org"], "auditor@alpha.test", "auditor")
    html = web(auditor.user).get("/app/dashboards/?section=operations").content.decode()
    assert 'data-drill="open_work_orders"' in html and 'href="/app/work-orders/?open=1"' in html
    assert 'data-drill="overdue_work"' in html and 'href="/app/work-orders/?overdue=1"' in html


def test_kpi_does_not_link_where_the_caller_cannot_open_the_target(p3, make_member):
    ops = make_member(p3["org"], "reportonly@alpha.test", "auditor")
    from apps.dashboards.views import drill_links

    class Fake:
        pass

    links = drill_links(ops)
    assert links["open_work_orders"].startswith("/app/work-orders/")
    tech_links = drill_links(p3["tech"])
    assert "open_work_orders" not in tech_links and "sla_breaches" not in tech_links


def test_open_and_overdue_filters_return_exactly_the_matching_orders(p3):
    ops = web(p3["ops"].user)
    closed_free = new_wo(p3, title="Cancelled one")
    step(closed_free, "cancel", p3, "planner", reason="not needed")
    live = new_wo(p3, title="Open draft")
    late = new_wo(p3, title="Late planned")
    past = timezone.now() - timedelta(days=2)
    late = step(late, "plan", p3, "planner", planned_start=past - timedelta(hours=2), planned_end=past)
    on_time = wo_in_progress(p3, work_type="PREVENTIVE", asset=p3["asset2"])
    page = ops.get("/app/work-orders/?open=1").content.decode()
    assert "Open draft" in page and "Late planned" in page and "Cancelled one" not in page
    page = ops.get("/app/work-orders/?overdue=1").content.decode()
    assert "Late planned" in page and "Open draft" not in page and on_time.number not in page
    assert live.number not in page
