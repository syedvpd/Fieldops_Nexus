"""M11 REST API and HTML: RBAC, tenant isolation, site scope, IDOR, validation, metrics, panels on request / work
order pages and the real buttons (acknowledge, run check, profile / target / rule forms)."""
import uuid

import pytest
from django.test import Client

from apps.audit.models import AuditLog
from apps.incidents import services as incidents
from apps.sla import services as sla
from apps.sla.models import SLABreach, SLATracking
from tests.pm_support import T0, freeze
from tests.test_m11_sla import at

pytestmark = pytest.mark.django_db


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def ctx(sla_, as_user, org_b, make_member, make_site, make_asset, monkeypatch):
    freeze(monkeypatch, T0)
    s = sla_
    b_svc = make_member(org_b, "svc@beta.test", "service_manager")
    b_site = make_site(org_b, "B1")
    b_asset = make_asset(org_b, b_site, "B-PUMP")
    b_profile = sla.create_profile(org_b, name="Beta SLA", applies_to="REQUEST", actor=b_svc.user)
    sla.set_target(b_profile, priority="HIGH", response_minutes=10, resolution_minutes=20, actor=b_svc.user)
    b_tech = make_member(org_b, "tech@beta.test", "technician")
    b_sr = incidents.create_request(org_b, asset=b_asset, reporter=b_tech, title="Beta leak", severity="HIGH",
                                    actor=b_tech.user)
    sr = incidents.create_request(s["org"], asset=s["asset"], reporter=s["tech"], title="Alpha leak",
                                  severity="HIGH", actor=s["tech"].user)
    sr2 = incidents.create_request(s["org"], asset=s["asset2"], reporter=s["tech"], title="Alpha fan",
                                   severity="HIGH", actor=s["tech"].user)
    s.update(sr=sr, sr2=sr2, b_svc=b_svc, b_profile=b_profile, b_sr=b_sr, b_tracking=SLATracking.objects.get(
        request=b_sr), cb=as_user(b_svc.user, org_b),
        c={k: as_user(s[k].user, s["org"]) for k in ("svc", "ops", "sup", "tech", "planner", "reader")},
        cl={k: client_for(s[k].user) for k in ("svc", "ops", "sup", "tech", "planner", "reader")})
    return s


def err(r):
    return r.json()["error"]["code"]


def breach_now(ctx, monkeypatch, minutes=40):
    freeze(monkeypatch, at(minutes))
    return sla.process_organization(ctx["org"])


# --- API: RBAC / tenant / IDOR -----------------------------------------------------------------------------------------


def test_view_permissions_and_site_scope(ctx, make_scoped_member, as_user):
    c = ctx["c"]
    assert c["tech"].get("/api/v1/sla-trackings/").status_code == 403  # technicians have no sla.view
    for who in ("svc", "ops", "sup", "planner"):
        assert c[who].get("/api/v1/sla-trackings/").status_code == 200, who
    r = c["ops"].get("/api/v1/sla-trackings/")
    assert r.status_code == 200 and r.json()["count"] == 2
    scoped = make_scoped_member(ctx["org"], "ops2@alpha.test", "operations_manager", [ctx["site2"]])
    r = as_user(scoped.user, ctx["org"]).get("/api/v1/sla-trackings/")
    assert [row["subject_number"] for row in r.json()["results"]] == [ctx["sr2"].number]
    own = SLATracking.objects.get(request=ctx["sr"])
    assert as_user(scoped.user, ctx["org"]).get(f"/api/v1/sla-trackings/{own.pk}/").status_code == 404


def test_cross_tenant_and_unknown_ids_are_404(ctx):
    cb, ca = ctx["cb"], ctx["c"]["svc"]
    own = SLATracking.objects.get(request=ctx["sr"])
    assert cb.get(f"/api/v1/sla-trackings/{own.pk}/").status_code == 404
    assert ca.get(f"/api/v1/sla-trackings/{ctx['b_tracking'].pk}/").status_code == 404
    assert ca.get(f"/api/v1/sla-profiles/{ctx['b_profile'].pk}/").status_code == 404
    assert ca.get(f"/api/v1/sla-trackings/{uuid.uuid4()}/").status_code == 404
    assert ca.post(f"/api/v1/sla-profiles/{ctx['b_profile'].pk}/targets/", {
        "priority": "LOW", "response_minutes": 1, "resolution_minutes": 2}, format="json").status_code == 404
    assert not ctx["b_profile"].targets.filter(priority="LOW").exists()
    assert cb.post(f"/api/v1/sla-profiles/{ctx['profile'].pk}/deactivate/").status_code == 404
    ctx["profile"].refresh_from_db()
    assert ctx["profile"].is_active


