"""M07 Technician Workspace views (Django templates + HTMX). Orchestration only: every action calls the owning
module's service (M06 lifecycle / labor / material / evidence, M08 checklists), so no rule is implemented twice and
the backend re-checks authorization on every POST. Chain: login -> membership -> permission gate -> organization +
site + assignment scoped lookup (404) -> permission for the order's site (403) -> service.
"""
from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.checklists import selectors as cl_selectors
from apps.checklists import services as cl_services
from apps.checklists.models import Finding
from apps.core.exceptions import DomainError
from apps.core.exceptions import PermissionDenied as DomainPermissionDenied
from apps.inventory import selectors as inv_selectors
from apps.inventory import services as inv_services
from apps.inventory.forms import QuantityForm, RequestPartForm
from apps.rbac import services as rbac
from apps.sites.selectors import scoped_get
from apps.sites.views import need, or404
from apps.ui.mixins import TenantPermissionMixin
from apps.workorders import selectors as wo_selectors
from apps.workorders import services as wos
from apps.workorders.forms import CompleteForm, EvidenceForm, LaborForm, MaterialForm
from apps.workorders.views import build_actions
from apps.workorders.workflow import ACTION_PERMISSIONS, TERMINAL_STATES

from . import selectors, services
from .forms import FindingForm, NoteForm
from .models import WorkNote

WORKSPACE_ACTIONS = ("dispatch", "start", "hold", "resume", "complete")  # the lifecycle subset M07 exposes
RECORDABLE = ("IN_PROGRESS", "ON_HOLD", "COMPLETED", "SUPERVISOR_REVIEW")


class WorkspaceBase(TenantPermissionMixin, View):
    required_permission = "work_order.view_assigned"


def _wo(request, pk, code=None):
    wo = or404(wo_selectors.get_work_order, request.membership, request.organization, pk)
    if code:
        need(request, code, wo.site_id)
    return wo


def _job_url(wo, anchor=""):
    return reverse("workspace:job", args=[wo.pk]) + (f"#{anchor}" if anchor else "")


class JobsView(WorkspaceBase):
    def get(self, request):
        m, org = request.membership, request.organization
        view = request.GET.get("view", "active")
        if view not in ("active", "review", "all"):
            view = "active"
        page = Paginator(selectors.my_jobs(m, org, view), 20).get_page(request.GET.get("page"))
        pending = cl_selectors.pending_required_counts(org, list(page))
        return render(request, "workspace/jobs.html", {
            "page": page, "view": view, "counts": selectors.counts(m, org), "pending": pending})


class JobView(WorkspaceBase):
    def get(self, request, pk):
        m, org = request.membership, request.organization
        wo = _wo(request, pk)
        actions = [a for a in build_actions(request, wo) if a["action"] in WORKSPACE_ACTIONS]
        for a in actions:
            a["url"] = reverse("workspace:transition", args=[wo.pk, a["action"]])
            if a["kind"] == "complete":
                a["form"] = CompleteForm(initial={"resolution_notes": wo.resolution_notes})
        can = {k: rbac.has_permission(m, code, wo.site_id) for k, code in (
            ("record", "work_order.record"), ("attach", "work_order.attach"),
            ("inspect", "inspection.execute"), ("view_inspection", "inspection.view"))}
        try:
            wos.assert_can_execute(wo, m)
            executor = True
        except DomainPermissionDenied:
            executor = False
        recordable = wo.status in RECORDABLE and (executor or can["record"]) and wo.status not in TERMINAL_STATES
        requirements = cl_selectors.requirements_for(org, wo, cl_services)
        started_keys = {r["template"].key for r in requirements}
        can_start = (wo.status == "IN_PROGRESS" and executor and can["inspect"]
                     and rbac.has_permission_anywhere(m, "checklist.execute"))
        optional = [t for t in cl_selectors.available_templates(org, wo) if t.key not in started_keys] if can_start else []
        blockers = wos.checklist_blockers(wo) if wo.status in ("IN_PROGRESS", "ON_HOLD") else []
        evidence_missing = (wo.work_type in wos.EVIDENCE_REQUIRED_TYPES and wo.status in ("IN_PROGRESS", "ON_HOLD")
                            and not wos.evidence_for(wo).exists())
        labor = wo_selectors.labor_for(org, wo)
        part_lines = list(inv_selectors.lines_for_work_order(org, wo))
        can_consume = recordable and rbac.has_permission(m, "inventory.consume", wo.site_id)
        can_request_part = (wo.status in ("PLANNED", "ASSIGNED", "DISPATCHED", "IN_PROGRESS", "ON_HOLD")
                            and rbac.has_permission(m, "inventory.request", wo.site_id)
                            and inv_services.can_request(wo, m))
        return render(request, "workspace/job.html", {
            "part_lines": part_lines, "can_consume": can_consume, "can_request_part": can_request_part,
            "request_part_form": RequestPartForm(parts=inv_selectors.parts_for(org).filter(is_active=True).order_by(
                "part_number")) if can_request_part else None,
            "wo": wo, "actions": actions, "can": can, "executor": executor, "recordable": recordable,
            "requirements": requirements, "optional_templates": optional, "can_start": can_start,
            "blockers": blockers, "evidence_missing": evidence_missing,
            "notes": WorkNote.objects.for_organization(org).filter(work_order=wo).select_related("author")[:30],
            "labor": labor, "total_hours": wo_selectors.total_hours(org, wo),
            "materials": wo_selectors.materials_for(org, wo),
            "evidence": wos.evidence_for(wo).select_related("uploaded_by"),
            "events": wo_selectors.events_for(org, wo)[:12],
            "note_form": NoteForm(), "labor_form": LaborForm(), "material_form": MaterialForm(),
            "evidence_form": EvidenceForm(), "terminal": wo.status in TERMINAL_STATES})


