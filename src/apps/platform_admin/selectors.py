"""Read-only, cross-organization selectors for the Super Admin console. Every number comes from the database.
The platform admin MONITORS tenants here; nothing in this module mutates tenant data (no support mode: D-PA-1)."""
import csv
import datetime
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, F, Max, Q, Sum
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetComponent, AssetDocument, AssetMeter
from apps.audit.models import AuditLog
from apps.incidents.models import ServiceRequest
from apps.inventory.models import Part, StockBalance, StockMovement, Warehouse, WorkOrderPart
from apps.maintenance.models import MaintenanceCycle, MaintenancePlan, MaintenanceSchedule
from apps.rbac.models import MembershipRole, Permission, Role
from apps.sites.models import Site, Zone
from apps.sla.models import SLABreach, SLAProfile, SLATracking
from apps.tenancy.models import Membership, Organization
from apps.workorders.models import WorkOrder
from apps.workorders.workflow import CANCELLED, CLOSED, COMPLETED, SUPERVISOR_REVIEW

PAGE_SIZE = 25
DONE_WO = (CLOSED, CANCELLED)
FINISHED_WO = (CLOSED, CANCELLED, COMPLETED, SUPERVISOR_REVIEW)


# ---- cell / section helpers -------------------------------------------------------------------------------
def T(v):
    return {"k": "t", "v": "—" if v in (None, "") else v}


def B(v):
    return {"k": "b", "v": v}


def L(text, url):
    return {"k": "l", "v": text or "—", "u": url}


def BAR(value, pct):
    return {"k": "bar", "v": value, "pct": max(0, min(100, int(pct)))}


def dt(v, fmt="%d %b %Y %H:%M"):
    return v.strftime(fmt) if v else None


def _uuid(raw):
    try:
        return uuid.UUID(raw or "")
    except ValueError:
        return None


def _orgs():
    return list(Organization.objects.order_by("name").values("id", "name"))


def _x(model):
    return model.objects.unscoped()


def _scope(qs, request, org_field="organization_id", site_field=None):
    org = _uuid(request.GET.get("org"))
    if org:
        qs = qs.filter(**{org_field: org})
    site = _uuid(request.GET.get("site"))
    if site and site_field:
        qs = qs.filter(**{site_field: site})
    return qs


def _count_by(qs, field):
    return dict(qs.order_by().values_list(field).annotate(n=Count("id")))


def _by_org(qs, **flt):
    return {k: v for k, v in qs.filter(**flt).order_by().values_list("organization_id").annotate(n=Count("id"))}


def paged(request, qs, cols, row_fn, title, empty="No records."):
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    return {"title": title, "cols": cols, "rows": [row_fn(o) for o in page], "page": page, "empty": empty}


def table(title, cols, rows, empty="No records."):
    return {"title": title, "cols": cols, "rows": rows, "empty": empty}


def _base(request, title, subtitle, *, filters=(), status_choices=None, **extra):
    ctx = {"title": title, "subtitle": subtitle, "filters": filters, "orgs": _orgs(),
           "f_org": request.GET.get("org", ""), "f_site": request.GET.get("site", ""),
           "f_status": request.GET.get("status", ""), "f_q": (request.GET.get("q") or "").strip(),
           "status_choices": status_choices or [], "kpis": [], "tables": []}
    if "site" in filters:
        sq = _scope(_x(Site), request)
        ctx["sites"] = list(sq.order_by("name").values("id", "name")[:300])
    ctx.update(extra)
    return ctx


def kpi(label, value, href=None, tone=""):
    return {"label": label, "value": value, "href": href, "tone": tone}


def _purl(name, *a):
    return reverse(f"platform_admin:{name}", args=a)


# ---- system health ------------------------------------------------------------------------------------------
def system_health():
    out = []
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        out.append(("Application", "ok", "Serving requests"))
        out.append(("Database", "ok", f"{connection.vendor} reachable"))
    except Exception:
        out.append(("Database", "error", "Query failed"))
    try:
        cache.set("health:probe", "1", 10)
        out.append(("Cache / Redis", "ok" if cache.get("health:probe") == "1" else "error", "Round-trip probe"))
    except Exception:
        out.append(("Cache / Redis", "error", "Probe failed"))
    sched = _x(MaintenanceSchedule).filter(is_active=True)
    errs = sched.exclude(last_error="").count()
    last = sched.exclude(last_run_at=None).order_by("-last_run_at").values_list("last_run_at", flat=True).first()
    state = "error" if errs else ("ok" if last else "warn")
    out.append(("PM scheduler", state, f"{errs} schedule error(s); last run {dt(last) or 'never'}"))
    lock = AuditLog.objects.filter(action="auth.lockout", occurred_at__gte=timezone.now() - datetime.timedelta(hours=24)).count()
    out.append(("Authentication", "warn" if lock else "ok", f"{lock} lockout(s) in last 24h"))
    return [{"name": n, "state": s, "detail": d} for n, s, d in out]