def test_configuration_needs_sla_manage(ctx):
    c = ctx["c"]
    body = {"name": "New one", "applies_to": "WORK_ORDER"}
    for who in ("ops", "sup", "planner", "tech"):
        assert c[who].post("/api/v1/sla-profiles/", body, format="json").status_code == 403, who
    r = c["svc"].post("/api/v1/sla-profiles/", body, format="json")
    assert r.status_code == 201, r.content
    assert c["svc"].post("/api/v1/sla-profiles/", body, format="json").status_code == 409
    r = c["svc"].post("/api/v1/sla-profiles/", {"name": "x", "applies_to": "REQUEST"}, format="json")
    assert r.status_code == 400 and err(r) == "name_required"


def test_target_and_rule_api_validation_and_audit(ctx):
    svc, p = ctx["c"]["svc"], ctx["profile"]
    r = svc.post(f"/api/v1/sla-profiles/{p.pk}/targets/", {
        "priority": "CRITICAL", "response_minutes": 60, "resolution_minutes": 30}, format="json")
    assert r.status_code == 400 and err(r) == "resolution_before_response"
    r = svc.post(f"/api/v1/sla-profiles/{p.pk}/targets/", {
        "priority": "CRITICAL", "response_minutes": 5, "resolution_minutes": 30}, format="json")
    assert r.status_code == 200
    assert AuditLog.objects.filter(action="sla.target_set").count() >= 2
    r = svc.post(f"/api/v1/sla-profiles/{p.pk}/rules/", {
        "target_kind": "RESPONSE", "trigger": "ESCALATION", "after_minutes": 10,
        "notify_role": str(ctx["ops_role"].pk)}, format="json")
    assert r.status_code == 200
    r = svc.post(f"/api/v1/sla-profiles/{p.pk}/rules/", {
        "target_kind": "RESPONSE", "trigger": "ESCALATION", "after_minutes": 11,
        "notify_role": str(ctx["b_profile"].pk)}, format="json")
    assert r.status_code == 404  # a foreign / unknown role is not found
    r = svc.post(f"/api/v1/sla-profiles/{p.pk}/targets/remove/", {"priority": "CRITICAL"}, format="json")
    assert r.status_code == 200 and not p.targets.filter(priority="CRITICAL").exists()


# --- API: monitor, breaches, metrics ------------------------------------------------------------------------------------


def test_process_acknowledge_and_metrics_over_http(ctx, monkeypatch):
    c = ctx["c"]
    freeze(monkeypatch, at(40))
    assert c["ops"].post("/api/v1/sla-trackings/process/").status_code == 403
    r = c["svc"].post("/api/v1/sla-trackings/process/")
    assert r.status_code == 200 and r.json()["breaches"] == 2
    assert c["svc"].post("/api/v1/sla-trackings/process/").json()["breaches"] == 0  # idempotent
    rows = c["ops"].get("/api/v1/sla-breaches/?status=OPEN").json()["results"]
    assert len(rows) == 2 and {x["site_code"] for x in rows} == {"A1", "A2"}
    pk = rows[0]["id"]
    assert c["sup"].post(f"/api/v1/sla-breaches/{pk}/acknowledge/").status_code == 403
    assert c["ops"].post(f"/api/v1/sla-breaches/{pk}/acknowledge/").status_code == 200
    assert c["ops"].post(f"/api/v1/sla-breaches/{pk}/acknowledge/").status_code == 409
    assert ctx["cb"].post(f"/api/v1/sla-breaches/{pk}/acknowledge/").status_code == 404
    m = c["ops"].get("/api/v1/sla-metrics/").json()
    assert m["trackings"] == 2 and m["breaches_open"] == 2 and m["response"]["breached"] == 2
    assert m["breaches_open_by_priority"] == {"response": {"HIGH": 2}}
    assert ctx["cb"].get("/api/v1/sla-metrics/").json()["trackings"] == 1  # only its own tenant
    assert c["tech"].get("/api/v1/sla-metrics/").status_code == 403


def test_invalid_filters_are_empty_not_errors(ctx):
    r = ctx["c"]["ops"].get("/api/v1/sla-trackings/?status=BOGUS&site=not-a-uuid")
    assert r.status_code == 200 and r.json()["count"] == 0


# --- HTML ------------------------------------------------------------------------------------------------------------------


def test_pages_render_and_panels_show_on_request_and_work_order(ctx, monkeypatch):
    c = ctx["cl"]["svc"]
    t = SLATracking.objects.get(request=ctx["sr"])
    pages = {"/app/sla/trackings/": "Alpha leak", f"/app/sla/trackings/{t.pk}/": "Timeline", "/app/sla/breaches/": "SLA breaches",
             "/app/sla/profiles/": "Incident SLA", "/app/sla/profiles/new/": "Pause the timers",
             f"/app/sla/profiles/{ctx['profile'].pk}/": "Escalation rules",
             f"/app/sla/profiles/{ctx['profile'].pk}/edit/": "Edit"}
    for url, text in pages.items():
        r = c.get(url)
        assert r.status_code == 200 and text in r.content.decode(), url
    r = ctx["cl"]["ops"].get(f"/app/incidents/{ctx['sr'].pk}/")
    assert r.status_code == 200 and 'id="sla-panel"' in r.content.decode()
    assert 'id="sla-panel"' not in ctx["cl"]["tech"].get(f"/app/incidents/{ctx['sr'].pk}/").content.decode()


