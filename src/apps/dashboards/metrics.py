"""M14 operational metrics. Every number is an aggregate over persisted records of the caller's organization,
restricted to the sites the caller may see (INTERSECTION of ``report.view`` and the section's data permission) and,
optionally, one site and a date window. Nothing is stored or hard-coded; each KPI's formula, source tables and
filters are listed in ``KPI_DEFINITIONS`` (shown on the dashboards and in docs/modules/M14_DASHBOARDS.md).

Time conventions (OUR IMPLEMENTATION DECISIONS): the window is [from 00:00, to+1 day 00:00) in UTC; snapshot KPIs
(open work orders, asset status, stock) describe "now" and ignore the window; technician capacity is assumed to be
8 h per calendar day (HPE gives no shift data), so utilization = recorded labor hours / (days x 8 h).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.fields import DateTimeField
from django.db.models.functions import Coalesce, Greatest, Least, TruncDate
from django.utils import timezone

from apps.core.exceptions import ValidationFailed
from apps.rbac import services as rbac

CAPACITY_HOURS_PER_DAY = 8
MAX_DAYS = 400
PRE_COMPLETION = ("DRAFT", "PLANNED", "ASSIGNED", "DISPATCHED", "IN_PROGRESS", "ON_HOLD")
TERMINAL = ("CLOSED", "CANCELLED")

KPI_DEFINITIONS = {
    "open_work_orders": "Work orders not CLOSED or CANCELLED now. Source: workorders.WorkOrder.status.",
    "overdue_work": "Open work orders before completion (DRAFT .. ON_HOLD) whose planned end is in the past.",
    "completed": "Work orders whose completed_at falls in the window.",
    "mttr": "Mean time to repair = average (restored - failed) of incident downtimes that ENDED in the window. "
            "Source: incidents.Downtime.",
    "mtbf": "Mean time between failures = (assets in scope x window hours - downtime hours) / failures started in "
            "the window. Shown only when at least one failure exists. Source: assets.Asset, incidents.Downtime.",
    "downtime": "Sum of downtime overlapping the window, clipped to it (open downtime counts up to now).",
    "utilization": f"Labor hours recorded in the window / (days in window x {CAPACITY_HOURS_PER_DAY} h) per "
                   "technician. Source: workorders.WorkOrderLabor.",
    "sla_breaches": "SLA breaches whose due instant falls in the window. Source: sla.SLABreach.",
    "pm_compliance": "Time-based PM cycles due in the window (up to today): completed on or before the due date / "
                     "(on time + late + not completed). Cancelled work orders are excluded. Source: "
                     "maintenance.MaintenanceCycle, workorders.WorkOrder.completed_at.",
    "parts_consumption": "Net quantity issued to work orders = ISSUE - RETURN stock movements in the window. "
                         "Source: inventory.StockMovement.",
    "asset_status": "Assets by status now. Source: assets.Asset.status.",
}


# --- filters and scope ---------------------------------------------------------------------------------------------------


@dataclass
class Filters:
    site: object | None
    since: datetime.datetime
    until: datetime.datetime  # exclusive
    from_date: datetime.date
    to_date: datetime.date

    @property
    def days(self) -> int:
        return (self.to_date - self.from_date).days + 1

    @property
    def hours(self) -> Decimal:
        return Decimal(self.days * 24)


def _date(value, what):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(f"{what} must be a date (YYYY-MM-DD).", code="invalid_date") from exc


def parse_filters(params, membership, org) -> Filters:
    from apps.sites import selectors as site_selectors

    today = timezone.now().date()
    to_raw, from_raw = (params.get("to") or "").strip(), (params.get("from") or "").strip()
    to_date = _date(to_raw, "To") if to_raw else today
    from_date = _date(from_raw, "From") if from_raw else to_date - datetime.timedelta(days=29)
    if from_date > to_date:
        raise ValidationFailed("The start date is after the end date.", code="invalid_range")
    if (to_date - from_date).days + 1 > MAX_DAYS:
        raise ValidationFailed(f"The window is limited to {MAX_DAYS} days.", code="range_too_long")
    site = None
    raw_site = (params.get("site") or "").strip()
    if raw_site:
        site = site_selectors.get_site(membership, org, raw_site, "report.view")  # NotFound outside scope
    tz = datetime.UTC
    since = datetime.datetime.combine(from_date, datetime.time.min, tzinfo=tz)
    until = datetime.datetime.combine(to_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=tz)
    return Filters(site=site, since=since, until=until, from_date=from_date, to_date=to_date)


def sites_allowed(membership, *codes):
    """None = every site; otherwise the frozenset of site ids permitted by ALL codes."""
    result = None
    for code in codes:
        scope = rbac.site_scope(membership, code)
        if scope.all_sites:
            continue
        result = scope.site_ids if result is None else result & scope.site_ids
    return result


def _scope(qs, allowed, f: Filters, field="site_id"):
    if allowed is not None:
        qs = qs.filter(**{f"{field}__in": allowed})
    if f.site is not None:
        qs = qs.filter(**{field: f.site.pk})
    return qs


def can_see(membership, *codes) -> bool:
    return all(rbac.has_permission_anywhere(membership, c) for c in codes)


def _hours(td) -> float:
    return round(td.total_seconds() / 3600, 2) if td else 0.0


def _pct(num, den):
    return round(100 * num / den, 1) if den else None


def _label(user_name, email):
    return user_name or email or "—"


# --- sections --------------------------------------------------------------------------------------------------------------


def operations(m, org, f: Filters) -> dict:
    from apps.workorders.models import WorkOrder, WorkOrderLabor

    allowed = sites_allowed(m, "report.view", "work_order.view")
    now = timezone.now()
    wos = _scope(WorkOrder.objects.for_organization(org), allowed, f)
    window = lambda field: Q(**{f"{field}__gte": f.since, f"{field}__lt": f.until})  # noqa: E731
    k = wos.aggregate(
        open_total=Count("pk", filter=~Q(status__in=TERMINAL)),
        overdue=Count("pk", filter=Q(status__in=PRE_COMPLETION, planned_end__lt=now)),
        created=Count("pk", filter=window("created_at")),
        completed=Count("pk", filter=window("completed_at")),
        closed=Count("pk", filter=window("closed_at")),
    )
    open_qs = wos.exclude(status__in=TERMINAL)
    by_status = {r["status"]: r["n"] for r in open_qs.values("status").annotate(n=Count("pk"))}
    by_priority = {r["priority"]: r["n"] for r in open_qs.values("priority").annotate(n=Count("pk"))}
    by_type = {r["work_type"]: r["n"] for r in wos.filter(window("created_at")).values("work_type").annotate(
        n=Count("pk"))}
    labor = _scope(WorkOrderLabor.objects.for_organization(org), allowed, f, "work_order__site_id").filter(
        work_date__gte=f.from_date, work_date__lte=f.to_date)
    hours = {r["technician_id"]: r["h"] for r in labor.values("technician_id").annotate(h=Sum("hours"))}
    jobs = {r["assigned_to_id"]: r for r in open_qs.filter(assigned_to__isnull=False).values(
        "assigned_to_id", "assigned_to__user__full_name", "assigned_to__user__email").annotate(n=Count("pk"))}
    names = {}
    if hours.keys() - jobs.keys():
        from apps.tenancy.models import Membership

        for r in Membership.objects.for_organization(org).filter(pk__in=hours.keys() - jobs.keys()).values(
                "pk", "user__full_name", "user__email"):
            names[r["pk"]] = _label(r["user__full_name"], r["user__email"])
    capacity = Decimal(f.days * CAPACITY_HOURS_PER_DAY)
    techs = []
    for tid in set(hours) | set(jobs):
        row = jobs.get(tid)
        h = hours.get(tid, Decimal(0))
        techs.append({"name": _label(row["assigned_to__user__full_name"], row["assigned_to__user__email"])
                      if row else names.get(tid, "—"),
                      "open_jobs": row["n"] if row else 0, "hours": float(h), "utilization": _pct(h, capacity)})
    techs.sort(key=lambda t: (-t["hours"], t["name"]))
    overdue_list = list(open_qs.filter(status__in=PRE_COMPLETION, planned_end__lt=now).order_by("planned_end")
                        .values("pk", "number", "title", "priority", "planned_end", "asset__asset_tag")[:10])
    return {"kpis": {**k, "capacity_hours_per_day": CAPACITY_HOURS_PER_DAY},
            "open_by_status": by_status, "open_by_priority": by_priority, "created_by_type": by_type,
            "technicians": techs, "overdue_list": overdue_list}


def assets(m, org, f: Filters) -> dict:
    from apps.assets.models import Asset
    from apps.incidents.models import Downtime

    allowed = sites_allowed(m, "report.view", "asset.view")
    now = timezone.now()
    asset_qs = _scope(Asset.objects.for_organization(org), allowed, f)
    status = {r["status"]: r["n"] for r in asset_qs.values("status").annotate(n=Count("pk"))}
    in_scope = asset_qs.filter(created_at__lt=f.until).exclude(status__in=("RETIRED", "DISPOSED")).count()
    dts = _scope(Downtime.objects.for_organization(org), allowed, f, "asset__site_id")
    clip = ExpressionWrapper(
        Least(Coalesce("ended_at", Value(now, output_field=DateTimeField())),
              Value(f.until, output_field=DateTimeField()))
        - Greatest(F("started_at"), Value(f.since, output_field=DateTimeField())), output_field=DurationField())
    overlapping = dts.filter(started_at__lt=f.until).filter(Q(ended_at__isnull=True) | Q(ended_at__gt=f.since))
    down = overlapping.annotate(ov=clip).aggregate(total=Sum("ov"))["total"]
    top = [{"asset": f"{r['asset__asset_tag']} · {r['asset__name']}", "hours": _hours(r["t"])}
           for r in overlapping.annotate(ov=clip).values("asset__asset_tag", "asset__name").annotate(
               t=Sum("ov")).order_by("-t")[:5]]
    failures = dts.filter(started_at__gte=f.since, started_at__lt=f.until).count()
    repaired = dts.filter(ended_at__gte=f.since, ended_at__lt=f.until)
    mttr = repaired.aggregate(a=Avg(F("ended_at") - F("started_at"), output_field=DurationField()))["a"]
    down_hours = _hours(down)
    mtbf = None
    if failures and in_scope:
        mtbf = round(max(float(f.hours) * in_scope - down_hours, 0) / failures, 2)
    expiring = None
    if rbac.has_permission_anywhere(m, "contract.view"):
        from apps.contracts.models import CoverageAgreement

        today = timezone.now().date()
        cscope = sites_allowed(m, "report.view", "contract.view")
        expiring = _scope(CoverageAgreement.objects.for_organization(org), cscope, f).filter(
            is_active=True, end_date__gte=today, end_date__lte=today + datetime.timedelta(days=30)).count()
    return {"status": status, "assets_total": sum(status.values()),
            "kpis": {"failures": failures, "downtime_hours": down_hours,
                     "mttr_hours": _hours(mttr) if mttr else None, "mtbf_hours": mtbf,
                     "assets_in_scope": in_scope, "agreements_expiring_30d": expiring},
            "top_downtime": top}


def maintenance(m, org, f: Filters) -> dict:
    from apps.maintenance.models import MaintenanceCycle, MaintenanceSchedule
    from apps.workorders.models import WorkOrder

    allowed = sites_allowed(m, "report.view", "maintenance.view")
    today = timezone.now().date()
    last = min(f.to_date, today)
    cycles = _scope(MaintenanceCycle.objects.for_organization(org), allowed, f, "schedule__plan__site_id")
    due = cycles.filter(due_date__gte=f.from_date, due_date__lte=last).exclude(work_order__status="CANCELLED")
    agg = due.annotate(cd=TruncDate("work_order__completed_at")).aggregate(
        total=Count("pk"),
        on_time=Count("pk", filter=Q(work_order__completed_at__isnull=False, cd__lte=F("due_date"))),
        late=Count("pk", filter=Q(work_order__completed_at__isnull=False, cd__gt=F("due_date"))),
        open_missed=Count("pk", filter=Q(work_order__completed_at__isnull=True, due_date__lt=today)))
    judged = agg["on_time"] + agg["late"] + agg["open_missed"]
    sch = _scope(MaintenanceSchedule.objects.for_organization(org), allowed, f, "plan__site_id").filter(
        is_active=True, plan__is_active=True)
    upcoming = sch.filter(next_due_date__gte=today, next_due_date__lte=today + datetime.timedelta(days=14)).count()
    generated = cycles.filter(created_at__gte=f.since, created_at__lt=f.until).count()
    pm_wos = _scope(WorkOrder.objects.for_organization(org), allowed, f).filter(
        source_type="PREVENTIVE_MAINTENANCE", created_at__gte=f.since, created_at__lt=f.until).count()
    return {"kpis": {"due_in_window": agg["total"], "on_time": agg["on_time"], "late": agg["late"],
                     "missed_open": agg["open_missed"], "compliance_percent": _pct(agg["on_time"], judged),
                     "upcoming_14d": upcoming, "generated_in_window": generated, "pm_work_orders": pm_wos}}


def service(m, org, f: Filters) -> dict:
    from apps.incidents.models import ServiceRequest
    from apps.sla.models import SLABreach, SLATracking

    allowed = sites_allowed(m, "report.view", "incident.view")
    reqs = _scope(ServiceRequest.objects.for_organization(org), allowed, f)
    created = reqs.filter(created_at__gte=f.since, created_at__lt=f.until)
    by_status = {r["status"]: r["n"] for r in created.values("status").annotate(n=Count("pk"))}
    by_severity = {r["severity"]: r["n"] for r in created.values("severity").annotate(n=Count("pk"))}
    out = {"requests": {"created": created.count(), "by_status": by_status, "by_severity": by_severity,
                        "awaiting_triage": reqs.filter(status="NEW").count(),
                        "awaiting_confirmation": reqs.filter(status="RESOLVED").count(),
                        "from_clients": created.filter(reported_by__portal_account__isnull=False).count(),
                        "incidents": created.filter(kind="INCIDENT").count(),
                        "service_requests": created.filter(kind="SERVICE_REQUEST").count()},
           "sla": None}
    if rbac.has_permission_anywhere(m, "sla.view"):
        sallowed = sites_allowed(m, "report.view", "sla.view")
        trk = _scope(SLATracking.objects.for_organization(org), sallowed, f).filter(
            started_at__gte=f.since, started_at__lt=f.until)
        br = _scope(SLABreach.objects.for_organization(org), sallowed, f).filter(
            breached_at__gte=f.since, breached_at__lt=f.until)

        def bucket(field):
            c = {r[field]: r["n"] for r in trk.values(field).annotate(n=Count("pk"))}
            met, late, breached = c.get("MET", 0), c.get("MET_LATE", 0), c.get("BREACHED", 0)
            return {"met": met, "met_late": late, "breached": breached, "pending": c.get("PENDING", 0),
                    "compliance_percent": _pct(met, met + late + breached)}

        out["sla"] = {"trackings": trk.count(), "response": bucket("response_state"),
                      "resolution": bucket("resolution_state"), "breaches": br.count(),
                      "breaches_open": br.exclude(status="CLOSED").count(),
                      "breaches_by_kind": {r["target_kind"]: r["n"] for r in br.values("target_kind").annotate(
                          n=Count("pk"))},
                      "breaches_escalated": br.filter(escalation_level__gt=0).count()}
    return out


def inventory(m, org, f: Filters) -> dict:
    from apps.inventory.models import StockBalance, StockMovement

    allowed = sites_allowed(m, "report.view", "inventory.view")
    moves = _scope(StockMovement.objects.for_organization(org), allowed, f, "warehouse__site_id").filter(
        created_at__gte=f.since, created_at__lt=f.until)
    net = moves.filter(movement_type__in=("ISSUE", "RETURN")).values("part_id", "part__part_number", "part__name",
                                                                     "part__unit").annotate(
        issued=Sum("quantity", filter=Q(movement_type="ISSUE")),
        returned=Sum("quantity", filter=Q(movement_type="RETURN")))
    rows = []
    for r in net:
        issued, returned = r["issued"] or Decimal(0), r["returned"] or Decimal(0)
        rows.append({"part": f"{r['part__part_number']} · {r['part__name']}", "unit": r["part__unit"],
                     "issued": float(issued), "returned": float(returned), "net": float(issued - returned)})
    rows.sort(key=lambda r: -r["net"])
    balances = _scope(StockBalance.objects.for_organization(org), allowed, f, "warehouse__site_id")
    low = balances.filter(min_level__isnull=False, on_hand__lte=F("min_level")).count()
    types = {r["movement_type"]: r["n"] for r in moves.values("movement_type").annotate(n=Count("pk"))}
    return {"kpis": {"net_consumption_lines": len(rows), "low_stock_balances": low, "movements": sum(types.values())},
            "top_parts": rows[:10], "movements_by_type": types}


def my_work(m, org, f: Filters) -> dict:
    from apps.workorders.models import WorkOrder, WorkOrderLabor

    mine = WorkOrder.objects.for_organization(org).filter(assigned_to=m)
    now = timezone.now()
    k = mine.aggregate(
        open=Count("pk", filter=~Q(status__in=TERMINAL) & ~Q(status__in=("COMPLETED", "SUPERVISOR_REVIEW"))),
        overdue=Count("pk", filter=Q(status__in=PRE_COMPLETION, planned_end__lt=now)),
        completed=Count("pk", filter=Q(completed_at__gte=f.since, completed_at__lt=f.until)))
    hours = WorkOrderLabor.objects.for_organization(org).filter(
        technician=m, work_date__gte=f.from_date, work_date__lte=f.to_date).aggregate(h=Sum("hours"))["h"] or 0
    upcoming = list(mine.filter(status__in=PRE_COMPLETION).order_by("planned_start")
                    .values("pk", "number", "title", "status", "planned_start", "asset__asset_tag")[:10])
    return {"kpis": {**k, "hours": float(hours),
                     "utilization": _pct(Decimal(hours), Decimal(f.days * CAPACITY_HOURS_PER_DAY))},
            "upcoming": upcoming}


SECTIONS = {
    "operations": ("Operations", operations, ("report.view", "work_order.view")),
    "assets": ("Assets", assets, ("report.view", "asset.view")),
    "maintenance": ("Maintenance", maintenance, ("report.view", "maintenance.view")),
    "service": ("Service", service, ("report.view", "incident.view")),
    "inventory": ("Inventory", inventory, ("report.view", "inventory.view")),
}


def visible_sections(membership) -> list[str]:
    return [k for k, (_l, _fn, codes) in SECTIONS.items() if can_see(membership, *codes)]