# ---- 1. overview --------------------------------------------------------------------------------------------
def overview(request):
    now = timezone.now()
    today = timezone.localdate()
    ctx = _base(request, "Platform overview", "Live, cross-organization control center. All figures are read from the database.")
    orgs = Organization.objects.all()
    users = User.objects.filter(is_platform_admin=False)
    wo, asset, sr = _x(WorkOrder), _x(Asset), _x(ServiceRequest)
    open_wo = wo.exclude(status__in=DONE_WO)
    overdue = open_wo.exclude(status__in=FINISHED_WO).filter(planned_end__lt=now).count()
    low = _x(StockBalance).filter(min_level__isnull=False, on_hand__lte=F("min_level")).count()
    due_pm = _x(MaintenanceSchedule).filter(is_active=True, next_due_date__lte=today).count()
    breaches = _x(SLABreach).exclude(status="CLOSED").count()
    health = system_health()
    alerts = sum(1 for h in health if h["state"] != "ok")
    ctx["kpis"] = [
        kpi("Organizations", orgs.count(), _purl("organizations")),
        kpi("Active", orgs.filter(status="ACTIVE").count()),
        kpi("Suspended", orgs.filter(status="SUSPENDED").count(), _purl("organizations") + "?status=SUSPENDED"),
        kpi("Sites", _x(Site).count(), _purl("sites")),
        kpi("Users", users.count(), _purl("users")),
        kpi("Active members", _x(Membership).filter(status="ACTIVE").count()),
        kpi("Pending invites", _x(Membership).filter(status="INVITED").count(), _purl("users") + "?status=INVITED"),
        kpi("Assets", asset.count(), _purl("assets")),
        kpi("Under maintenance", asset.filter(status="UNDER_MAINTENANCE").count(), _purl("assets") + "?status=UNDER_MAINTENANCE"),
        kpi("Out of service", asset.filter(status="OUT_OF_SERVICE").count(), _purl("assets") + "?status=OUT_OF_SERVICE", "danger"),
        kpi("Open service requests", sr.exclude(status="CLOSED").count(), _purl("service_ops")),
        kpi("Open work orders", open_wo.count(), _purl("work_orders")),
        kpi("Overdue work orders", overdue, _purl("work_orders") + "?overdue=1", "danger" if overdue else ""),
        kpi("Active PM schedules", _x(MaintenanceSchedule).filter(is_active=True).count(), _purl("maintenance")),
        kpi("PM due / overdue", due_pm, _purl("maintenance"), "warn" if due_pm else ""),
        kpi("Parts in catalogue", _x(Part).count(), _purl("inventory")),
        kpi("Low-stock lines", low, _purl("inventory"), "warn" if low else ""),
        kpi("Active SLA profiles", _x(SLAProfile).filter(is_active=True).count(), _purl("sla")),
        kpi("Open SLA breaches", breaches, _purl("sla"), "danger" if breaches else ""),
        kpi("System alerts", alerts, None, "danger" if alerts else ""),
    ]
    u, s, a = _by_org(_x(Membership), status="ACTIVE"), _by_org(_x(Site)), _by_org(asset)
    ow, br = _by_org(open_wo), _by_org(_x(SLABreach), status__in=["OPEN", "ACKNOWLEDGED"])
    last = {k: v for k, v in AuditLog.objects.filter(organization__isnull=False).order_by().values_list("organization_id").annotate(m=Max("occurred_at"))}
    rows = [[L(o.name, _purl("organization_detail", o.pk)), T(u.get(o.pk, 0)), T(s.get(o.pk, 0)), T(a.get(o.pk, 0)),
             T(ow.get(o.pk, 0)), T(br.get(o.pk, 0)), T(dt(last.get(o.pk))), B(o.status)] for o in orgs.order_by("name")]
    ctx["tables"] = [table("Organization health", ["Organization", "Users", "Sites", "Assets", "Open WO", "SLA breaches", "Last activity", "Status"], rows, "No organizations yet."),
                     {"title": "System health", "health": health}]
    return ctx


# ---- 3. sites -----------------------------------------------------------------------------------------------
def sites(request):
    ctx = _base(request, "Sites & Locations", "Organization → site → zone hierarchy across every tenant.",
                filters=("org", "status", "q"), status_choices=Site.Status.choices)
    qs = _scope(_x(Site).select_related("organization"), request)
    if ctx["f_status"]:
        qs = qs.filter(status=ctx["f_status"])
    if ctx["f_q"]:
        qs = qs.filter(Q(name__icontains=ctx["f_q"]) | Q(code__icontains=ctx["f_q"]))
    zc, ac = _count_by(_x(Zone), "site_id"), _count_by(_x(Asset), "site_id")
    wc, uc = _count_by(_x(WorkOrder).exclude(status__in=DONE_WO), "site_id"), _count_by(MembershipRole.objects.filter(site__isnull=False), "site_id")
    ctx["kpis"] = [kpi("Sites", qs.count()), kpi("Active", qs.filter(status="ACTIVE").count()),
                   kpi("Zones / areas", _scope(_x(Zone), request).count()), kpi("Organizations", qs.values("organization_id").distinct().count())]
    ctx["tables"] = [paged(request, qs.order_by("organization__name", "code"),
                           ["Organization", "Code", "Site", "City", "Zones", "Assets", "Open WO", "Site-scoped users", "Status"],
                           lambda s: [T(s.organization.name), T(s.code), L(s.name, _purl("site_detail", s.pk)), T(s.city), T(zc.get(s.pk, 0)),
                                      T(ac.get(s.pk, 0)), T(wc.get(s.pk, 0)), T(uc.get(s.pk, 0)), B(s.status)], "Sites")]
    return ctx


