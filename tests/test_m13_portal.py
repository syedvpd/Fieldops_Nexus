"""M13 Client portal: client-only accounts, asset grants, request submission through M05, ownership isolation
(client vs client, tenant vs tenant), client-safe projections, confirmation / reopen rules, privileged endpoints
closed to clients, attachments, UI and the full request -> work order -> confirmation -> closure journey."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, InvalidTransition, NotFound, PermissionDenied, ValidationFailed
from apps.files.models import Attachment
from apps.incidents import services as incidents
from apps.incidents.models import ServiceRequest
from apps.notifications.models import Notification
from apps.portal import selectors
from apps.portal import services as portal
from apps.portal.models import PortalAccount, PortalAssetGrant
from tests.phase3_support import finish_work, step

pytestmark = pytest.mark.django_db


@pytest.fixture
def pt_(p3, make_member, org_b, make_site, make_asset):
    org = p3["org"]
    svc = make_member(org, "svc@alpha.test", "service_manager")
    a = make_member(org, "clienta@alpha.test", "client_requester")
    b = make_member(org, "clientb@alpha.test", "client_requester")
    acct_a = portal.enable_account(org, a, company="Acme Foods", actor=svc.user)
    acct_b = portal.enable_account(org, b, company="Bolt Ltd", actor=svc.user)
    portal.grant_asset(acct_a, p3["asset"], actor=svc.user)
    portal.grant_asset(acct_b, p3["asset2"], actor=svc.user)
    beta_client = make_member(org_b, "client@beta.test", "client_requester")
    beta_svc = make_member(org_b, "svc@beta.test", "service_manager")
    b_asset = make_asset(org_b, make_site(org_b, "B7"), "B-LINE")
    b_acct = portal.enable_account(org_b, beta_client, actor=beta_svc.user)
    portal.grant_asset(b_acct, b_asset, actor=beta_svc.user)
    return {**p3, "svc": svc, "a": a, "b": b, "acct_a": acct_a, "acct_b": acct_b, "org_b": org_b,
            "beta_client": beta_client, "beta_svc": beta_svc, "b_asset": b_asset}


def api(user, org):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


def web(user):
    c = Client()
    c.force_login(user)
    return c


def upload(name="photo.txt", body=b"leaking seal evidence"):
    return SimpleUploadedFile(name, body)


def submit(p, who="a", asset=None, **kw):
    return portal.submit_request(p[who], asset=asset or p["asset"], title=kw.pop("title", "Pump is leaking"),
                                 description=kw.pop("description", "Water on the floor"), **kw)


# --- accounts and grants -----------------------------------------------------------------------------------------


def test_only_client_role_members_can_be_enabled(pt_):
    with pytest.raises(Conflict) as e:
        portal.enable_account(pt_["org"], pt_["tech"], actor=pt_["svc"].user)
    assert e.value.code == "not_client_role"
    with pytest.raises(Conflict) as e:
        portal.enable_account(pt_["org"], pt_["a"], actor=pt_["svc"].user)
    assert e.value.code == "account_exists"
    with pytest.raises(ValidationFailed):
        portal.enable_account(pt_["org"], pt_["beta_client"], actor=pt_["svc"].user)  # other organization
    assert AuditLog.objects.filter(action="portal.account_enabled", organization=pt_["org"]).count() == 2


def test_grants(pt_):
    with pytest.raises(Conflict):
        portal.grant_asset(pt_["acct_a"], pt_["asset"], actor=pt_["svc"].user)
    with pytest.raises(NotFound):
        portal.grant_asset(pt_["acct_a"], pt_["b_asset"], actor=pt_["svc"].user)  # other tenant's asset
    portal.revoke_asset(pt_["acct_a"], pt_["asset"], actor=pt_["svc"].user)
    assert not selectors.granted_assets(pt_["a"]).exists()
    with pytest.raises(ValidationFailed):
        portal.revoke_asset(pt_["acct_a"], pt_["asset"], actor=pt_["svc"].user)
    portal.grant_asset(pt_["acct_a"], pt_["asset"], actor=pt_["svc"].user)
    portal.set_account_active(pt_["acct_a"], False, actor=pt_["svc"].user)
    assert not selectors.granted_assets(pt_["a"]).exists()


# --- submitting --------------------------------------------------------------------------------------------------


def test_submit_creates_m05_request_with_evidence_audit_and_staff_notification(pt_):
    sr = submit(pt_, uploads=[upload("a.txt"), upload("b.txt", b"second")], urgency="HIGH", kind="INCIDENT")
    sr = ServiceRequest.objects.for_organization(pt_["org"]).get(pk=sr.pk)
    assert sr.status == "NEW" and sr.reported_by == pt_["a"] and sr.severity == "HIGH" and sr.asset == pt_["asset"]
    assert sr.number.startswith("INC-") and sr.site == pt_["site"]
    assert Attachment.objects.for_organization(pt_["org"]).filter(object_id=str(sr.pk)).count() == 2
    assert AuditLog.objects.filter(action="portal.request_submitted", target_id=str(sr.pk)).exists()
    assert AuditLog.objects.filter(action="incident.created", target_id=str(sr.pk)).exists()  # M05 stays authoritative
    notes = Notification.objects.for_organization(pt_["org"]).filter(source="portal")
    assert notes.filter(recipient=pt_["ops"].user).exists() and not notes.filter(recipient=pt_["a"].user).exists()
    assert ServiceRequest.objects.for_organization(pt_["org"]).count() == 1  # no second request model


def test_submit_rules(pt_):
    with pytest.raises(NotFound):
        submit(pt_, "a", asset=pt_["asset2"])  # not granted to client A
    with pytest.raises(NotFound):
        submit(pt_, "a", asset=pt_["b_asset"])  # another tenant
    with pytest.raises(ValidationFailed):
        submit(pt_, urgency="CRITICAL")
    with pytest.raises(ValidationFailed):
        submit(pt_, kind="HACK")
    with pytest.raises(ValidationFailed):
        submit(pt_, uploads=[upload(f"{i}.txt") for i in range(6)])
    with pytest.raises(ValidationFailed):
        submit(pt_, title="  ")
    assert not ServiceRequest.objects.for_organization(pt_["org"]).exists()
    portal.set_account_active(pt_["acct_a"], False, actor=pt_["svc"].user)
    with pytest.raises(PermissionDenied):
        submit(pt_)
    with pytest.raises(PermissionDenied):
        portal.submit_request(pt_["tech"], asset=pt_["asset"], title="Not a client")  # no portal account


def test_bad_attachment_rolls_back_the_whole_submission(pt_):
    with pytest.raises(ValidationFailed):
        submit(pt_, uploads=[upload("ok.txt"), SimpleUploadedFile("evil.exe", b"MZ\x90\x00")])
    assert not ServiceRequest.objects.for_organization(pt_["org"]).exists()
    assert not Attachment.objects.for_organization(pt_["org"]).exists()
    assert not AuditLog.objects.filter(action="portal.request_submitted").exists()


# --- isolation ---------------------------------------------------------------------------------------------------


def test_clients_only_see_their_own_requests(pt_):
    mine = submit(pt_, "a")
    theirs = portal.submit_request(pt_["b"], asset=pt_["asset2"], title="Fan noisy")
    assert list(selectors.my_requests(pt_["a"])) == [mine]
    assert list(selectors.my_requests(pt_["b"])) == [theirs]
    with pytest.raises(NotFound):
        selectors.get_my_request(pt_["a"], theirs.pk)
    for fn in (lambda: portal.confirm(pt_["a"], theirs), lambda: portal.reopen(pt_["a"], theirs, reason="no"),
               lambda: portal.add_attachment(pt_["a"], theirs, upload())):
        with pytest.raises(NotFound):
            fn()


def test_cross_tenant_client_cannot_touch_requests(pt_):
    mine = submit(pt_, "a")
    with pytest.raises(NotFound):
        selectors.get_my_request(pt_["beta_client"], mine.pk)
    with pytest.raises(NotFound):
        portal.confirm(pt_["beta_client"], mine)


def test_api_isolation_between_clients_and_tenants(pt_):
    mine = submit(pt_, "a", uploads=[upload()])
    theirs = portal.submit_request(pt_["b"], asset=pt_["asset2"], title="Fan noisy")
    ca, cb = api(pt_["a"].user, pt_["org"]), api(pt_["b"].user, pt_["org"])
    cbeta = api(pt_["beta_client"].user, pt_["org_b"])
    assert [r["number"] for r in ca.get("/api/v1/portal/requests/").json()["results"]] == [mine.number]
    assert ca.get(f"/api/v1/portal/requests/{theirs.pk}/").status_code == 404
    assert cbeta.get(f"/api/v1/portal/requests/{mine.pk}/").status_code == 404
    assert cb.get(f"/api/v1/portal/requests/{mine.pk}/").status_code == 404
    for verb in ("confirm", "reopen", "attachments"):
        assert ca.post(f"/api/v1/portal/requests/{theirs.pk}/{verb}/", {"reason": "x"}, format="json"
                       ).status_code == 404
    cross = APIClient()
    cross.force_authenticate(user=pt_["a"].user)
    cross.credentials(HTTP_X_ORGANIZATION=pt_["org_b"].slug)
    assert cross.get("/api/v1/portal/requests/").status_code == 403
    assert [a["asset_tag"] for a in ca.get("/api/v1/portal/assets/").json()["results"]] == ["P3-PUMP"]
    assert ca.post("/api/v1/portal/requests/", {"asset": str(pt_["asset2"].pk), "title": "Not mine"}, format="json"
                   ).status_code == 404
    assert ca.post("/api/v1/portal/requests/", {"asset": str(pt_["b_asset"].pk), "title": "Not mine"}, format="json"
                   ).status_code == 404


def test_attachment_download_rules(pt_):
    mine = submit(pt_, "a", uploads=[upload("client.txt")])
    own = Attachment.objects.for_organization(pt_["org"]).get(object_id=str(mine.pk))
    staff = incidents.add_evidence(mine, upload("tech.txt", b"internal photo"), actor=pt_["ops"].user)
    ca, cb, cbeta, ops = (web(pt_[k].user) for k in ("a", "b", "beta_client", "ops"))
    assert ca.get(f"/app/files/{own.pk}/download/").status_code == 200
    assert ca.get(f"/app/files/{staff.pk}/download/").status_code == 404  # staff evidence is not the client's
    assert cb.get(f"/app/files/{own.pk}/download/").status_code == 404
    assert cbeta.get(f"/app/files/{own.pk}/download/").status_code == 404
    assert ops.get(f"/app/files/{own.pk}/download/").status_code == 200
    assert ops.get(f"/app/files/{staff.pk}/download/").status_code == 200
    assert Client().get(f"/app/files/{own.pk}/download/").status_code == 302


def test_client_projection_hides_internal_data(pt_):
    sr = submit(pt_, "a")
    incidents.transition(sr, action="triage", actor=pt_["ops"].user, reason="internal triage note: contractor error")
    body = api(pt_["a"].user, pt_["org"]).get(f"/api/v1/portal/requests/{sr.pk}/").json()
    assert set(body) == {"id", "number", "kind", "title", "description", "severity", "asset", "asset_tag",
                         "asset_name", "status", "client_status", "visit", "created_at", "resolved_at",
                         "confirmed_at", "closed_at"}
    assert "internal triage note" not in str(body)
    html = web(pt_["a"].user).get(f"/app/portal/requests/{sr.pk}/").content.decode()
    assert "internal triage note" not in html and "Under review" in html


def test_privileged_endpoints_are_closed_to_clients(pt_):
    sr = submit(pt_, "a")
    ca = api(pt_["a"].user, pt_["org"])
    for url in ("/api/v1/service-requests/", f"/api/v1/service-requests/{sr.pk}/", "/api/v1/work-orders/",
                "/api/v1/assets/", "/api/v1/parts/", "/api/v1/stock-movements/", "/api/v1/sla-profiles/",
                "/api/v1/sla-trackings/", "/api/v1/audit-logs/", "/api/v1/sites/", "/api/v1/members/",
                "/api/v1/maintenance-plans/", "/api/v1/coverage-agreements/", "/api/v1/asset-identifiers/",
                "/api/v1/portal-accounts/"):
        assert ca.get(url).status_code == 403, url
    for url in ("/api/v1/inspections/", "/api/v1/findings/"):  # self-scoping reads: the selector yields nothing
        r = ca.get(url)
        assert r.status_code == 200 and r.json()["results"] == [], url
    for verb in ("triage", "approve", "close", "confirm"):
        r = ca.post(f"/api/v1/service-requests/{sr.pk}/{verb}/", {}, format="json")
        assert r.status_code in (403, 404, 405), (verb, r.status_code)
    assert ca.post("/api/v1/work-orders/", {"asset": str(pt_["asset"].pk), "title": "x"}, format="json"
                   ).status_code == 403
    assert ca.post("/api/v1/portal-accounts/", {"membership": str(pt_["a"].pk)}, format="json").status_code == 403
    sr.refresh_from_db()
    assert sr.status == "NEW"
    for url in ("/app/incidents/", "/app/work-orders/", "/app/inventory/parts/", "/app/sla/", "/app/audit/",
                "/app/portal/accounts/", f"/app/incidents/{sr.pk}/", "/app/assets/"):
        assert web(pt_["a"].user).get(url).status_code in (403, 404), url


# --- confirmation and closure rules ------------------------------------------------------------------------------


def test_cannot_confirm_or_reopen_before_resolution(pt_):
    sr = submit(pt_, "a")
    with pytest.raises(Exception) as e:
        portal.confirm(pt_["a"], sr)
    assert getattr(e.value, "code", "") == "invalid_transition"
    with pytest.raises(InvalidTransition):
        portal.reopen(pt_["a"], sr, reason="not yet fixed")
    sr.refresh_from_db()
    assert sr.status == "NEW" and sr.confirmed_at is None
    ca = api(pt_["a"].user, pt_["org"])
    assert ca.post(f"/api/v1/portal/requests/{sr.pk}/confirm/").status_code in (400, 409)
    assert ca.post(f"/api/v1/portal/requests/{sr.pk}/close/").status_code == 404  # no such client action


def _work_through(pt_, sr):
    """Staff side: triage, approve and create the work order from the request."""
    incidents.transition(sr, action="triage", actor=pt_["ops"].user)
    incidents.transition(sr, action="approve", actor=pt_["ops"].user)
    t0 = timezone.now() + timedelta(days=1)
    return incidents.create_work_order_for_request(sr, actor=pt_["planner"].user, membership=pt_["planner"],
                                                   planned_start=t0, planned_end=t0 + timedelta(hours=3))


def test_full_client_journey_over_ui_and_backend(pt_):
    p = pt_
    ca = web(p["a"].user)
    assert ca.get("/app/portal/").status_code == 200
    r = ca.post("/app/portal/requests/new/", {"asset": str(p["asset"].pk), "kind": "INCIDENT", "title": "Press stuck",
                                              "description": "Will not move", "urgency": "HIGH",
                                              "files": upload("press.txt")})
    assert r.status_code == 302, r.context["form"].errors if r.context else r
    sr = ServiceRequest.objects.for_organization(p["org"]).get(title="Press stuck")
    assert r["Location"] == f"/app/portal/requests/{sr.pk}/" and sr.reported_by == p["a"]
    assert "Received" in ca.get(r["Location"]).content.decode()
    wo = _work_through(p, sr)
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"
    page = ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    assert "Scheduled visit" in page and "To be confirmed" in page  # no technician shown before dispatch
    wo = step(wo, "plan", p, "planner", planned_start=wo.planned_start, planned_end=wo.planned_end)
    wo = step(wo, "assign", p, "planner", technician=p["tech"])
    assert p["tech"].user.display_name not in ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    wo = step(wo, "dispatch", p, "planner")
    assert p["tech"].user.display_name in ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    wo = step(wo, "start", p, "tech")
    sr.refresh_from_db()
    assert sr.status == "IN_SERVICE" and "Work in progress" in ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    assert "confirm-card" not in ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    ca.post(f"/app/portal/requests/{sr.pk}/confirm/")  # premature: rejected by the state machine
    sr.refresh_from_db()
    assert sr.status == "IN_SERVICE"
    finish_work(wo, p)
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"
    page = ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    assert "confirm-card" in page and "Resolved: please confirm" in page
    assert Notification.objects.for_organization(p["org"]).filter(recipient=p["a"].user,
                                                                  title__contains="resolved").exists()
    ca.post(f"/app/portal/requests/{sr.pk}/confirm/")
    sr.refresh_from_db()
    assert sr.status == "CONFIRMED" and sr.confirmed_at is not None
    assert "closing" in ca.get(f"/app/portal/requests/{sr.pk}/").content.decode().lower()
    assert api(p["a"].user, p["org"]).post(f"/api/v1/service-requests/{sr.pk}/transition/", {"action": "close"},
                                           format="json").status_code == 403
    incidents.transition(sr, action="close", actor=p["svc"].user)
    sr.refresh_from_db()
    assert sr.status == "CLOSED"
    assert "Closed" in ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    for action in ("portal.request_submitted", "portal.request_confirmed", "incident.created"):
        assert AuditLog.objects.filter(action=action, target_id=str(sr.pk)).exists(), action
    with pytest.raises(Conflict):
        portal.add_attachment(p["a"], sr, upload())  # closed requests are locked


def test_reopen_returns_request_to_staff(pt_):
    sr = submit(pt_, "a")
    wo = _work_through(pt_, sr)
    wo = step(wo, "plan", pt_, "planner", planned_start=wo.planned_start, planned_end=wo.planned_end)
    wo = step(wo, "assign", pt_, "planner", technician=pt_["tech"])
    wo = step(wo, "dispatch", pt_, "planner")
    wo = step(wo, "start", pt_, "tech")
    finish_work(wo, pt_)
    ca = web(pt_["a"].user)
    assert ca.post(f"/app/portal/requests/{sr.pk}/reopen/", {"reason": ""}).status_code == 400
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"
    assert ca.post(f"/app/portal/requests/{sr.pk}/reopen/",
                   {"reason": "Still leaking after the repair"}).status_code == 302
    sr.refresh_from_db()
    assert sr.status == "APPROVED"
    assert "Still leaking" in ca.get(f"/app/portal/requests/{sr.pk}/").content.decode()
    assert AuditLog.objects.filter(action="portal.request_reopened", target_id=str(sr.pk)).exists()


def test_rejected_request_shows_reason_to_client(pt_):
    sr = submit(pt_, "a")
    incidents.transition(sr, action="triage", actor=pt_["ops"].user)
    incidents.transition(sr, action="reject", reason="Outside the service contract", actor=pt_["ops"].user)
    html = web(pt_["a"].user).get(f"/app/portal/requests/{sr.pk}/").content.decode()
    assert "Declined" in html and "Outside the service contract" in html


# --- UI and staff screens ----------------------------------------------------------------------------------------


def test_portal_pages_render_for_client_and_are_mobile_ready(pt_):
    sr = submit(pt_, "a")
    ca = web(pt_["a"].user)
    for url in ("/app/portal/", "/app/portal/requests/", "/app/portal/requests/new/", f"/app/portal/requests/{sr.pk}/",
                "/app/portal/requests/?stage=open&q=leak"):
        r = ca.get(url)
        assert r.status_code == 200, url
        html = r.content.decode()
        assert 'name="viewport"' in html and "FieldOps Nexus" in html
    assert 'id="count-open">1<' in ca.get("/app/portal/").content.decode()
    assert ca.post("/app/portal/requests/new/", {"asset": str(pt_["asset2"].pk), "kind": "INCIDENT",
                                                 "title": "Not my asset", "urgency": "LOW"}).status_code == 400
    assert ServiceRequest.objects.for_organization(pt_["org"]).count() == 1
    portal.set_account_active(pt_["acct_a"], False, actor=pt_["svc"].user)
    assert "not been enabled" in ca.get("/app/portal/requests/new/").content.decode()
    assert ca.post("/app/portal/requests/new/", {"asset": str(pt_["asset"].pk), "kind": "INCIDENT", "title": "Try",
                                                 "urgency": "LOW"}).status_code == 400


def test_client_only_users_land_in_the_portal_and_staff_do_not(pt_):
    home = web(pt_["a"].user).get("/app/")
    assert home.status_code == 302 and home["Location"] == "/app/portal/"
    assert web(pt_["ops"].user).get("/app/").status_code == 200


def test_staff_account_screens_and_api(pt_):
    svc = web(pt_["svc"].user)
    assert svc.get("/app/portal/accounts/").status_code == 200
    assert svc.get(f"/app/portal/accounts/{pt_['acct_a'].pk}/").status_code == 200
    assert web(pt_["tech"].user).get("/app/portal/accounts/").status_code == 403
    svc.post(f"/app/portal/accounts/{pt_['acct_a'].pk}/", {"action": "grant", "asset": str(pt_["asset2"].pk)})
    assert PortalAssetGrant.objects.for_organization(pt_["org"]).filter(account=pt_["acct_a"]).count() == 2
    svc.post(f"/app/portal/accounts/{pt_['acct_a'].pk}/", {"action": "revoke", "asset": str(pt_["asset2"].pk)})
    assert PortalAssetGrant.objects.for_organization(pt_["org"]).filter(account=pt_["acct_a"]).count() == 1
    svc.post(f"/app/portal/accounts/{pt_['acct_a'].pk}/", {"action": "disable"})
    pt_["acct_a"].refresh_from_db()
    assert not pt_["acct_a"].is_active
    other = PortalAccount.objects.for_organization(pt_["org_b"]).get()
    assert svc.get(f"/app/portal/accounts/{other.pk}/").status_code == 404
    assert svc.post(f"/app/portal/accounts/{other.pk}/", {"action": "disable"}).status_code == 404
    other.refresh_from_db()
    assert other.is_active
    sa = api(pt_["svc"].user, pt_["org"])
    assert len(sa.get("/api/v1/portal-accounts/").json()["results"]) == 2
    assert sa.get(f"/api/v1/portal-accounts/{other.pk}/").status_code == 404
    assert sa.post(f"/api/v1/portal-accounts/{other.pk}/grant/", {"asset": str(pt_["asset"].pk)}, format="json"
                   ).status_code == 404
    assert sa.post(f"/api/v1/portal-accounts/{pt_['acct_b'].pk}/grant/", {"asset": str(pt_["b_asset"].pk)},
                   format="json").status_code == 404
    assert api(pt_["tech"].user, pt_["org"]).get("/api/v1/portal-accounts/").status_code == 403


def test_api_client_submission_and_attachment(pt_):
    ca = api(pt_["a"].user, pt_["org"])
    r = ca.post("/api/v1/portal/requests/", {"asset": str(pt_["asset"].pk), "title": "Motor hot", "urgency": "MEDIUM",
                                             "files": [upload("one.txt")]}, format="multipart")
    assert r.status_code == 201, r.json()
    rid = r.json()["id"]
    assert Attachment.objects.for_organization(pt_["org"]).filter(object_id=rid).count() == 1
    r = ca.post(f"/api/v1/portal/requests/{rid}/attachments/", {"file": upload("two.txt", b"more")},
                format="multipart")
    assert r.status_code == 201
    assert Attachment.objects.for_organization(pt_["org"]).filter(object_id=rid).count() == 2
    assert ca.post(f"/api/v1/portal/requests/{rid}/attachments/", {}, format="multipart").status_code == 400
    assert ca.post("/api/v1/portal/requests/", {"asset": str(pt_["asset"].pk), "title": "x", "urgency": "CRITICAL"},
                   format="json").status_code == 400
    assert APIClient().get("/api/v1/portal/requests/").status_code in (401, 403)