def test_forbidden_roles_and_foreign_objects_on_pages(ctx):
    assert ctx["cl"]["tech"].get("/app/sla/trackings/").status_code == 403
    for who in ("ops", "sup", "planner"):
        assert ctx["cl"][who].get("/app/sla/profiles/").status_code == 403, who
        assert ctx["cl"][who].post("/app/sla/process/").status_code == 403, who
    assert Client().get("/app/sla/trackings/").status_code in (302, 401)
    c = ctx["cl"]["svc"]
    assert c.get(f"/app/sla/trackings/{ctx['b_tracking'].pk}/").status_code == 404
    assert c.get(f"/app/sla/profiles/{ctx['b_profile'].pk}/").status_code == 404
    assert c.post(f"/app/sla/profiles/{ctx['b_profile'].pk}/active/", {"active": "0"}).status_code == 404
    ctx["b_profile"].refresh_from_db()
    assert ctx["b_profile"].is_active


def test_run_check_and_acknowledge_buttons_persist_and_audit(ctx, monkeypatch):
    freeze(monkeypatch, at(40))
    r = ctx["cl"]["svc"].post("/app/sla/process/")
    assert r.status_code == 302 and SLABreach.objects.count() == 2
    b = SLABreach.objects.filter(site=ctx["site"]).get()
    assert ctx["cl"]["sup"].post(f"/app/sla/breaches/{b.pk}/acknowledge/").status_code == 403
    r = ctx["cl"]["ops"].post(f"/app/sla/breaches/{b.pk}/acknowledge/", {"next": "//evil.example/"})
    assert r.status_code == 302 and r["Location"] == "/app/sla/breaches/"  # no open redirect
    b.refresh_from_db()
    assert b.status == "ACKNOWLEDGED" and AuditLog.objects.filter(action="sla.breach_acknowledged").count() == 1
    page = ctx["cl"]["ops"].get("/app/sla/breaches/").content.decode()
    assert "Acknowledged" in page


def test_profile_target_and_rule_forms_end_to_end(ctx):
    c = ctx["cl"]["svc"]
    r = c.post("/app/sla/profiles/new/", {"name": "Work order SLA", "applies_to": "WORK_ORDER",
                                          "pause_states": ["WORK_ORDER:ON_HOLD"]})
    assert r.status_code == 302
    p = sla.SLAProfile.objects.get(name="Work order SLA")
    assert p.pause_states == ["WORK_ORDER:ON_HOLD"]
    assert c.post("/app/sla/profiles/new/", {"name": "Work order SLA", "applies_to": "WORK_ORDER"}).status_code == 400
    c.post(f"/app/sla/profiles/{p.pk}/targets/", {"priority": "URGENT", "response_minutes": 15,
                                                  "resolution_minutes": 60, "warning_percent": 75})
    t = p.targets.get(priority="URGENT")
    assert (t.response_minutes, t.resolution_minutes, t.warning_percent) == (15, 60, 75)
    c.post(f"/app/sla/profiles/{p.pk}/targets/", {"priority": "URGENT", "response_minutes": 90,
                                                  "resolution_minutes": 60, "warning_percent": 75})
    t.refresh_from_db()
    assert t.response_minutes == 15  # invalid input changed nothing
    c.post(f"/app/sla/profiles/{p.pk}/rules/", {"target_kind": "RESOLUTION", "trigger": "BREACH", "level": 1,
                                                "notify_role": str(ctx["ops_role"].pk)})
    rule = p.rules.get()
    c.post(f"/app/sla/profiles/{p.pk}/rules/{rule.pk}/remove/")
    assert p.rules.count() == 0
    c.post(f"/app/sla/profiles/{p.pk}/targets/{t.pk}/remove/")
    assert p.targets.count() == 0
    c.post(f"/app/sla/profiles/{p.pk}/active/", {"active": "0"})
    p.refresh_from_db()
    assert not p.is_active
    for action in ("sla.profile_created", "sla.target_set", "sla.rule_created", "sla.rule_deleted",
                   "sla.target_removed", "sla.profile_deactivated"):
        assert AuditLog.objects.filter(action=action).exists(), action
    # a foreign role id in the rule form is rejected by the form's tenant-scoped queryset
    p2 = sla.SLAProfile.objects.get(name="Incident SLA")
    before = p2.rules.count()
    c.post(f"/app/sla/profiles/{p2.pk}/rules/", {"target_kind": "RESPONSE", "trigger": "BREACH", "level": 1,
                                                 "notify_role": str(uuid.uuid4())})
    assert p2.rules.count() == before