def site_detail(pk):
    s = _x(Site).select_related("organization").filter(pk=pk).first()
    if not s:
        return None
    zones = _x(Zone).filter(site=s).order_by("code", "name")
    wo = _x(WorkOrder).filter(site=s).exclude(status__in=DONE_WO).select_related("asset")[:20]
    return {"title": f"{s.code} · {s.name}", "subtitle": f"Site of {s.organization.name}", "back": _purl("sites"),
            "facts": [("Organization", s.organization.name), ("Status", s.status), ("Address", ", ".join(x for x in [s.address, s.city, s.state_region, s.country] if x) or "—"),
                      ("Timezone", s.timezone), ("Contact", s.contact_name or "—"),
                      ("Assets", _x(Asset).filter(site=s).count()), ("Open work orders", len(wo)),
                      ("Service requests", _x(ServiceRequest).filter(site=s).count()),
                      ("Maintenance plans", _x(MaintenancePlan).filter(site=s).count()),
                      ("Warehouses", _x(Warehouse).filter(site=s).count()),
                      ("Site-scoped users", MembershipRole.objects.filter(site=s).values("membership").distinct().count()),
                      ("SLA breaches (open)", _x(SLABreach).filter(site=s).exclude(status="CLOSED").count())],
            "tables": [table("Zones / service areas", ["Code", "Name", "Type", "Status"], [[T(z.code), T(z.name), T(z.zone_type), B(z.status)] for z in zones], "No zones."),
                       table("Open work orders", ["Number", "Title", "Asset", "Priority", "Status"], [[L(w.number, _purl("work_order_detail", w.pk)), T(w.title), T(w.asset.asset_tag), B(w.priority), B(w.status)] for w in wo], "None open.")],
            "audit_for": s.pk}


# ---- 4. users -----------------------------------------------------------------------------------------------
def users(request):
    ctx = _base(request, "Users", "Every identity and membership on the platform. Platform admins hold no tenant permissions.",
                filters=("org", "status", "q"), status_choices=Membership.Status.choices)
    qs = _scope(_x(Membership).select_related("user", "organization"), request)
    if ctx["f_status"]:
        qs = qs.filter(status=ctx["f_status"])
    if ctx["f_q"]:
        qs = qs.filter(Q(user__email__icontains=ctx["f_q"]) | Q(user__full_name__icontains=ctx["f_q"]))
    allm = _scope(_x(Membership), request)
    since = timezone.now() - datetime.timedelta(hours=24)
    ctx["kpis"] = [kpi("Memberships", allm.count()), kpi("Active", allm.filter(status="ACTIVE").count()),
                   kpi("Pending (invited)", allm.filter(status="INVITED").count()), kpi("Suspended", allm.filter(status="SUSPENDED").count()),
                   kpi("Disabled identities", User.objects.filter(is_active=False).count()),
                   kpi("Lockouts (24h)", AuditLog.objects.filter(action="auth.lockout", occurred_at__gte=since).count(), None, "warn")]
    roles = {}
    for mr in MembershipRole.objects.filter(membership__in=qs.values("pk")).select_related("role", "site"):
        roles.setdefault(mr.membership_id, []).append(mr)

    def row(m):
        mrs = roles.get(m.pk, [])
        return [T(m.user.display_name), T(m.user.email), T(m.organization.name), T(", ".join(sorted({r.role.name for r in mrs}))),
                T(", ".join(sorted({r.site.name if r.site else "All sites" for r in mrs}))), B(m.status),
                T(dt(m.user.last_login)), T("Active" if m.user.is_active else "Disabled")]
    ctx["tables"] = [paged(request, qs.order_by("organization__name", "user__full_name"),
                           ["Name", "Email", "Organization", "Role(s)", "Site scope", "Membership", "Last login", "Identity"], row, "Memberships")]
    return ctx


# ---- 5. roles & permissions -------------------------------------------------------------------------------------
def roles(request):
    ctx = _base(request, "Roles & Permissions", "Configured RBAC per organization. Owner roles implicitly hold every permission.", filters=("org",))
    qs = _scope(_x(Role).select_related("organization"), request)
    pc = _count_by(Role.permissions.through.objects.all(), "role_id")
    uc = {k: v for k, v in MembershipRole.objects.order_by().values_list("role_id").annotate(n=Count("membership", distinct=True))}
    total_perms = Permission.objects.count()
    ctx["kpis"] = [kpi("Roles", qs.count()), kpi("System roles", qs.exclude(system_key="").count()), kpi("Custom roles", qs.filter(system_key="").count()),
                   kpi("Permissions in catalogue", total_perms), kpi("Role assignments", MembershipRole.objects.filter(role__in=qs.values("pk")).count())]
    ctx["tables"] = [paged(request, qs.order_by("organization__name", "name"), ["Organization", "Role", "Type", "Users", "Permissions", "Coverage"],
                           lambda r: [T(r.organization.name), T(r.name), T("System" if r.system_key else "Custom"), T(uc.get(r.pk, 0)),
                                      T("All (owner)" if r.is_owner else pc.get(r.pk, 0)), BAR(f"{total_perms if r.is_owner else pc.get(r.pk, 0)}/{total_perms}", 100 * (total_perms if r.is_owner else pc.get(r.pk, 0)) / max(total_perms, 1))], "Roles")]
    org = _uuid(request.GET.get("org")) or (ctx["orgs"][0]["id"] if ctx["orgs"] else None)
    if org:
        rs = list(_x(Role).filter(organization_id=org).order_by("name")[:12])
        grants = set(Role.permissions.through.objects.filter(role__in=rs).values_list("role_id", "permission__code"))
        mod = request.GET.get("module", "")
        perms = Permission.objects.all() if not mod else Permission.objects.filter(module=mod)
        rows = [[T(p.code)] + [T("✓" if (r.is_owner or (r.pk, p.code) in grants) else "·") for r in rs] for p in perms[:200]]
        ctx["tables"].append(table(f"Permission matrix ({next((o['name'] for o in ctx['orgs'] if o['id'] == org), '')})",
                                   ["Permission"] + [r.name for r in rs], rows))
    return ctx


