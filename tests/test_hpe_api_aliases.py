"""HPE-named API paths (section "Mandatory API groups") behave exactly like the canonical routes: same RBAC, tenant
scope and service rules."""
import uuid
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory import services as inv
from apps.portal import services as portal
from tests.phase3_support import new_wo, step, wo_in_progress

pytestmark = pytest.mark.django_db


def api(user, org):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


def test_work_order_action_urls_assign_start_hold_complete(p3):
    wo = new_wo(p3, work_type="CORRECTIVE")
    t0 = timezone.now() + timedelta(days=1)
    step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=2))
    planner, tech = api(p3["planner"].user, p3["org"]), api(p3["tech"].user, p3["org"])
    base = f"/api/v1/work-orders/{wo.pk}"
    assert tech.post(f"{base}/assign/", {"technician": str(p3["tech"].pk)}, format="json").status_code == 404  # an unassigned job is invisible to the technician
    r = planner.post(f"{base}/assign/", {"technician": str(p3["tech"].pk)}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "ASSIGNED"
    assert tech.post(f"{base}/start/", {}, format="json").status_code == 409  # not dispatched yet
    assert planner.post(f"{base}/transition/", {"action": "dispatch"}, format="json").status_code == 200
    assert tech.post(f"{base}/start/", {}, format="json").json()["status"] == "IN_PROGRESS"
    assert tech.post(f"{base}/hold/", {}, format="json").status_code == 400  # a reason is required
    assert tech.post(f"{base}/hold/", {"reason": "Waiting for parts"}, format="json").json()["status"] == "ON_HOLD"
    assert tech.post(f"{base}/transition/", {"action": "resume"}, format="json").status_code == 200
    assert tech.post(f"{base}/complete/", {}, format="json").status_code in (400, 409)  # notes / evidence missing
    assert planner.post(f"{base}/complete/", {"resolution_notes": "x" * 20}, format="json").status_code == 403
    other = api(p3["reader"].user, p3["org"])
    assert other.post(f"{base}/start/", {}, format="json").status_code == 403


def test_hpe_named_read_aliases_match_the_canonical_routes(sla_):
    p = sla_
    ops = api(p["ops"].user, p["org"])
    pairs = {"/api/v1/schedules/": "/api/v1/maintenance-schedules/", "/api/v1/slas/": "/api/v1/sla-profiles/",
             "/api/v1/breaches/": "/api/v1/sla-breaches/", "/api/v1/stock/": "/api/v1/stock-balances/",
             "/api/v1/checklists/": "/api/v1/checklist-templates/"}
    for alias, canonical in pairs.items():
        a, c = ops.get(alias), ops.get(canonical)
        assert a.status_code == c.status_code, alias
        if a.status_code == 200:
            assert a.json() == c.json(), alias
    tech = api(p["tech"].user, p["org"])
    for alias in ("/api/v1/slas/", "/api/v1/breaches/", "/api/v1/escalations/", "/api/v1/schedules/"):
        assert tech.get(alias).status_code == 403, alias
    assert ops.get("/api/v1/escalations/").status_code == 200


def test_reserve_issue_return_urls_move_stock_through_the_same_service(inv_):
    p = inv_
    wo = wo_in_progress(p)
    inv.receive(p["wh"], p["part"], 10, actor=p["stores"].user)
    line = inv.request_part(wo, p["part"], 4, actor=p["tech"].user, membership=p["tech"])
    stores, tech = api(p["stores"].user, p["org"]), api(p["tech"].user, p["org"])
    body = {"part_line": str(line.pk), "warehouse": str(p["wh"].pk)}
    assert tech.post("/api/v1/reserve/", body, format="json").status_code == 403
    assert stores.post("/api/v1/reserve/", body, format="json").status_code == 200
    assert stores.post("/api/v1/issue/", {**body, "quantity": "3"}, format="json").status_code == 200
    assert stores.post("/api/v1/return/", {"part_line": str(line.pk), "quantity": "1"}, format="json").status_code == 200
    from apps.inventory.models import StockBalance

    assert StockBalance.objects.get(warehouse=p["wh"], part=p["part"]).on_hand == 8  # 10 - 3 + 1
    assert stores.post("/api/v1/issue/", {**body, "quantity": "50"}, format="json").status_code == 409
    assert stores.post("/api/v1/issue/", {"part_line": str(uuid.uuid4()), "warehouse": str(p["wh"].pk),
                                          "quantity": "1"}, format="json").status_code == 404
    assert stores.post("/api/v1/issue/", {"warehouse": str(p["wh"].pk), "quantity": "1"}, format="json"
                       ).status_code == 404


def test_generate_work_orders_url(p3):
    ops, tech = api(p3["ops"].user, p3["org"]), api(p3["tech"].user, p3["org"])
    assert tech.post("/api/v1/generate-work-orders/", {}, format="json").status_code == 403
    r = ops.post("/api/v1/generate-work-orders/", {}, format="json")
    assert r.status_code == 200 and r.json()["generated"] == 0
    assert ops.post("/api/v1/generate-work-orders/", {}, format="json").json()["generated"] == 0  # idempotent


def test_client_requests_and_status_urls(p3, make_member):
    org = p3["org"]
    svc = make_member(org, "svc@alias.test", "service_manager")
    client = make_member(org, "client@alias.test", "client_requester")
    acct = portal.enable_account(org, client, actor=svc.user)
    portal.grant_asset(acct, p3["asset"], actor=svc.user)
    c = api(client.user, org)
    r = c.post("/api/v1/client/requests/", {"asset": str(p3["asset"].pk), "title": "Alias request", "urgency": "LOW",
                                            "files": [SimpleUploadedFile("a.txt", b"evidence")]}, format="multipart")
    assert r.status_code == 201, r.json()
    rid = r.json()["id"]
    assert c.get("/api/v1/client/requests/").json()["count"] == 1
    st = c.get(f"/api/v1/client/requests/{rid}/status/").json()
    assert st["status"] == "NEW" and st["client_status"]["label"] == "Received" and set(st) == {
        "number", "status", "client_status", "visit"}
    other = make_member(org, "client2@alias.test", "client_requester")
    assert api(other.user, org).get(f"/api/v1/client/requests/{rid}/status/").status_code in (403, 404)
    assert api(p3["tech"].user, org).get(f"/api/v1/client/requests/{rid}/status/").status_code == 403