class _Post(WorkspaceBase):
    http_method_names = ["post"]
    anchor = ""

    def done(self, request, wo, ok=None):
        if ok:
            messages.success(request, ok)
        return redirect(_job_url(wo, self.anchor))

    def fail(self, request, wo, exc):
        messages.error(request, exc.message if isinstance(exc, DomainError) else str(exc))
        return self.done(request, wo)


class TransitionView(_Post):
    def post(self, request, pk, action):
        wo = _wo(request, pk)
        if action not in WORKSPACE_ACTIONS:  # planning / review / close belong to M06 screens, not the workspace
            messages.error(request, "That action is not available in the technician workspace.")
            return self.done(request, wo)
        need(request, ACTION_PERMISSIONS[action], wo.site_id)
        data = {}
        try:
            if action == "complete":
                form = CompleteForm(request.POST)
                if not form.is_valid():
                    messages.error(request, "Resolution notes (at least 10 characters) are required.")
                    return self.done(request, wo)
                data = {"resolution_notes": form.cleaned_data["resolution_notes"]}
            wos.transition(wo, action=action, reason=request.POST.get("reason", ""), actor=request.user,
                           membership=request.membership, request=request, **data)
            return self.done(request, wo, "Work order updated.")
        except DomainError as exc:
            return self.fail(request, wo, exc)


class NoteView(_Post):
    anchor = "notes"

    def post(self, request, pk):
        wo = _wo(request, pk, "work_order.record")
        form = NoteForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Write a note (3 - 2000 characters).")
            return self.done(request, wo)
        try:
            services.add_note(wo, body=form.cleaned_data["body"], actor=request.user, membership=request.membership,
                              request=request)
            return self.done(request, wo, "Note saved.")
        except DomainError as exc:
            return self.fail(request, wo, exc)


class LaborView(_Post):
    anchor = "labor"

    def post(self, request, pk):
        wo = _wo(request, pk, "work_order.record")
        form = LaborForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a valid date and hours (0.01 - 24).")
            return self.done(request, wo)
        d = form.cleaned_data
        try:
            wos.record_labor(wo, technician=request.membership, work_date=d["work_date"], hours=d["hours"],
                             notes=d["notes"], actor=request.user, membership=request.membership, request=request)
            return self.done(request, wo, "Time recorded.")
        except DomainError as exc:
            return self.fail(request, wo, exc)


class MaterialView(_Post):
    anchor = "materials"

    def post(self, request, pk):
        wo = _wo(request, pk, "work_order.record")
        form = MaterialForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Describe the material and enter a quantity above zero.")
            return self.done(request, wo)
        d = form.cleaned_data
        try:
            wos.record_material(wo, description=d["description"], quantity=d["quantity"], unit=d["unit"],
                                part_number=d["part_number"], actor=request.user, membership=request.membership,
                                request=request)
            return self.done(request, wo, "Free-text material noted (no stock is moved).")
        except DomainError as exc:
            return self.fail(request, wo, exc)


