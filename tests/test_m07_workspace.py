"""M07 Technician Workspace + M08 UI: pages render, every control posts to a real endpoint that persists and audits,
the required-checklist gate holds through the UI, forbidden roles / foreign objects are refused (404 / 403), CSRF is
enforced, evidence downloads honour scope, and the whole job runs end to end without touching the DB directly."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.checklists import services as cl
from apps.checklists.models import ChecklistTemplate, Finding, Inspection, InspectionResponse
from apps.files.models import Attachment
from apps.incidents import services as incidents
from apps.workorders import services as wos
from apps.workorders.models import WorkOrder, WorkOrderLabor, WorkOrderMaterial
from apps.workspace.models import WorkNote
from tests.phase3_support import (
    ITEMS,
    good_answers,
    item_ids,
    make_template,
    step,
    upload,
    wo_in_progress,
)

pytestmark = pytest.mark.django_db


def client_for(user):
    c = Client()
    c.force_login(user)
    return c


def audited(org, action):
    return AuditLog.objects.filter(organization=org, action=action).exists()


def form_values(template, answers):
    return {f"item_{k}": v for k, v in answers.items()}


def msgs(response):
    return [str(m) for m in response.context["messages"]] if response.context else []


# --- My Jobs ---------------------------------------------------------------------------------------------------------


def test_my_jobs_lists_only_my_assigned_work_and_guessed_urls_are_404(p3):
    mine = wo_in_progress(p3, tech="tech")
    theirs = wo_in_progress(p3, tech="tech2")
    tech, tech2 = client_for(p3["tech"].user), client_for(p3["tech2"].user)
    page = tech.get("/app/workspace/").content.decode()
    assert mine.number in page and theirs.number not in page
    assert theirs.number in tech2.get("/app/workspace/").content.decode()
    assert tech.get(f"/app/workspace/{mine.pk}/").status_code == 200
    assert tech.get(f"/app/workspace/{theirs.pk}/").status_code == 404  # other technician's job: indistinguishable
    # every workspace POST endpoint also answers 404 for a job that is not theirs
    for url in (f"/app/workspace/{theirs.pk}/transition/hold/", f"/app/workspace/{theirs.pk}/notes/",
                f"/app/workspace/{theirs.pk}/labor/", f"/app/workspace/{theirs.pk}/materials/",
                f"/app/workspace/{theirs.pk}/evidence/"):
        assert tech.post(url, {"reason": "nope nope", "body": "intruder note"}).status_code == 404, url
    assert not WorkNote.objects.exists()
    assert type(theirs).objects.get(pk=theirs.pk).status == "IN_PROGRESS"


def test_my_jobs_views_and_status_filters(p3):
    wo = wo_in_progress(p3)
    t = client_for(p3["tech"].user)
    assert wo.number in t.get("/app/workspace/?view=active").content.decode()
    assert wo.number not in t.get("/app/workspace/?view=review").content.decode()
    assert wo.number in t.get("/app/workspace/?view=all").content.decode()
    assert t.get("/app/workspace/?view=bogus").status_code == 200


def test_unauthenticated_inactive_and_cross_tenant_access(p3, org_b, make_member, make_site, make_asset):
    from apps.tenancy.models import Membership

    wo = wo_in_progress(p3)
    assert Client().get("/app/workspace/").status_code == 302
    assert Client().post(f"/app/workspace/{wo.pk}/notes/", {"body": "anon note"}).status_code == 302
    tech_b = make_member(org_b, "tech@beta.test", "technician")
    b = client_for(tech_b.user)
    assert b.get(f"/app/workspace/{wo.pk}/").status_code == 404
    assert b.post(f"/app/workspace/{wo.pk}/transition/hold/", {"reason": "cross tenant"}).status_code == 404
    insp_t = make_template(p3)
    insp = cl.start_inspection(p3["org"], template=insp_t, membership=p3["tech"], actor=p3["tech"].user,
                               work_order=wo)
    assert b.get(f"/app/workspace/inspections/{insp.pk}/").status_code == 404
    assert b.post(f"/app/workspace/inspections/{insp.pk}/save/", {"action": "complete"}).status_code == 404
    assert b.get(f"/app/checklists/{insp_t.pk}/").status_code in (403, 404)
    assert b.get(f"/app/inspections/{insp.pk}/").status_code in (403, 404)
    m = p3["tech"]
    m.status = Membership.Status.SUSPENDED
    m.save(update_fields=["status"])
    assert client_for(m.user).get(f"/app/workspace/{wo.pk}/").status_code in (302, 403)


def test_csrf_is_enforced_on_workspace_posts(p3):
    wo = wo_in_progress(p3)
    c = Client(enforce_csrf_checks=True)
    c.force_login(p3["tech"].user)
    assert c.post(f"/app/workspace/{wo.pk}/notes/", {"body": "no token here"}).status_code == 403
    assert not WorkNote.objects.exists()


# --- lifecycle through the workspace (M06 services) -----------------------------------------------------------------


def test_start_hold_resume_via_workspace_and_invalid_state_rejected(p3):
    wo = wos.create_work_order(p3["org"], asset=p3["asset"], actor=p3["planner"].user, title="Lube bearings",
                               work_type="PREVENTIVE")
    t0 = timezone.now() + timedelta(days=1)
    wo = step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=1))
    wo = step(wo, "assign", p3, "planner", technician=p3["tech"])
    tech = client_for(p3["tech"].user)
    page = tech.get(f"/app/workspace/{wo.pk}/").content.decode()
    assert "/transition/start/" not in page  # not dispatched yet
    r = tech.post(f"/app/workspace/{wo.pk}/transition/start/")  # direct POST bypassing the missing button
    assert r.status_code == 302 and WorkOrder.objects.get(pk=wo.pk).status == "ASSIGNED"
    step(wo, "dispatch", p3, "planner")
    assert "/transition/start/" in tech.get(f"/app/workspace/{wo.pk}/").content.decode()
    assert tech.post(f"/app/workspace/{wo.pk}/transition/start/").status_code == 302
    assert WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS" and audited(p3["org"], "work_order.status_changed")
    # hold needs a reason; resume restores
    tech.post(f"/app/workspace/{wo.pk}/transition/hold/", {"reason": ""})
    assert WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS"
    tech.post(f"/app/workspace/{wo.pk}/transition/hold/", {"reason": "Waiting for permit"})
    assert WorkOrder.objects.get(pk=wo.pk).status == "ON_HOLD"
    tech.post(f"/app/workspace/{wo.pk}/transition/resume/")
    assert WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS"


def test_workspace_refuses_planner_and_supervisor_actions_and_other_roles(p3):
    wo = wo_in_progress(p3)
    tech, reader, sup = (client_for(p3[k].user) for k in ("tech", "reader", "sup"))
    for action in ("plan", "assign", "start_review", "close", "cancel", "reject_review", "bogus"):
        tech.post(f"/app/workspace/{wo.pk}/transition/{action}/", {"reason": "try it anyway"})
        assert WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS", action
    assert reader.post(f"/app/workspace/{wo.pk}/transition/hold/", {"reason": "read only role"}).status_code == 403
    assert reader.post(f"/app/workspace/{wo.pk}/notes/", {"body": "read only note"}).status_code == 403
    # a supervisor may look at the job but is neither the assignee nor a dispatcher: the service refuses
    sup.post(f"/app/workspace/{wo.pk}/transition/hold/", {"reason": "not my job at all"})
    assert WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS"
    page = reader.get(f"/app/workspace/{wo.pk}/").content.decode()
    assert "/transition/" not in page and "Save note" not in page


# --- notes / evidence / labor / material ------------------------------------------------------------------------------


def test_notes_labor_material_evidence_persist_and_validate(p3):
    wo = wo_in_progress(p3, work_type="PREVENTIVE")
    tech = client_for(p3["tech"].user)
    base = f"/app/workspace/{wo.pk}"
    assert tech.post(f"{base}/notes/", {"body": "ab"}).status_code == 302 and not WorkNote.objects.exists()
    assert tech.post(f"{base}/notes/", {"body": "Bearing runs warm after lubrication"}).status_code == 302
    note = WorkNote.objects.get()
    assert note.author_id == p3["tech"].user.pk and note.work_order_id == wo.pk and audited(p3["org"], "work_order.note_added")
    with pytest.raises(ValueError):
        note.save()  # append-only
    # labor: rules of M06 apply (hours range, future date, one-self)
    today = timezone.localdate()
    for bad in ({"work_date": today, "hours": "0"}, {"work_date": today, "hours": "24.5"},
                {"work_date": today + timedelta(days=5), "hours": "2"}, {"work_date": "garbage", "hours": "1"}):
        tech.post(f"{base}/labor/", bad)
    assert not WorkOrderLabor.objects.exists()
    tech.post(f"{base}/labor/", {"work_date": today, "hours": "2.5", "notes": "Alignment check"})
    row = WorkOrderLabor.objects.get()
    assert row.technician_id == p3["tech"].pk and str(row.hours) == "2.50"
    # material is free text only: nothing but the line itself is written
    tech.post(f"{base}/materials/", {"description": "Grease cartridge", "quantity": "0", "unit": "pcs"})
    assert not WorkOrderMaterial.objects.exists()
    tech.post(f"{base}/materials/", {"description": "Grease cartridge", "quantity": "2", "unit": "pcs"})
    assert WorkOrderMaterial.objects.get().description == "Grease cartridge"
    # evidence: valid + invalid type
    tech.post(f"{base}/evidence/", {"file": SimpleUploadedFile("after.txt", b"photo notes after the work")})
    assert wos.evidence_for(wo).count() == 1
    tech.post(f"{base}/evidence/", {"file": SimpleUploadedFile("run.exe", b"MZ\x90\x00bad")})
    assert wos.evidence_for(wo).count() == 1
    page = tech.get(f"{base}/").content.decode()
    for needle in ("Bearing runs warm", "Alignment check", "Grease cartridge", "after.txt", "Total 2.50 h"):
        assert needle in page, needle
    for action in ("work_order.labor_recorded", "work_order.material_recorded", "work_order.evidence_added"):
        assert audited(p3["org"], action), action


def test_notes_refused_when_not_in_progress_or_not_mine(p3):
    wo = wos.create_work_order(p3["org"], asset=p3["asset"], actor=p3["planner"].user, title="Not started yet",
                               work_type="PREVENTIVE")
    t0 = timezone.now() + timedelta(days=1)
    wo = step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=1))
    step(wo, "assign", p3, "planner", technician=p3["tech"])
    tech = client_for(p3["tech"].user)
    tech.post(f"/app/workspace/{wo.pk}/notes/", {"body": "too early to note"})
    assert not WorkNote.objects.exists()


# --- checklist execution through the UI -------------------------------------------------------------------------------


def start_via_ui(tech, wo, template):
    r = tech.post(f"/app/workspace/{wo.pk}/checklists/{template.pk}/start/")
    assert r.status_code == 302, r.status_code
    return Inspection.objects.get(work_order=wo, template=template)


def test_required_checklist_blocks_ui_completion_until_inspection_completed(p3):
    t = make_template(p3)
    wo = wo_in_progress(p3)
    tech = client_for(p3["tech"].user)
    page = tech.get(f"/app/workspace/{wo.pk}/").content.decode()
    assert t.name in page and "Required" in page and "Start checklist" in page and "Before you can complete" in page
    tech.post(f"/app/workspace/{wo.pk}/labor/", {"work_date": timezone.localdate(), "hours": "1"})
    notes = {"resolution_notes": "All done and verified on site."}
    r = tech.post(f"/app/workspace/{wo.pk}/transition/complete/", notes, follow=True)
    assert any("checklist" in m.lower() for m in msgs(r)) and WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS"
    insp = start_via_ui(tech, wo, t)
    assert tech.post(f"/app/workspace/{wo.pk}/checklists/{t.pk}/start/").status_code == 302
    assert Inspection.objects.filter(work_order=wo).count() == 1  # duplicate start refused
    r = tech.post(f"/app/workspace/{wo.pk}/transition/complete/", notes, follow=True)
    assert WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS"  # started but not completed
    ids = item_ids(t)
    # answers: invalid numeric rejected, nothing saved (HTMX partial carries the message)
    r = tech.post(f"/app/workspace/inspections/{insp.pk}/save/",
                  form_values(t, {ids["Casing free of leaks"]: "pass", ids["Discharge pressure"]: "lots"}),
                  HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and "must be a number" in r.content.decode()
    assert not InspectionResponse.objects.filter(inspection=insp).exists()
    # completion refused while required answers are missing; the partial answers are kept
    r = tech.post(f"/app/workspace/inspections/{insp.pk}/save/",
                  {**form_values(t, {ids["Casing free of leaks"]: "pass"}), "action": "complete"},
                  HTTP_HX_REQUEST="true")
    body = r.content.decode()
    assert "cannot be completed yet" in body and "Question 2 is required" in body
    assert Inspection.objects.get(pk=insp.pk).status == "IN_PROGRESS"
    assert InspectionResponse.objects.filter(inspection=insp).count() == 1
    # refresh preserves the stored answer
    assert 'value="pass" checked' in tech.get(f"/app/workspace/inspections/{insp.pk}/").content.decode()
    # complete properly (HTMX -> HX-Redirect back to the job)
    r = tech.post(f"/app/workspace/inspections/{insp.pk}/save/",
                  {**form_values(t, good_answers(t)), "action": "complete", "summary": "All good"},
                  HTTP_HX_REQUEST="true")
    assert r.status_code == 204 and r["HX-Redirect"] == f"/app/workspace/{wo.pk}/"
    done = Inspection.objects.get(pk=insp.pk)
    assert done.status == "COMPLETED" and done.summary == "All good" and done.completed_by_id == p3["tech"].pk
    page = tech.get(f"/app/workspace/{wo.pk}/").content.decode()
    assert "Before you can complete" not in page
    tech.post(f"/app/workspace/{wo.pk}/transition/complete/", notes)
    assert WorkOrder.objects.get(pk=wo.pk).status == "COMPLETED"
    assert audited(p3["org"], "inspection.completed")


def test_stale_form_after_completion_is_refused_and_db_unchanged(p3):
    t = make_template(p3)
    wo = wo_in_progress(p3)
    tech = client_for(p3["tech"].user)
    insp = start_via_ui(tech, wo, t)
    ids = item_ids(t)
    tech.post(f"/app/workspace/inspections/{insp.pk}/save/", {**form_values(t, good_answers(t)), "action": "complete"})
    assert Inspection.objects.get(pk=insp.pk).status == "COMPLETED"
    before = {r.item_id: (r.value_number, r.value_bool) for r in InspectionResponse.objects.filter(inspection=insp)}
    tech.post(f"/app/workspace/inspections/{insp.pk}/save/",  # stale form still open in another tab
              {**form_values(t, {ids["Discharge pressure"]: "5.5", ids["Casing free of leaks"]: "fail"}),
               "action": "save"})
    after = {r.item_id: (r.value_number, r.value_bool) for r in InspectionResponse.objects.filter(inspection=insp)}
    assert before == after
    r = tech.post(f"/app/workspace/inspections/{insp.pk}/save/", {"action": "complete"}, HTTP_HX_REQUEST="true")
    assert "completed" in r.content.decode()
    page = tech.get(f"/app/workspace/inspections/{insp.pk}/").content.decode()
    assert "Complete inspection" not in page and "Save answers" not in page


def test_exception_needs_finding_and_evidence_through_ui(p3):
    items = [{"prompt": "Casing free of leaks", "item_type": "BOOLEAN"},
             {"prompt": "Nameplate photo", "item_type": "TEXT", "evidence_required": True}]
    t = make_template(p3, items=items)
    wo = wo_in_progress(p3)
    tech = client_for(p3["tech"].user)
    insp = start_via_ui(tech, wo, t)
    ids = item_ids(t)
    tech.post(f"/app/workspace/inspections/{insp.pk}/save/",
              form_values(t, {ids["Casing free of leaks"]: "fail", ids["Nameplate photo"]: "X-100"}))
    assert InspectionResponse.objects.get(inspection=insp, item_id=ids["Casing free of leaks"]).is_exception
    r = tech.post(f"/app/workspace/inspections/{insp.pk}/save/", {"action": "complete"}, HTTP_HX_REQUEST="true")
    body = r.content.decode()
    assert "record a finding" in body and "needs evidence" in body
    # finding: validation then persistence with full context
    tech.post(f"/app/workspace/inspections/{insp.pk}/findings/", {"description": "x", "severity": "HIGH"})
    assert not Finding.objects.exists()
    tech.post(f"/app/workspace/inspections/{insp.pk}/findings/",
              {"description": "Water leaking from casing joint", "severity": "HIGH", "item": ids["Casing free of leaks"]})
    f = Finding.objects.get()
    assert (f.severity, f.status, f.work_order_id, f.asset_id, f.site_id, f.created_by_id) == (
        "HIGH", "OPEN", wo.pk, p3["asset"].pk, p3["site"].pk, p3["tech"].user.pk)
    # evidence on an answer; invalid file refused; finding evidence too
    assert tech.post(f"/app/workspace/inspections/{insp.pk}/evidence/",
                     {"item": ids["Nameplate photo"], "file": SimpleUploadedFile("bad.exe", b"MZ\x90\x00bad")}).status_code == 302
    assert not Attachment.objects.filter(object_id__in=[str(r.pk) for r in InspectionResponse.objects.all()]).exists()
    tech.post(f"/app/workspace/inspections/{insp.pk}/evidence/", {"item": ids["Nameplate photo"], "file": upload("plate.txt")})
    tech.post(f"/app/workspace/inspections/{insp.pk}/evidence/", {"finding": str(f.pk), "file": upload("leak.txt")})
    assert Attachment.objects.filter(object_id=str(f.pk)).count() == 1
    tech.post(f"/app/workspace/inspections/{insp.pk}/save/", {"action": "complete"})
    assert Inspection.objects.get(pk=insp.pk).status == "COMPLETED"


def test_evidence_download_follows_inspection_scope_and_tenancy(p3, org_b, make_member):
    items = [{"prompt": "Nameplate photo", "item_type": "TEXT"}]
    t = make_template(p3, items=items)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=p3["tech"], actor=p3["tech"].user, work_order=wo)
    cl.save_responses(insp, {str(t.items.get().pk): "X-100"}, membership=p3["tech"], actor=p3["tech"].user)
    att = cl.add_response_evidence(insp, t.items.get(), upload("plate.txt"), membership=p3["tech"],
                                   actor=p3["tech"].user)
    url = f"/app/files/{att.pk}/download/"
    assert client_for(p3["tech"].user).get(url).status_code == 200
    assert client_for(p3["sup"].user).get(url).status_code == 200
    assert client_for(p3["tech2"].user).get(url).status_code == 404  # another technician: out of scope
    assert client_for(make_member(org_b, "sup@beta.test", "supervisor").user).get(url).status_code == 404
    assert client_for(make_member(org_b, "tech@beta.test", "technician").user).get(url).status_code == 404
    assert Client().get(url).status_code == 302


def test_completed_inspection_page_is_read_only_for_other_roles(p3):
    t = make_template(p3)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=p3["tech"], actor=p3["tech"].user, work_order=wo)
    cl.save_responses(insp, good_answers(t), membership=p3["tech"], actor=p3["tech"].user)
    sup = client_for(p3["sup"].user)
    page = sup.get(f"/app/workspace/inspections/{insp.pk}/").content.decode()
    assert "Save answers" not in page and "Complete inspection" not in page  # not the assignee: read-only
    assert sup.get(f"/app/inspections/{insp.pk}/").status_code == 200  # the results page is theirs
    r = sup.post(f"/app/workspace/inspections/{insp.pk}/save/", {"action": "complete", **form_values(t, good_answers(t))},
                 follow=True)
    assert any("assigned technician" in m for m in msgs(r))
    assert Inspection.objects.get(pk=insp.pk).status == "IN_PROGRESS"
    assert InspectionResponse.objects.filter(inspection=insp).count() == 3  # nothing changed


# --- M08 UI: template management and results --------------------------------------------------------------------------


def test_template_management_ui_end_to_end_and_permissions(p3):
    sup, tech, reader = (client_for(p3[k].user) for k in ("sup", "tech", "reader"))
    assert tech.get("/app/checklists/").status_code == 403 and tech.get("/app/checklists/new/").status_code == 403
    assert reader.get("/app/checklists/").status_code == 200
    assert reader.post("/app/checklists/new/", {"name": "Reader list"}).status_code == 403
    assert sup.get("/app/checklists/new/").status_code == 200
    assert sup.post("/app/checklists/new/", {"name": "ab"}).status_code == 400
    r = sup.post("/app/checklists/new/", {"name": "Pump weekly", "work_type": "PREVENTIVE", "is_required": "on",
                                          "description": "Weekly pump round"})
    t = ChecklistTemplate.objects.get(name="Pump weekly")
    assert r.status_code == 302 and r.url == f"/app/checklists/{t.pk}/" and t.is_required and t.status == "DRAFT"
    page = sup.get(r.url).content.decode()
    assert "Add a question" in page and "Activate" in page
    base = f"/app/checklists/{t.pk}"
    sup.post(f"{base}/items/add/", {"prompt": "ab", "item_type": "TEXT"})
    assert t.items.count() == 0
    sup.post(f"{base}/items/add/", {"prompt": "Gauge reading", "item_type": "NUMERIC", "min_value": "1", "max_value": "5",
                                    "unit": "bar", "required": "on"})
    sup.post(f"{base}/items/add/", {"prompt": "Seal condition", "item_type": "SELECTION", "options": "Good\nWorn\nFailed",
                                    "exception_options": "Failed", "required": "on", "evidence_required": "on"})
    sup.post(f"{base}/items/add/", {"prompt": "Choose one", "item_type": "SELECTION", "options": "OnlyOne"})
    assert t.items.count() == 2
    first, second = t.items.order_by("position")
    sup.post(f"{base}/items/{second.pk}/move/up/")
    assert [i.prompt for i in t.items.order_by("position")] == ["Seal condition", "Gauge reading"]
    assert sup.get(f"{base}/items/{first.pk}/edit/").status_code == 200
    sup.post(f"{base}/items/{first.pk}/edit/", {"prompt": "Gauge reading (bar)", "item_type": "NUMERIC", "min_value": "9",
                                                 "max_value": "1"})
    assert t.items.get(pk=first.pk).prompt == "Gauge reading"  # invalid range refused
    sup.post(f"{base}/items/{first.pk}/edit/", {"prompt": "Gauge reading (bar)", "item_type": "NUMERIC", "min_value": "1",
                                                 "max_value": "6", "required": "on"})
    assert t.items.get(pk=first.pk).prompt == "Gauge reading (bar)"
    assert tech.post(f"{base}/activate/").status_code == 403
    sup.post(f"{base}/activate/")
    t.refresh_from_db()
    assert t.status == "ACTIVE"
    sup.post(f"{base}/items/add/", {"prompt": "Late question", "item_type": "TEXT"})
    assert t.items.count() == 2  # frozen
    assert sup.post(f"{base}/edit/", {"name": "Renamed"}).status_code == 400
    sup.post(f"{base}/new-version/")
    v2 = ChecklistTemplate.objects.get(key=t.key, version=2)
    assert v2.status == "DRAFT" and v2.items.count() == 2
    sup.post(f"/app/checklists/{v2.pk}/activate/")
    t.refresh_from_db()
    assert t.status == "INACTIVE"
    for action in ("checklist.created", "checklist.item_added", "checklist.items_reordered", "checklist.activated",
                   "checklist.version_created"):
        assert audited(p3["org"], action), action
    assert "Pump weekly" in reader.get("/app/checklists/").content.decode()
    assert sup.get("/app/checklists/00000000-0000-0000-0000-000000000000/").status_code == 404


def test_inspection_results_page_and_finding_resolution_in_ui(p3):
    t = make_template(p3)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=p3["tech"], actor=p3["tech"].user, work_order=wo)
    ids = item_ids(t)
    cl.save_responses(insp, {ids["Casing free of leaks"]: False, ids["Discharge pressure"]: "4", ids["Seal condition"]: "Good"},
                      membership=p3["tech"], actor=p3["tech"].user)
    f = cl.add_finding(insp, description="Casing weeping at joint", severity="HIGH",
                       item=t.items.get(prompt="Casing free of leaks"), membership=p3["tech"], actor=p3["tech"].user)
    sup, tech = client_for(p3["sup"].user), client_for(p3["tech"].user)
    assert "Inspections" in sup.get("/app/inspections/").content.decode()
    page = sup.get(f"/app/inspections/{insp.pk}/").content.decode()
    assert "Casing weeping at joint" in page and "Exception" in page and "Fail" in page
    assert tech.post(f"/app/findings/{f.pk}/resolve/", {"reason": "tech should not"}).status_code == 403
    assert Finding.objects.get(pk=f.pk).status == "OPEN"
    sup.post(f"/app/findings/{f.pk}/resolve/", {"reason": "x"})
    assert Finding.objects.get(pk=f.pk).status == "OPEN"
    sup.post(f"/app/findings/{f.pk}/resolve/", {"reason": "Joint re-sealed and pressure tested"})
    assert Finding.objects.get(pk=f.pk).status == "RESOLVED" and audited(p3["org"], "inspection.finding_resolved")


def test_site_scoped_supervisor_cannot_open_other_site_inspection_pages(p3, make_scoped_member):
    t = make_template(p3)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=p3["tech"], actor=p3["tech"].user, work_order=wo)
    other = client_for(make_scoped_member(p3["org"], "sup2@alpha.test", "supervisor", [p3["site2"]]).user)
    assert other.get(f"/app/inspections/{insp.pk}/").status_code == 404
    assert other.get(f"/app/workspace/{wo.pk}/").status_code == 404
    assert str(insp.pk) not in other.get("/app/inspections/").content.decode()


# --- performance -----------------------------------------------------------------------------------------------------------


def test_my_jobs_page_does_not_issue_per_row_queries(p3, django_assert_max_num_queries):
    make_template(p3)
    from tests.phase3_support import new_wo

    t0 = timezone.now() + timedelta(days=1)
    for i in range(8):
        wo = new_wo(p3, title=f"Job {i}")
        wo = step(wo, "plan", p3, "planner", planned_start=t0 + timedelta(days=i, hours=0),
                  planned_end=t0 + timedelta(days=i, hours=1))
        step(wo, "assign", p3, "planner", technician=p3["tech"])
    tech = client_for(p3["tech"].user)
    tech.get("/app/workspace/")  # warm caches (content types, permissions)
    with django_assert_max_num_queries(25):
        r = tech.get("/app/workspace/")
    assert r.content.decode().count("Job ") >= 8


# --- the whole job, no DB injection ------------------------------------------------------------------------------------------


def test_full_journey_incident_to_closed_through_api_and_html(p3, as_user):
    """Organization > Site > Asset > Incident > Work Order > assignment > workspace > start > checklist > required
    responses > finding > evidence > labor > complete > supervisor review > close."""
    template = make_template(p3, work_type="CORRECTIVE", items=ITEMS)
    org = p3["org"]
    # incident -> approved -> work order (services, as the Phase 2 journey proves the API/UI for these steps)
    ops = p3["ops"]
    sr = incidents.create_request(org, asset=p3["asset"], reporter=ops, actor=ops.user, title="Pump seal leaking",
                                  severity="HIGH")
    for a in ("triage", "approve"):
        sr = incidents.transition(sr, action=a, actor=ops.user)
    planner_api = as_user(p3["planner"].user, org)
    r = planner_api.post(f"/api/v1/service-requests/{sr.pk}/create-work-order/", {}, format="json")
    assert r.status_code in (200, 201), r.content
    wo = WorkOrder.objects.get(source_request=sr)
    t0 = (timezone.now() + timedelta(days=1)).isoformat()
    t1 = (timezone.now() + timedelta(days=1, hours=3)).isoformat()
    assert planner_api.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "plan", "planned_start": t0,
                                                                         "planned_end": t1}, format="json").status_code == 200
    assert planner_api.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "assign",
                            "technician": str(p3["tech"].pk)}, format="json").status_code == 200
    assert planner_api.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": "dispatch"}, format="json").status_code == 200
    tech = client_for(p3["tech"].user)
    assert wo.number in tech.get("/app/workspace/").content.decode()
    # start in the workspace
    tech.post(f"/app/workspace/{wo.pk}/transition/start/")
    assert WorkOrder.objects.get(pk=wo.pk).status == "IN_PROGRESS"
    # checklist: required items; the seal is an exception, so a finding + evidence follow
    insp = start_via_ui(tech, wo, template)
    ids = item_ids(template)
    tech.post(f"/app/workspace/inspections/{insp.pk}/save/", form_values(template, {
        ids["Casing free of leaks"]: "fail", ids["Discharge pressure"]: "3.8", ids["Seal condition"]: "Failed",
        ids["Technician remarks"]: "Seal replaced"}))
    tech.post(f"/app/workspace/inspections/{insp.pk}/findings/", {
        "description": "Mechanical seal failed", "severity": "HIGH", "item": ids["Seal condition"]})
    tech.post(f"/app/workspace/inspections/{insp.pk}/findings/", {
        "description": "Casing wet around the seal housing", "severity": "MEDIUM", "item": ids["Casing free of leaks"]})
    tech.post(f"/app/workspace/inspections/{insp.pk}/evidence/", {
        "finding": str(Finding.objects.get(severity="HIGH").pk), "file": upload("seal.txt")})
    r = tech.post(f"/app/workspace/inspections/{insp.pk}/save/", {"action": "complete"})
    assert Inspection.objects.get(pk=insp.pk).status == "COMPLETED", r.status_code
    # notes / labor / material / evidence for the job, then completion
    tech.post(f"/app/workspace/{wo.pk}/notes/", {"body": "Replaced the mechanical seal, no leaks after test run."})
    tech.post(f"/app/workspace/{wo.pk}/labor/", {"work_date": timezone.localdate(), "hours": "3", "notes": "Seal swap"})
    tech.post(f"/app/workspace/{wo.pk}/materials/", {"description": "Mechanical seal 40mm", "quantity": "1", "unit": "pcs"})
    tech.post(f"/app/workspace/{wo.pk}/evidence/", {"file": upload("after.txt")})
    r = tech.post(f"/app/workspace/{wo.pk}/transition/complete/", {"resolution_notes": "Replaced the mechanical seal and tested."},
                  follow=True)
    assert WorkOrder.objects.get(pk=wo.pk).status == "COMPLETED", msgs(r)
    # supervisor review and closure through the M06 screens
    sup = client_for(p3["sup"].user)
    sup.post(f"/app/work-orders/{wo.pk}/transition/start_review/")
    assert WorkOrder.objects.get(pk=wo.pk).status == "SUPERVISOR_REVIEW"
    assert wos.closure_blockers(WorkOrder.objects.get(pk=wo.pk)) == []
    sup.post(f"/app/work-orders/{wo.pk}/transition/close/")
    wo = WorkOrder.objects.get(pk=wo.pk)
    assert wo.status == "CLOSED" and wo.closed_at
    # database evidence
    assert Inspection.objects.filter(work_order=wo, status="COMPLETED").count() == 1
    assert InspectionResponse.objects.filter(inspection=insp).count() == 4
    assert Finding.objects.filter(work_order=wo, status="OPEN").count() == 2
    assert WorkNote.objects.filter(work_order=wo).count() == 1 and WorkOrderLabor.objects.filter(work_order=wo).count() == 1
    assert WorkOrderMaterial.objects.filter(work_order=wo).count() == 1
    for action in ("inspection.started", "inspection.responses_saved", "inspection.finding_added", "inspection.completed",
                   "work_order.note_added", "work_order.labor_recorded", "work_order.status_changed"):
        assert audited(org, action), action
    # the supervisor then resolves the finding on the results page
    f = Finding.objects.get(work_order=wo, severity="HIGH")
    sup.post(f"/app/findings/{f.pk}/resolve/", {"reason": "Seal replaced under this work order"})
    assert Finding.objects.get(pk=f.pk).status == "RESOLVED"