# ---- 6. assets ---------------------------------------------------------------------------------------------------
def assets(request):
    ctx = _base(request, "Assets", "Global asset visibility and lifecycle (monitoring only).", filters=("org", "site", "status", "q"),
                status_choices=Asset.Status.choices)
    base = _scope(_x(Asset), request, site_field="site_id")
    qs = base.select_related("organization", "site", "category")
    if ctx["f_status"]:
        qs = qs.filter(status=ctx["f_status"])
    if ctx["f_q"]:
        qs = qs.filter(Q(name__icontains=ctx["f_q"]) | Q(asset_tag__icontains=ctx["f_q"]))
    sc = _count_by(base, "status")
    ctx["kpis"] = [kpi("Total assets", base.count())] + [kpi(label, sc.get(v, 0), _purl("assets") + f"?status={v}") for v, label in Asset.Status.choices]
    ctx["tables"] = [paged(request, qs.order_by("organization__name", "asset_tag"), ["Organization", "Tag", "Asset", "Category", "Site", "Warranty", "Status"],
                           lambda a: [T(a.organization.name), T(a.asset_tag), L(a.name, _purl("asset_detail", a.pk)), T(a.category.name), T(a.site.name), T(a.warranty_ref), B(a.status)], "Assets")]
    return ctx


def asset_detail(pk):
    a = _x(Asset).select_related("organization", "site", "category", "zone").filter(pk=pk).first()
    if not a:
        return None
    wos = _x(WorkOrder).filter(asset=a)[:15]
    srs = _x(ServiceRequest).filter(asset=a)[:15]
    plans = _x(MaintenancePlan).filter(asset=a)
    return {"title": f"{a.asset_tag} · {a.name}", "subtitle": f"Asset of {a.organization.name}", "back": _purl("assets"),
            "facts": [("Organization", a.organization.name), ("Status", a.status), ("Category", a.category.name), ("Site", a.site.name), ("Zone", a.zone.name if a.zone else "—"),
                      ("Manufacturer / model", f"{a.manufacturer} {a.model}".strip() or "—"), ("Serial", a.serial_number or "—"), ("Purchased", a.purchase_date or "—"),
                      ("Commissioned", a.commission_date or "—"), ("Warranty ref", a.warranty_ref or "—"), ("Components", _x(AssetComponent).filter(parent=a).count()),
                      ("Meters", _x(AssetMeter).filter(asset=a).count()), ("Documents", _x(AssetDocument).filter(asset=a).count()), ("Maintenance plans", plans.count())],
            "tables": [table("Work orders", ["Number", "Title", "Priority", "Status"], [[L(w.number, _purl("work_order_detail", w.pk)), T(w.title), B(w.priority), B(w.status)] for w in wos], "None."),
                       table("Service requests", ["Number", "Title", "Severity", "Status"], [[L(s.number, _purl("service_detail", s.pk)), T(s.title), B(s.severity), B(s.status)] for s in srs], "None."),
                       table("Maintenance plans", ["Plan", "Active"], [[T(p.name), T("Yes" if p.is_active else "No")] for p in plans], "None.")],
            "audit_for": a.pk}


# ---- 7. service operations ---------------------------------------------------------------------------------------
def service_ops(request):
    ctx = _base(request, "Service Operations", "Global service request / incident lifecycle.", filters=("org", "site", "status", "q"),
                status_choices=ServiceRequest.Status.choices)
    base = _scope(_x(ServiceRequest), request, site_field="site_id")
    qs = base.select_related("organization", "asset", "site", "reported_by__user")
    if ctx["f_status"]:
        qs = qs.filter(status=ctx["f_status"])
    if ctx["f_q"]:
        qs = qs.filter(Q(number__icontains=ctx["f_q"]) | Q(title__icontains=ctx["f_q"]))
    sc = _count_by(base, "status")
    sla = {k: v for k, v in _x(SLATracking).filter(request__in=qs.values("pk")).values_list("request_id", "resolution_state")}
    now = timezone.now()
    ctx["kpis"] = [kpi(label, sc.get(v, 0), _purl("service_ops") + f"?status={v}") for v, label in ServiceRequest.Status.choices]
    ctx["tables"] = [paged(request, qs.order_by("-created_at"), ["Organization", "Number", "Title", "Requester", "Asset", "Severity", "Status", "SLA", "Age"],
                           lambda s: [T(s.organization.name), L(s.number, _purl("service_detail", s.pk)), T(s.title), T(s.reported_by.user.display_name), T(s.asset.asset_tag),
                                      B(s.severity), B(s.status), B(sla[s.pk]) if s.pk in sla else T(None), T(f"{(now - s.created_at).days}d")], "Service requests")]
    return ctx


