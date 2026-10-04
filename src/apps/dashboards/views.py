"""M14 HTML dashboards: one page per persona section (Operations, Assets, Maintenance, Service, Inventory) and the
technician's own summary. Filters (site, date range) are validated server-side; nothing is computed client-side."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.core.exceptions import DomainError
from apps.rbac import services as rbac
from apps.sites import selectors as site_selectors
from apps.ui.mixins import TenantPermissionMixin

from . import metrics

LABELS = {"DRAFT": "Draft", "PLANNED": "Planned", "ASSIGNED": "Assigned", "DISPATCHED": "Dispatched",
          "IN_PROGRESS": "In progress", "ON_HOLD": "On hold", "ACTIVE": "Active",
          "UNDER_MAINTENANCE": "Under maintenance", "OUT_OF_SERVICE": "Out of service", "RETIRED": "Retired",
          "DISPOSED": "Disposed"}


def bars(mapping, order=None, label_map=None):
    """{key: n} -> [{label, value, pct}] for CSS bars (width relative to the largest value)."""
    keys = list(order) if order else sorted(mapping, key=lambda k: -mapping[k])
    top = max([mapping.get(k, 0) for k in keys] or [0]) or 1
    return [{"label": (label_map or LABELS).get(k, str(k).replace("_", " ").title()), "value": mapping.get(k, 0),
             "pct": round(100 * mapping.get(k, 0) / top)} for k in keys if mapping.get(k, 0) or order]


# KPI key -> (list page, permission that page needs). A KPI only links when the caller can open the target.
DRILL = {
    "open_work_orders": ("/app/work-orders/?open=1", "work_order.view"),
    "overdue_work": ("/app/work-orders/?overdue=1", "work_order.view"),
    "pm_wo": ("/app/work-orders/?work_type=PREVENTIVE", "work_order.view"),
    "requests": ("/app/incidents/", "incident.view"),
    "awaiting_triage": ("/app/incidents/?status=NEW", "incident.view"),
    "awaiting_confirmation": ("/app/incidents/?status=RESOLVED", "incident.view"),
    "sla_breaches": ("/app/sla/breaches/", "sla.view"),
    "sla_open": ("/app/sla/breaches/", "sla.view"),
    "due": ("/app/maintenance/due/", "maintenance.view"),
    "upcoming": ("/app/maintenance/due/", "maintenance.view"),
    "missed": ("/app/maintenance/due/", "maintenance.view"),
    "pm_compliance": ("/app/maintenance/history/", "maintenance.view"),
    "assets": ("/app/assets/", "asset.view"),
    "expiring": ("/app/contracts/expiry/", "contract.view"),
    "low_stock": ("/app/inventory/stock/", "inventory.view"),
    "movements": ("/app/inventory/movements/", "inventory.view"),
    "open": ("/app/workspace/", "work_order.view_assigned"),
    "overdue": ("/app/workspace/", "work_order.view_assigned"),
}


def drill_links(membership) -> dict:
    return {key: url for key, (url, code) in DRILL.items() if rbac.has_permission_anywhere(membership, code)}


class DashBase(TenantPermissionMixin, View):
    required_permission = "report.view"

    def filters(self, request, allow_site=True):
        params = request.GET if allow_site else {k: v for k, v in request.GET.items() if k != "site"}
        try:
            return metrics.parse_filters(params, request.membership, request.organization), None
        except DomainError as exc:
            messages.error(request, exc.message)
            return metrics.parse_filters({}, request.membership, request.organization), exc.message


class IndexView(DashBase):
    def get(self, request):
        m, org = request.membership, request.organization
        sections = metrics.visible_sections(m)
        if not sections:
            return render(request, "dashboards/none.html", status=200)
        current = request.GET.get("section")
        if current not in sections:
            current = sections[0]
        f, err = self.filters(request)
        label, fn, _codes = metrics.SECTIONS[current]
        data = fn(m, org, f)
        ctx = {"sections": [(k, metrics.SECTIONS[k][0]) for k in sections], "current": current, "label": label,
               "f": f, "data": data, "error": err, "definitions": metrics.KPI_DEFINITIONS,
               "sites": site_selectors.sites_for(m, org, "report.view").order_by("code"),
               "has_my_work": rbac.has_permission_anywhere(m, "work_order.view_assigned"),
               "drill": drill_links(m)}
        if current == "operations":
            ctx["bars_status"] = bars(data["open_by_status"], ["DRAFT", "PLANNED", "ASSIGNED", "DISPATCHED",
                                                               "IN_PROGRESS", "ON_HOLD", "COMPLETED",
                                                               "SUPERVISOR_REVIEW"])
            ctx["bars_priority"] = bars(data["open_by_priority"], ["URGENT", "HIGH", "MEDIUM", "LOW"])
            ctx["bars_type"] = bars(data["created_by_type"])
        elif current == "assets":
            ctx["bars_status"] = bars(data["status"], ["ACTIVE", "UNDER_MAINTENANCE", "OUT_OF_SERVICE", "RETIRED",
                                                       "DISPOSED"])
        elif current == "service":
            ctx["bars_req_status"] = bars(data["requests"]["by_status"])
            ctx["bars_req_severity"] = bars(data["requests"]["by_severity"], ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
        elif current == "inventory":
            ctx["bars_moves"] = bars(data["movements_by_type"])
        return render(request, f"dashboards/{current}.html", ctx)


class MineView(TenantPermissionMixin, View):
    required_permission = "work_order.view_assigned"

    def get(self, request):
        m, org = request.membership, request.organization
        try:
            f = metrics.parse_filters({k: v for k, v in request.GET.items() if k != "site"}, m, org)
        except DomainError as exc:
            messages.error(request, exc.message)
            return redirect("dashboards:mine")
        return render(request, "dashboards/mine.html", {"f": f, "data": metrics.my_work(m, org, f),
                                                        "definitions": metrics.KPI_DEFINITIONS,
                                                        "drill": drill_links(m)})