class PartRequestView(_Post):
    """M07 -> M09 contract: the technician asks for parts through the inventory service (no stock is touched)."""

    anchor = "parts"

    def post(self, request, pk):
        wo = _wo(request, pk, "inventory.request")
        form = RequestPartForm(request.POST, parts=inv_selectors.parts_for(request.organization))
        if not form.is_valid():
            messages.error(request, "Choose a part and enter a quantity above zero.")
            return self.done(request, wo)
        d = form.cleaned_data
        try:
            inv_services.request_part(wo, d["part"], d["quantity"], actor=request.user, membership=request.membership,
                                      notes=d["notes"], request=request)
            return self.done(request, wo, "Part requested; stores will reserve and issue it.")
        except DomainError as exc:
            return self.fail(request, wo, exc)


class PartConsumeView(_Post):
    """M07 -> M09 contract: records how much of the issued stock was used (the stock itself left at issue time)."""

    anchor = "parts"

    def post(self, request, pk, line):
        wo = _wo(request, pk, "inventory.consume")
        row = or404(scoped_get, inv_selectors.lines_for_work_order(request.organization, wo), line, "Part line")
        form = QuantityForm(request.POST)
        if not form.is_valid() or form.cleaned_data.get("quantity") is None:
            messages.error(request, "Enter the quantity used.")
            return self.done(request, wo)
        try:
            inv_services.consume(row, form.cleaned_data["quantity"], actor=request.user,
                                 membership=request.membership, request=request)
            return self.done(request, wo, "Consumption recorded.")
        except DomainError as exc:
            return self.fail(request, wo, exc)


class EvidenceView(_Post):
    anchor = "evidence"

    def post(self, request, pk):
        wo = _wo(request, pk, "work_order.attach")
        form = EvidenceForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Choose a file to upload.")
            return self.done(request, wo)
        try:
            wos.add_evidence(wo, form.cleaned_data["file"], description=form.cleaned_data["description"],
                             actor=request.user, membership=request.membership, request=request)
            return self.done(request, wo, "Evidence uploaded.")
        except DomainError as exc:
            return self.fail(request, wo, exc)


# --- checklist execution (M08 services) -------------------------------------------------------------------------


class StartInspectionView(_Post):
    required_permission = "inspection.execute"

    def post(self, request, pk, template):
        wo = _wo(request, pk, "inspection.execute")
        need(request, "checklist.execute")
        tpl = or404(cl_selectors.get_template, request.organization, template)
        try:
            insp = cl_services.start_inspection(request.organization, template=tpl, membership=request.membership,
                                                actor=request.user, work_order=wo, request=request)
        except DomainError as exc:
            return self.fail(request, wo, exc)
        return redirect("workspace:inspection", pk=insp.pk)


def _inspection(request, pk, code=None):
    insp = or404(cl_selectors.get_inspection, request.membership, request.organization, pk)
    if code:
        need(request, code, insp.site_id)
    return insp


def _form_values(request, items):
    return {str(it.pk): request.POST.get(f"item_{it.pk}", "") for it in items}


def _inspection_context(request, insp, *, values=None, errors=None, issues=None):
    org = request.organization
    items = list(cl_selectors.items_for(org, insp.template))
    responses = cl_selectors.responses_for(org, insp)
    evidence = {}
    for att in cl_services.evidence_for_inspection(insp):
        evidence.setdefault(att.object_id, []).append(att)
    try:
        if insp.work_order_id:
            wos.assert_can_execute(insp.work_order, request.membership)
        editable = (insp.status == "IN_PROGRESS" and (insp.work_order is None or insp.work_order.status == "IN_PROGRESS")
                    and rbac.has_permission(request.membership, "inspection.execute", insp.site_id))
    except DomainPermissionDenied:
        editable = False
    rows = []
    for it in items:
        r = responses.get(it.pk)
        raw = (values or {}).get(str(it.pk))
        if raw is None and r is not None:
            raw = ("pass" if r.value_bool else "fail") if r.value_bool is not None else (
                f"{r.value_number.normalize():f}" if r.value_number is not None else r.value_text)
        rows.append({"item": it, "response": r, "value": raw or "", "error": (errors or {}).get(str(it.pk)),
                     "evidence": evidence.get(str(r.pk), []) if r else []})
    findings = list(insp.findings.select_related("item"))
    for f in findings:
        f.files = evidence.get(str(f.pk), [])
    return {"insp": insp, "rows": rows, "editable": editable, "issues": issues if issues is not None else (
        cl_services.completion_issues(insp) if insp.status == "IN_PROGRESS" else []),
        "findings": findings, "finding_evidence": evidence, "finding_form": FindingForm(),
        "evidence_form": EvidenceForm(), "wo": insp.work_order}