def service_detail(pk):
    s = _x(ServiceRequest).select_related("organization", "asset", "site", "reported_by__user").filter(pk=pk).first()
    if not s:
        return None
    wos = _x(WorkOrder).filter(source_request=s)
    slas = _x(SLATracking).filter(request=s)
    return {"title": f"{s.number} · {s.title}", "subtitle": f"Request of {s.organization.name}", "back": _purl("service_ops"),
            "facts": [("Status", s.status), ("Kind", s.kind), ("Severity", s.severity), ("Impact", s.service_impact), ("Asset", s.asset.asset_tag), ("Site", s.site.name),
                      ("Reported by", s.reported_by.user.display_name), ("Occurred", dt(s.occurred_at)), ("Triaged", dt(s.triaged_at) or "—"), ("Decided", dt(s.decided_at) or "—"),
                      ("Decision reason", s.decision_reason or "—"), ("Resolved", dt(s.resolved_at) or "—"), ("Confirmed", dt(s.confirmed_at) or "—"), ("Closed", dt(s.closed_at) or "—")],
            "tables": [table("Work orders", ["Number", "Title", "Status"], [[L(w.number, _purl("work_order_detail", w.pk)), T(w.title), B(w.status)] for w in wos], "No work order yet."),
                       table("SLA tracking", ["Profile", "Response", "Resolution", "Status"], [[T(t.profile.name), B(t.response_state), B(t.resolution_state), B(t.status)] for t in slas.select_related("profile")], "None.")],
            "audit_for": s.pk}


# ---- 8. work orders ----------------------------------------------------------------------------------------------
def work_orders(request):
    ctx = _base(request, "Work Orders", "Global work-order monitoring across every organization.", filters=("org", "site", "status", "q"),
                status_choices=WorkOrder.Status.choices)
    base = _scope(_x(WorkOrder), request, site_field="site_id")
    qs = base.select_related("organization", "asset", "site", "assigned_to__user")
    now = timezone.now()
    if ctx["f_status"]:
        qs = qs.filter(status=ctx["f_status"])
    if request.GET.get("overdue"):
        qs = qs.exclude(status__in=FINISHED_WO).filter(planned_end__lt=now)
    if ctx["f_q"]:
        qs = qs.filter(Q(number__icontains=ctx["f_q"]) | Q(title__icontains=ctx["f_q"]))
    sc = _count_by(base, "status")
    ctx["kpis"] = [kpi("Total", base.count()), kpi("Open", base.exclude(status__in=DONE_WO).count()),
                   kpi("Overdue", base.exclude(status__in=FINISHED_WO).filter(planned_end__lt=now).count(), _purl("work_orders") + "?overdue=1", "danger")] + \
                  [kpi(label, sc.get(v, 0), _purl("work_orders") + f"?status={v}") for v, label in WorkOrder.Status.choices]
    sla = {k: v for k, v in _x(SLATracking).filter(work_order__in=qs.values("pk")).values_list("work_order_id", "resolution_state")}
    ctx["tables"] = [paged(request, qs.order_by("-created_at"), ["Organization", "Number", "Title", "Asset", "Site", "Technician", "Priority", "Status", "SLA", "Due", "Age"],
                           lambda w: [T(w.organization.name), L(w.number, _purl("work_order_detail", w.pk)), T(w.title), T(w.asset.asset_tag), T(w.site.name),
                                      T(w.assigned_to.user.display_name if w.assigned_to else None), B(w.priority), B(w.status), B(sla[w.pk]) if w.pk in sla else T(None),
                                      T(dt(w.planned_end, "%d %b %Y")), T(f"{(now - w.created_at).days}d")], "Work orders")]
    return ctx


def work_order_detail(pk):
    w = _x(WorkOrder).select_related("organization", "asset", "site", "assigned_to__user", "source_request").filter(pk=pk).first()
    if not w:
        return None
    lines = _x(WorkOrderPart).filter(work_order=w).select_related("part")
    slas = _x(SLATracking).filter(work_order=w).select_related("profile")
    return {"title": f"{w.number} · {w.title}", "subtitle": f"Work order of {w.organization.name}", "back": _purl("work_orders"),
            "facts": [("Status", w.status), ("Type", w.work_type), ("Priority", w.priority), ("Asset", w.asset.asset_tag), ("Site", w.site.name),
                      ("Technician", w.assigned_to.user.display_name if w.assigned_to else "Unassigned"), ("Source", w.source_type or "Direct"),
                      ("Planned", f"{dt(w.planned_start) or '—'} → {dt(w.planned_end) or '—'}"), ("Dispatched", dt(w.dispatched_at) or "—"), ("Started", dt(w.started_at) or "—"),
                      ("Completed", dt(w.completed_at) or "—"), ("Review started", dt(w.review_started_at) or "—"), ("Closed", dt(w.closed_at) or "—"),
                      ("Hold reason", w.hold_reason or "—")],
            "tables": [table("Part lines", ["Part", "Requested", "Issued", "Consumed", "Returned", "Status"], [[T(ln.part.part_number), T(ln.quantity_requested), T(ln.quantity_issued), T(ln.quantity_consumed), T(ln.quantity_returned), B(ln.status)] for ln in lines], "No parts."),
                       table("SLA tracking", ["Profile", "Response", "Resolution", "Status"], [[T(t.profile.name), B(t.response_state), B(t.resolution_state), B(t.status)] for t in slas], "None.")],
            "audit_for": w.pk}


