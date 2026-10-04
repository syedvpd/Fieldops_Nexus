"""M15 per-work-order evidence package: contents reconcile with the database, files carry checksums, and the
tenant / site / permission boundaries hold (UI + API); the export itself is audited."""
import csv
import hashlib
import io
import json
import zipfile
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.checklists import services as cl
from apps.checklists.models import ChecklistTemplate
from apps.incidents import services as incidents
from apps.workorders import services as wos
from tests.phase3_support import good_answers, make_template, step, upload

pytestmark = pytest.mark.django_db


def web(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def closed(p3):
    make_template(p3, required=True, work_type="CORRECTIVE")
    sr = incidents.create_request(p3["org"], asset=p3["asset"], reporter=p3["tech"], title="Seal leaking",
                                  severity="HIGH", actor=p3["tech"].user)
    incidents.transition(sr, action="triage", actor=p3["ops"].user)
    incidents.transition(sr, action="approve", actor=p3["ops"].user)
    wo = incidents.create_work_order_for_request(sr, actor=p3["planner"].user, membership=p3["planner"])
    t0 = timezone.now() + timedelta(days=1)
    wo = step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=2))
    wo = step(wo, "assign", p3, "planner", technician=p3["tech"])
    wo = step(wo, "dispatch", p3, "planner")
    wo = step(wo, "start", p3, "tech")
    template = ChecklistTemplate.objects.for_organization(p3["org"]).get(status="ACTIVE")
    insp = cl.start_inspection(p3["org"], template=template, membership=p3["tech"], actor=p3["tech"].user,
                               work_order=wo)
    cl.save_responses(insp, good_answers(template), membership=p3["tech"], actor=p3["tech"].user)
    cl.complete_inspection(insp, membership=p3["tech"], actor=p3["tech"].user)
    wos.add_evidence(wo, upload("seal.txt", b"photo of the new seal fitted"), description="after repair",
                     actor=p3["tech"].user, membership=p3["tech"])
    wos.record_labor(wo, technician=p3["tech"], work_date=timezone.localdate(), hours="2", actor=p3["tech"].user,
                     membership=p3["tech"])
    wo = step(wo, "complete", p3, "tech", resolution_notes="Replaced the seal and pressure-tested the line.")
    wo = step(wo, "start_review", p3, "sup")
    wo = step(wo, "close", p3, "sup")
    incidents.transition(sr, action="confirm", actor=p3["ops"].user)
    return {**p3, "wo": wo, "sr": sr}


def unzip(response):
    assert response.status_code == 200 and response["Content-Type"] == "application/zip"
    return zipfile.ZipFile(io.BytesIO(response.content))


def rows(z, name):
    return list(csv.DictReader(io.StringIO(z.read(name).decode())))


def test_package_contents_reconcile_with_the_records(closed, make_member):
    auditor = make_member(closed["org"], "auditor@alpha.test", "auditor")
    z = unzip(web(auditor.user).get(f"/app/audit/evidence/work-order/{closed['wo'].pk}/"))
    names = set(z.namelist())
    assert {"summary.json", "timeline.csv", "approvals.csv", "checklists.json", "labor.csv", "audit_trail.csv",
            "sla.json", "manifest.json", "request_history.csv", "coverage_checks.csv"} <= names
    summary = json.loads(z.read("summary.json"))
    assert summary["work_order"]["status"] == "CLOSED" and summary["source_request"]["number"] == closed["sr"].number
    assert [r["Action"] for r in rows(z, "timeline.csv")][-1] == "close"
    decisions = [r["Decision"] for r in rows(z, "approvals.csv")]
    assert "close" in decisions and "request:confirm" in decisions and "request:approve" in decisions
    checklist = json.loads(z.read("checklists.json"))
    assert checklist[0]["status"] == "COMPLETED" and checklist[0]["responses"]
    assert rows(z, "labor.csv")[0]["Hours"] == "2.00"
    audit_actions = {r["Action"] for r in rows(z, "audit_trail.csv")}
    assert "work_order.status_changed" in audit_actions and "incident.status_changed" in audit_actions
    manifest = json.loads(z.read("manifest.json"))
    evidence_files = [f for f in manifest["files"] if f["path"].startswith("evidence/")]
    assert evidence_files and all(f["checksum_ok"] for f in evidence_files)
    body = z.read(evidence_files[0]["path"])
    assert hashlib.sha256(body).hexdigest() == evidence_files[0]["sha256"]
    assert manifest["documents"]["summary.json"] == hashlib.sha256(z.read("summary.json")).hexdigest()
    assert AuditLog.objects.filter(action="audit.evidence_exported", organization=closed["org"],
                                   metadata__work_order=closed["wo"].number).exists()


def test_package_is_permission_and_tenant_scoped(closed, org_b, make_member, make_scoped_member):
    url = f"/app/audit/evidence/work-order/{closed['wo'].pk}/"
    assert web(closed["tech"].user).get(url).status_code == 403  # no audit.export
    assert web(closed["planner"].user).get(url).status_code == 403
    foreign = make_member(org_b, "auditor@beta.test", "auditor")
    assert web(foreign.user).get(url).status_code == 404
    # the API behaves the same
    api = APIClient()
    api.force_authenticate(user=foreign.user)
    api.credentials(HTTP_X_ORGANIZATION=org_b.slug)
    assert api.get(f"/api/v1/audit-logs/evidence/?work_order={closed['wo'].pk}").status_code == 404
    mine = make_member(closed["org"], "auditor2@alpha.test", "auditor")
    api2 = APIClient()
    api2.force_authenticate(user=mine.user)
    api2.credentials(HTTP_X_ORGANIZATION=closed["org"].slug)
    assert api2.get("/api/v1/audit-logs/evidence/").status_code == 400
    assert api2.get("/api/v1/audit-logs/evidence/?work_order=not-an-id").status_code == 400
    ok = api2.get(f"/api/v1/audit-logs/evidence/?work_order={closed['wo'].pk}")
    assert ok.status_code == 200 and zipfile.is_zipfile(io.BytesIO(ok.content))


def test_site_scoped_exporter_cannot_package_another_sites_order(closed, make_scoped_member):
    other_site = make_scoped_member(closed["org"], "scoped@alpha.test", "auditor", [closed["site2"]])
    r = web(other_site.user).get(f"/app/audit/evidence/work-order/{closed['wo'].pk}/")
    assert r.status_code in (403, 404)


def test_work_order_page_offers_the_package_only_to_exporters(closed, make_member):
    auditor = make_member(closed["org"], "auditor@alpha.test", "auditor")
    page = web(auditor.user).get(f"/app/work-orders/{closed['wo'].pk}/").content.decode()
    assert 'id="evidence-package"' in page
    page = web(closed["tech"].user).get(f"/app/work-orders/{closed['wo'].pk}/").content.decode()
    assert 'id="evidence-package"' not in page