class InspectionView(WorkspaceBase):
    required_permission = "inspection.execute"

    def get(self, request, pk):
        insp = _inspection(request, pk)
        return render(request, "workspace/inspection.html", _inspection_context(request, insp))


class InspectionSaveView(WorkspaceBase):
    """Saves the answers; with ``action=complete`` it then tries to complete the inspection. HTMX requests get the
    form fragment back (``#inspection-body``), plain posts redirect. The saved answers survive a refused completion."""

    required_permission = "inspection.execute"
    http_method_names = ["post"]

    def post(self, request, pk):
        insp = _inspection(request, pk, "inspection.execute")
        items = list(cl_selectors.items_for(request.organization, insp.template))
        values = _form_values(request, items)
        errors, issues, flash = {}, None, None
        try:
            cl_services.save_responses(insp, values, membership=request.membership, actor=request.user,
                                       request=request)
            flash = ("success", "Answers saved.")
            if request.POST.get("action") == "complete":
                cl_services.complete_inspection(insp, membership=request.membership, actor=request.user,
                                                summary=request.POST.get("summary", ""), request=request)
                messages.success(request, "Inspection completed.")
                target = reverse("workspace:job", args=[insp.work_order_id]) if insp.work_order_id else reverse(
                    "workspace:inspection", args=[insp.pk])
                if request.headers.get("HX-Request"):
                    from django.http import HttpResponse

                    resp = HttpResponse(status=204)
                    resp["HX-Redirect"] = target
                    return resp
                return redirect(target)
        except DomainError as exc:
            errors = (exc.details or {}).get("errors", {}) if exc.code == "invalid_responses" else {}
            issues = (exc.details or {}).get("issues")
            flash = ("error", exc.message if not errors else "Some answers are not valid.")
        insp.refresh_from_db()
        ctx = _inspection_context(request, insp, values=values if errors else None, errors=errors, issues=issues)
        ctx["flash"] = flash
        if request.headers.get("HX-Request"):
            return render(request, "workspace/_inspection_form.html", ctx, status=200)
        if flash:
            (messages.success if flash[0] == "success" else messages.error)(request, flash[1])
        return redirect("workspace:inspection", pk=insp.pk)


class FindingView(WorkspaceBase):
    required_permission = "inspection.execute"
    http_method_names = ["post"]

    def post(self, request, pk):
        insp = _inspection(request, pk, "inspection.execute")
        form = FindingForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Describe the finding (at least 3 characters) and choose a severity.")
        else:
            d = form.cleaned_data
            try:
                item = scoped_get(cl_selectors.items_for(request.organization, insp.template), d["item"],
                                  "Checklist item") if d.get("item") else None
                cl_services.add_finding(insp, description=d["description"], severity=d["severity"], item=item,
                                        membership=request.membership, actor=request.user, request=request)
                messages.success(request, "Finding recorded.")
            except DomainError as exc:
                messages.error(request, exc.message)
        return redirect("workspace:inspection", pk=insp.pk)


class InspectionEvidenceView(WorkspaceBase):
    required_permission = "inspection.execute"
    http_method_names = ["post"]

    def post(self, request, pk):
        insp = _inspection(request, pk, "inspection.execute")
        form = EvidenceForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Choose a file to upload.")
            return redirect("workspace:inspection", pk=insp.pk)
        d = form.cleaned_data
        try:
            if request.POST.get("finding"):
                finding = or404(scoped_get, Finding.objects.for_organization(request.organization).filter(
                    inspection=insp), request.POST["finding"], "Finding")
                cl_services.add_finding_evidence(finding, d["file"], description=d["description"],
                                                 membership=request.membership, actor=request.user, request=request)
            else:
                item = or404(scoped_get, cl_selectors.items_for(request.organization, insp.template),
                             request.POST.get("item", ""), "Checklist item")
                cl_services.add_response_evidence(insp, item, d["file"], description=d["description"],
                                                  membership=request.membership, actor=request.user,
                                                  request=request)
            messages.success(request, "Evidence uploaded.")
        except DomainError as exc:
            messages.error(request, exc.message)
        return redirect("workspace:inspection", pk=insp.pk)