# ---- 9. maintenance ----------------------------------------------------------------------------------------------
def maintenance(request):
    ctx = _base(request, "Maintenance", "Preventive-maintenance plans, schedules, generated work and scheduler health.", filters=("org", "site", "q"))
    today = timezone.localdate()
    plans = _scope(_x(MaintenancePlan), request, site_field="site_id")
    sched = _scope(_x(MaintenanceSchedule), request).filter(plan__in=plans.values("pk"))
    cycles = _scope(_x(MaintenanceCycle), request).filter(schedule__in=sched.values("pk"))
    pm_wo = _scope(_x(WorkOrder), request, site_field="site_id").filter(source_type="PREVENTIVE_MAINTENANCE")
    errs = sched.exclude(last_error="")
    last = sched.exclude(last_run_at=None).order_by("-last_run_at").values_list("last_run_at", flat=True).first()
    ctx["kpis"] = [kpi("Plans", plans.count()), kpi("Active plans", plans.filter(is_active=True).count()), kpi("Active schedules", sched.filter(is_active=True).count()),
                   kpi("Due today or earlier", sched.filter(is_active=True, next_due_date__lte=today).count(), None, "warn"),
                   kpi("Overdue (past due date)", sched.filter(is_active=True, next_due_date__lt=today).count(), None, "danger"),
                   kpi("Cycles generated", cycles.count()), kpi("PM work orders open", pm_wo.exclude(status__in=DONE_WO).count()),
                   kpi("PM work orders closed", pm_wo.filter(status="CLOSED").count()), kpi("Missed cycles (collapsed)", cycles.aggregate(s=Sum("skipped"))["s"] or 0),
                   kpi("Scheduler errors", errs.count(), None, "danger" if errs.exists() else ""), kpi("Scheduler last run", dt(last) or "never")]
    qs = sched.select_related("plan__asset", "organization").order_by("next_due_date", "plan__name")
    if ctx["f_q"]:
        qs = qs.filter(plan__name__icontains=ctx["f_q"])
    ctx["tables"] = [paged(request, qs, ["Organization", "Plan", "Asset", "Trigger", "Cadence", "Next due", "Active", "Last run", "Last error"],
                           lambda s: [T(s.organization.name), T(s.plan.name), T(s.plan.asset.asset_tag), T(s.trigger_type), T(s.describe()), T(s.next_due_date),
                                      B("ACTIVE" if s.is_active else "INACTIVE"), T(dt(s.last_run_at)), T(s.last_error)], "Schedules")]
    return ctx


# ---- 10. inventory -----------------------------------------------------------------------------------------------
def inventory(request):
    ctx = _base(request, "Inventory", "Warehouses, stock and the part-request lifecycle across tenants.", filters=("org", "site", "q"))
    today = timezone.localdate()
    wh = _scope(_x(Warehouse), request, site_field="site_id")
    bal = _scope(_x(StockBalance), request).filter(warehouse__in=wh.values("pk"))
    lines = _scope(_x(WorkOrderPart), request)
    mv = _scope(_x(StockMovement), request).filter(warehouse__in=wh.values("pk"))
    lc = _count_by(lines, "status")
    low = bal.filter(min_level__isnull=False, on_hand__lte=F("min_level"))
    ctx["kpis"] = [kpi("Warehouses", wh.count()), kpi("Parts", _scope(_x(Part), request).count()), kpi("Low-stock lines", low.count(), None, "warn"),
                   kpi("Out of stock", bal.filter(on_hand__lte=0).count(), None, "danger")] + \
                  [kpi(label, lc.get(v, 0)) for v, label in WorkOrderPart.Status.choices] + \
                  [kpi(f"{t} today", mv.filter(movement_type=t, created_at__date=today).count()) for t in ("ISSUE", "RETURN")]
    qs = mv.select_related("organization", "warehouse", "part", "work_order").order_by("-created_at")
    if ctx["f_q"]:
        qs = qs.filter(part__name__icontains=ctx["f_q"])
    ctx["tables"] = [paged(request, qs, ["When", "Organization", "Warehouse", "Part", "Movement", "Qty", "Work order", "Reference"],
                           lambda m: [T(dt(m.created_at)), T(m.organization.name), T(m.warehouse.code), T(m.part.part_number), B(m.movement_type), T(m.quantity),
                                      L(m.work_order.number, _purl("work_order_detail", m.work_order_id)) if m.work_order_id else T(None), T(m.reference)], "Stock movements")]
    ctx["tables"].append(table("Low-stock balances", ["Organization", "Warehouse", "Part", "On hand", "Reserved", "Min level"],
                               [[T(b.organization.name), T(b.warehouse.code), T(b.part.part_number), T(b.on_hand), T(b.reserved), T(b.min_level)] for b in low.select_related("organization", "warehouse", "part")[:20]], "No low-stock lines."))
    return ctx


