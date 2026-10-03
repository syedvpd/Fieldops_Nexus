"""Non-vacuous two-tenant verification after M10-M15: every route is first proven to WORK for its owner (positive
control, with real fixtures), then attacked with the other tenant's identities in both directions; writes are
checked against unchanged database state."""
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.contracts import services as contracts
from apps.files.models import Attachment
from apps.identification import services as idn
from apps.incidents.models import ServiceRequest
from apps.inventory import services as inv
from apps.maintenance import services as pm
from apps.portal import services as portal
from apps.workorders import services as wos
from apps.workorders.models import WorkOrder

pytestmark = pytest.mark.django_db


def api(user, org):
    c = APIClient()
    c.force_authenticate(user=user)
    c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


def web(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def world(org_a, org_b, make_site, make_asset, make_member):
    out = {}
    for tag, org in (("a", org_a), ("b", org_b)):
        site = make_site(org, f"{tag.upper()}S1")
        asset = make_asset(org, site, f"{tag.upper()}-PUMP")
        mgr = make_member(org, f"mgr@{tag}.world", "asset_manager")
        ops = make_member(org, f"ops@{tag}.world", "operations_manager")
        svc = make_member(org, f"svc@{tag}.world", "service_manager")
        stores = make_member(org, f"stores@{tag}.world", "stores_manager")
        auditor = make_member(org, f"aud@{tag}.world", "auditor")
        client = make_member(org, f"client@{tag}.world", "client_requester")
        acct = portal.enable_account(org, client, actor=svc.user)
        portal.grant_asset(acct, asset, actor=svc.user)
        sr = portal.submit_request(client, asset=asset, title=f"{tag} client request",
                                   uploads=[SimpleUploadedFile("evidence.txt", f"{tag} evidence".encode())])
        wo = wos.create_work_order(org, asset=asset, actor=ops.user, title=f"{tag} order", work_type="CORRECTIVE")
        part = inv.create_part(org, part_number=f"{tag}-PART", name=f"{tag} part", actor=stores.user)
        wh = inv.create_warehouse(org, site=site, code=f"{tag}WH", name=f"{tag} store", actor=stores.user)
        prov = contracts.create_provider(org, name=f"{tag} provider", actor=mgr.user)
        ag = contracts.create_agreement(org, kind="AMC", reference=f"{tag}-AMC", title="AMC", provider=prov, site=site,
                                        start_date=date(2026, 1, 1), end_date=date(2030, 1, 1), assets=[asset],
                                        actor=mgr.user)
        ident = idn.generate(asset, "QR", actor=mgr.user)
        plan = pm.create_plan(org, asset=asset, name=f"{tag} plan", actor=ops.user)
        att = Attachment.objects.for_organization(org).get(object_id=str(sr.pk))
        out[tag] = dict(org=org, site=site, asset=asset, mgr=mgr, ops=ops, svc=svc, stores=stores, auditor=auditor,
                        client=client, acct=acct, sr=sr, wo=wo, part=part, wh=wh, prov=prov, ag=ag, ident=ident,
                        plan=plan, att=att)
    return out


# rows legitimately written in the victim organization by the test itself (its own login, the extra work order)
NOISE = ("auth.login", "work_order.created", "sla.tracking_started")
API_GET = ["/api/v1/assets/{asset}/", "/api/v1/work-orders/{wo}/", "/api/v1/service-requests/{sr}/",
           "/api/v1/parts/{part}/", "/api/v1/warehouses/{wh}/", "/api/v1/coverage-agreements/{ag}/",
           "/api/v1/contract-providers/{prov}/", "/api/v1/asset-identifiers/{ident}/",
           "/api/v1/maintenance-plans/{plan}/", "/api/v1/sites/{site}/", "/api/v1/portal-accounts/{acct}/"]
UI_GET = ["/app/assets/{asset}/", "/app/work-orders/{wo}/", "/app/incidents/{sr}/",
          "/app/contracts/agreements/{ag}/", "/app/maintenance/plans/{plan}/",
          "/app/contracts/assets/{asset}/panel/", "/app/identification/assets/{asset}/panel/",
          "/app/identification/assets/{asset}/label/", "/app/contracts/work-orders/{wo}/panel/",
          "/app/portal/accounts/{acct}/", "/app/files/{att}/download/"]


def ids(side):
    return {k: str(v.pk) for k, v in side.items() if hasattr(v, "pk")}


def test_positive_controls_every_route_works_for_its_owner(world):
    """If the sweep below were attacking dead URLs it would 'pass' vacuously; prove every URL is live first."""
    for tag in ("a", "b"):
        w = world[tag]
        i = ids(w)
        mgr_api, svc_api = api(w["mgr"].user, w["org"]), api(w["svc"].user, w["org"])
        ops_web, svc_web = web(w["ops"].user), web(w["svc"].user)
        for t in API_GET:
            who = svc_api if "portal-accounts" in t else mgr_api
            if "work-orders" in t or "service-requests" in t or "maintenance" in t or "parts" in t or "warehouses" in t:
                who = api(w["ops"].user, w["org"])
            assert who.get(t.format(**i)).status_code == 200, t
        for t in UI_GET:
            who = svc_web if "portal/accounts" in t else (web(w["mgr"].user) if "contracts" in t or "identif" in t
                                                          or "/assets/" in t else ops_web)
            assert who.get(t.format(**i)).status_code == 200, t
        assert web(w["client"].user).get(f"/app/portal/requests/{i['sr']}/").status_code == 200
        assert web(w["client"].user).get(f"/app/files/{i['att']}/download/").status_code == 200


def test_attacks_in_both_directions_all_fail_and_change_nothing(world):
    attacks = 0
    for mine, theirs in (("a", "b"), ("b", "a")):
        me, other = world[mine], world[theirs]
        i = ids(other)
        before = {
            "wo": WorkOrder.objects.get(pk=other["wo"].pk).status,
            "sr": ServiceRequest.objects.get(pk=other["sr"].pk).status,
            "ag": other["ag"].__class__.objects.get(pk=other["ag"].pk).is_active,
            "ident": other["ident"].__class__.objects.get(pk=other["ident"].pk).is_active,
            "acct": other["acct"].__class__.objects.get(pk=other["acct"].pk).is_active,
            "rows": AuditLog.objects.filter(organization=other["org"]).exclude(action__in=NOISE).count(),
        }
        actors = {k: api(me[k].user, me["org"]) for k in ("mgr", "ops", "svc", "stores", "auditor", "client")}
        # GET every API route with every internal persona of the attacking tenant
        for t in API_GET:
            for k in ("mgr", "ops", "svc", "stores", "auditor"):
                r = actors[k].get(t.format(**i))
                assert r.status_code in (403, 404), (mine, k, t, r.status_code)
                attacks += 1
        # HTML routes
        for t in UI_GET:
            for k in ("mgr", "ops", "svc", "auditor"):
                r = web(me[k].user).get(t.format(**i))
                assert r.status_code in (403, 404), (mine, k, t, r.status_code)
                attacks += 1
        # portal: the other tenant's client request, files, actions
        c_api, c_web = actors["client"], web(me["client"].user)
        for url in (f"/api/v1/portal/requests/{i['sr']}/", f"/api/v1/client/requests/{i['sr']}/status/"):
            assert c_api.get(url).status_code == 404
        for verb in ("confirm", "reopen", "attachments"):
            assert c_api.post(f"/api/v1/portal/requests/{i['sr']}/{verb}/", {"reason": "x"}, format="json"
                              ).status_code == 404
        assert c_web.get(f"/app/portal/requests/{i['sr']}/").status_code == 404
        assert c_web.get(f"/app/files/{i['att']}/download/").status_code == 404
        assert c_web.post(f"/app/portal/requests/{i['sr']}/confirm/").status_code == 404
        attacks += 8
        # QR / scan
        assert idn.resolve(me["mgr"].user, other["ident"].token, me["mgr"]).outcome == "UNKNOWN"
        assert web(me["mgr"].user).get(f"/app/s/{other['ident'].token}/").status_code == 404
        assert actors["mgr"].post("/api/v1/scan/resolve/", {"token": other["ident"].token}, format="json"
                                  ).status_code == 404
        attacks += 3
        # audit: foreign rows by id, in filters and in exports
        foreign = list(AuditLog.objects.filter(organization=other["org"]).values_list("pk", flat=True)[:5])
        assert foreign
        for pk in foreign:
            assert actors["auditor"].get(f"/api/v1/audit-logs/{pk}/").status_code == 404
            assert web(me["auditor"].user).get(f"/app/audit/{pk}/").status_code == 404
            attacks += 2
        listing = actors["auditor"].get("/api/v1/audit-logs/", {"page_size": 500}).json()["results"]
        assert not ({str(p) for p in foreign} & {r["id"] for r in listing})
        export = web(me["auditor"].user).get("/app/audit/export/?format=csv").content.decode("utf-8-sig")
        for pk in (other["wo"].pk, other["sr"].pk, other["asset"].pk):
            assert str(pk) not in export
        # dashboards: foreign site is invisible; totals do not move when the other tenant adds data
        assert actors["ops"].get("/api/v1/dashboards/operations/", {"site": i["site"]}).status_code == 404
        totals = actors["ops"].get("/api/v1/dashboards/operations/").json()["data"]["kpis"]
        wos.create_work_order(other["org"], asset=other["asset"], actor=other["ops"].user, title="extra",
                              work_type="CORRECTIVE")
        assert actors["ops"].get("/api/v1/dashboards/operations/").json()["data"]["kpis"] == totals
        attacks += 3
        # representative workflow writes against the other tenant's objects
        writes = [
            (actors["ops"], "post", f"/api/v1/work-orders/{i['wo']}/transition/", {"action": "cancel", "reason": "x"}),
            (actors["ops"], "post", f"/api/v1/work-orders/{i['wo']}/assign/", {"technician": str(me["ops"].pk)}),
            (actors["mgr"], "patch", f"/api/v1/assets/{i['asset']}/", {"name": "hijacked"}),
            (actors["mgr"], "post", f"/api/v1/coverage-agreements/{i['ag']}/deactivate/", {"reason": "x"}),
            (actors["mgr"], "post", f"/api/v1/asset-identifiers/{i['ident']}/revoke/", {"reason": "x"}),
            (actors["svc"], "post", f"/api/v1/portal-accounts/{i['acct']}/disable/", {}),
            (actors["svc"], "post", f"/api/v1/portal-accounts/{i['acct']}/grant/", {"asset": str(me["asset"].pk)}),
            (actors["ops"], "post", f"/api/v1/service-requests/{i['sr']}/transition/", {"action": "triage"}),
            (actors["stores"], "post", f"/api/v1/parts/{i['part']}/deactivate/", {}),
            (actors["ops"], "post", f"/api/v1/maintenance-plans/{i['plan']}/disable/", {}),
        ]
        for client_, verb, url, body in writes:
            r = getattr(client_, verb)(url, body, format="json")
            assert r.status_code in (403, 404), (mine, verb, url, r.status_code)
            attacks += 1
        # nothing changed
        assert WorkOrder.objects.get(pk=other["wo"].pk).status == before["wo"]
        assert ServiceRequest.objects.get(pk=other["sr"].pk).status == before["sr"]
        assert other["ag"].__class__.objects.get(pk=other["ag"].pk).is_active == before["ag"]
        assert other["ident"].__class__.objects.get(pk=other["ident"].pk).is_active == before["ident"]
        assert other["acct"].__class__.objects.get(pk=other["acct"].pk).is_active == before["acct"]
        assert other["asset"].__class__.objects.get(pk=other["asset"].pk).name == other["asset"].name
        # the attacks produced no audit rows in the victim organization (other than the one dashboard write above)
        assert AuditLog.objects.filter(organization=other["org"]).exclude(action__in=NOISE).count() == before["rows"]
    assert attacks >= 150, f"sweep too small to be meaningful: {attacks}"


def test_cross_tenant_header_selection_is_refused(world):
    a, b = world["a"], world["b"]
    c = APIClient()
    c.force_authenticate(user=a["ops"].user)
    c.credentials(HTTP_X_ORGANIZATION=b["org"].slug)
    for url in ("/api/v1/work-orders/", "/api/v1/audit-logs/", "/api/v1/dashboards/operations/",
                "/api/v1/portal/requests/", "/api/v1/coverage-agreements/"):
        assert c.get(url).status_code == 403, url