# ---- 11. SLA -----------------------------------------------------------------------------------------------------
def sla(request):
    ctx = _base(request, "SLA & Policies", "Policy coverage, running timers and breaches per organization.", filters=("org", "site"))
    now = timezone.now()
    prof = _scope(_x(SLAProfile), request)
    trk = _scope(_x(SLATracking), request, site_field="site_id")
    active = list(trk.filter(status="ACTIVE").only("started_at", "resolution_due_at", "warning_percent", "resolution_state", "response_state"))
    warn = breached = 0
    for t in active:
        if "BREACHED" in (t.resolution_state, t.response_state) or t.resolution_due_at < now:
            breached += 1
        elif t.started_at + (t.resolution_due_at - t.started_at) * t.warning_percent / 100 <= now:
            warn += 1
    br = _scope(_x(SLABreach), request, site_field="site_id")
    ctx["kpis"] = [kpi("Active policies", prof.filter(is_active=True).count()), kpi("Running timers", len(active)), kpi("Healthy", len(active) - warn - breached),
                   kpi("Warning", warn, None, "warn"), kpi("Breached (running)", breached, None, "danger"), kpi("Paused", trk.filter(status="PAUSED").count()),
                   kpi("Open breaches", br.exclude(status="CLOSED").count(), None, "danger"), kpi("Escalated", br.filter(escalation_level__gt=0).count())]
    pc, tc, bc = _by_org(_x(SLAProfile), is_active=True), _by_org(_x(SLATracking), status="ACTIVE"), _by_org(_x(SLABreach), status__in=["OPEN", "ACKNOWLEDGED"])
    ctx["tables"] = [table("Organizations", ["Organization", "Active profiles", "Running timers", "Open breaches"],
                           [[T(o["name"]), T(pc.get(o["id"], 0)), T(tc.get(o["id"], 0)), T(bc.get(o["id"], 0))] for o in ctx["orgs"]]),
                     paged(request, prof.select_related("organization", "site").order_by("organization__name", "name"), ["Organization", "Profile", "Applies to", "Scope", "Active"],
                           lambda p: [T(p.organization.name), T(p.name), T(p.applies_to), T(p.site.name if p.site else "Whole organization"), B("ACTIVE" if p.is_active else "INACTIVE")], "SLA profiles"),
                     table("Recent breaches", ["Detected", "Organization", "Target", "Priority", "Escalation", "Status"],
                           [[T(dt(b.detected_at)), T(b.organization.name), T(b.target_kind), T(b.priority), T(b.escalation_level), B(b.status)] for b in br.select_related("organization").order_by("-detected_at")[:15]], "No breaches.")]
    return ctx


# ---- 12. dashboards ----------------------------------------------------------------------------------------------
def dashboards(request):
    ctx = _base(request, "Operational Dashboards", "Analytics and organization comparisons computed from live data.", filters=("org",))
    now = timezone.now()
    wo = _scope(_x(WorkOrder), request)
    total, closed, opn = _by_org(wo), _by_org(wo, status="CLOSED"), _by_org(wo.exclude(status__in=DONE_WO))
    pm_t, pm_c = _by_org(wo, source_type="PREVENTIVE_MAINTENANCE"), _by_org(wo, source_type="PREVENTIVE_MAINTENANCE", status="CLOSED")
    br = _by_org(_scope(_x(SLABreach), request))
    cons = {k: v for k, v in _scope(_x(StockMovement), request).filter(movement_type="ISSUE").order_by().values_list("organization_id").annotate(q=Sum("quantity"))}
    mx = max(total.values(), default=1)
    ctx["tables"] = [table("Organization comparison", ["Organization", "WO volume", "Open backlog", "Completion rate", "PM compliance", "SLA breaches", "Parts issued"],
                           [[T(o["name"]), BAR(total.get(o["id"], 0), 100 * total.get(o["id"], 0) / mx), T(opn.get(o["id"], 0)),
                             T(f"{100 * closed.get(o['id'], 0) // total[o['id']]}%" if total.get(o["id"]) else "—"),
                             T(f"{100 * pm_c.get(o['id'], 0) // pm_t[o['id']]}%" if pm_t.get(o["id"]) else "—"), T(br.get(o["id"], 0)), T(cons.get(o["id"], Decimal(0)))] for o in ctx["orgs"]]),
                     table("Work-order aging (open)", ["Age bucket", "Work orders"],
                           [[T(label), T(wo.exclude(status__in=DONE_WO).filter(created_at__lte=now - datetime.timedelta(days=lo), **({"created_at__gt": now - datetime.timedelta(days=hi)} if hi else {})).count())]
                            for label, lo, hi in (("0–7 days", 0, 7), ("8–30 days", 7, 30), ("31–90 days", 30, 90), ("90+ days", 90, None))]),
                     table("Failure frequency: top assets by corrective work orders", ["Organization", "Asset", "Corrective WOs"],
                           [[T(r["organization__name"]), T(f"{r['asset__asset_tag']} {r['asset__name']}"), T(r["n"])] for r in
                            wo.filter(work_type="CORRECTIVE").order_by().values("organization__name", "asset__asset_tag", "asset__name").annotate(n=Count("id")).order_by("-n")[:10]]),
                     table("Technician productivity (closed WOs)", ["Organization", "Technician", "Closed"],
                           [[T(r["organization__name"]), T(r["assigned_to__user__full_name"]), T(r["n"])] for r in
                            wo.filter(status="CLOSED", assigned_to__isnull=False).order_by().values("organization__name", "assigned_to__user__full_name").annotate(n=Count("id")).order_by("-n")[:10]])]
    return ctx


# ---- 13. audit ---------------------------------------------------------------------------------------------------
def audit_queryset(request):
    from apps.audit import selectors as audit_selectors
    qs = audit_selectors.filter_logs(AuditLog.objects.select_related("actor", "organization"), request.GET)
    org = _uuid(request.GET.get("organization") or request.GET.get("org"))
    if org:
        qs = qs.filter(organization_id=org)
    if request.GET.get("module"):
        qs = qs.filter(action__startswith=request.GET["module"] + ".")
    if request.GET.get("security"):
        qs = qs.filter(Q(action__startswith="auth.") | Q(action__startswith="rbac.") | Q(action__startswith="role."))
    return qs


def audit_csv(qs, response):
    w = csv.writer(response)
    w.writerow(["occurred_at", "organization", "action", "actor", "target_type", "target_id", "target", "ip"])
    for e in qs[:5000]:
        w.writerow([e.occurred_at.isoformat(), e.organization.name if e.organization else "", e.action, e.actor_email, e.target_type, e.target_id, e.target_repr, e.ip_address or ""])


# ---- 14. settings / security / profile ---------------------------------------------------------------------------
def _mask(url):
    return (url.split("://")[0] + "://***") if "://" in str(url) else ("not set" if not url else "configured")


def system_settings(request):
    ctx = _base(request, "System Settings", "Effective platform configuration (read-only). Values come from the running deployment; secrets are never shown.")
    s = settings
    groups = {
        "Platform": [("Debug mode", s.DEBUG), ("Time zone", s.TIME_ZONE), ("Database engine", connection.vendor)],
        "Authentication & session": [("Session lifetime (hours)", s.SESSION_COOKIE_AGE // 3600), ("Login failure limit (Axes)", getattr(s, "AXES_FAILURE_LIMIT", "—")),
                                     ("Lockout cool-off", str(getattr(s, "AXES_COOLOFF_TIME", "—"))), ("Password validators", len(s.AUTH_PASSWORD_VALIDATORS)),
                                     ("MFA", "Not implemented (CLARIFICATION REQUIRED, not in HPE PRD scope)")],
        "Email & notifications": [("Email backend", s.EMAIL_BACKEND.rsplit(".", 2)[-2]), ("Default from", getattr(s, "DEFAULT_FROM_EMAIL", "—"))],
        "Files": [("Upload limit (MB)", s.UPLOAD_MAX_BYTES // 1048576)],
        "Background jobs": [("Celery broker", _mask(getattr(s, "CELERY_BROKER_URL", ""))), ("Beat schedules", len(getattr(s, "CELERY_BEAT_SCHEDULE", {})) )],
        "Audit": [("Audit entries", AuditLog.objects.count()), ("Immutability", "Model guards + PostgreSQL trigger")],
        "Platform controls": [("Maintenance mode / feature flags", "Not implemented; no unsafe controls are exposed"), ("Support mode (tenant write access)", "Not implemented by design: monitoring is read-only")],
    }
    ctx["tables"] = [table(g, ["Setting", "Value"], [[T(k), T(str(v))] for k, v in rows]) for g, rows in groups.items()]
    ctx["tables"].append({"title": "System health", "health": system_health()})
    return ctx


def security(request):
    from django.contrib.sessions.models import Session
    ctx = _base(request, "Security", "Your account's sessions and platform-wide security events.")
    now = timezone.now()
    mine = 0
    for sess in Session.objects.filter(expire_date__gt=now)[:2000]:
        if sess.get_decoded().get("_auth_user_id") == str(request.user.pk):
            mine += 1
    hist = AuditLog.objects.filter(actor=request.user, action__startswith="auth.").order_by("-occurred_at")[:15]
    ev = AuditLog.objects.filter(action__startswith="auth.").exclude(action="auth.login").exclude(action="auth.logout").order_by("-occurred_at")[:20]
    ctx["kpis"] = [kpi("Your active sessions", mine), kpi("MFA", "Not enabled"), kpi("Lockouts (24h)", AuditLog.objects.filter(action="auth.lockout", occurred_at__gte=now - datetime.timedelta(hours=24)).count())]
    ctx["tables"] = [table("Your login history", ["When", "Event", "IP"], [[T(dt(e.occurred_at)), T(e.action), T(e.ip_address)] for e in hist], "None."),
                     table("Security events (platform-wide)", ["When", "Event", "Actor", "IP", "Organization"], [[T(dt(e.occurred_at)), T(e.action), T(e.actor_email), T(e.ip_address), T(e.organization.name if e.organization else None)] for e in ev.select_related("organization")], "None."),
                     ]
    ctx["actions"] = [("Change password", reverse("accounts:password_change"))]
    return ctx


def profile(request):
    u = request.user
    ctx = _base(request, "Profile", "Your Super Admin identity.")
    ctx["tables"] = [table("Account", ["Field", "Value"], [[T("Name"), T(u.full_name)], [T("Email"), T(u.email)], [T("Phone"), T(u.phone)], [T("Role"), T("Platform administrator")],
                                                          [T("Last login"), T(dt(u.last_login))], [T("Joined"), T(dt(u.date_joined))]])]
    ctx["actions"] = [("Edit profile", reverse("accounts:profile")), ("Change password", reverse("accounts:password_change"))]
    return ctx


SECTIONS = {"overview": overview, "sites": sites, "users": users, "roles": roles, "assets": assets, "service_ops": service_ops,
            "work_orders": work_orders, "maintenance": maintenance, "inventory": inventory, "sla": sla, "dashboards": dashboards,
            "settings": system_settings, "security": security, "profile": profile}
DETAILS = {"site_detail": site_detail, "asset_detail": asset_detail, "service_detail": service_detail, "work_order_detail": work_order_detail}
