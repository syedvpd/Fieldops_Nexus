"""M07 read side: the caller's own jobs, built on the M06 visibility rules (never a second visibility model)."""
from apps.workorders import selectors as wo_selectors
from apps.workorders.workflow import ASSIGNED, COMPLETED, DISPATCHED, IN_PROGRESS, ON_HOLD, SUPERVISOR_REVIEW

VIEWS = {
    "active": (ASSIGNED, DISPATCHED, IN_PROGRESS, ON_HOLD),
    "review": (COMPLETED, SUPERVISOR_REVIEW),
}


def my_jobs(membership, org, view="active"):
    qs = wo_selectors.work_orders_for(membership, org).filter(assigned_to=membership)
    if view in VIEWS:
        qs = qs.filter(status__in=VIEWS[view])
    return qs.order_by("planned_start", "-created_at", "id")


def counts(membership, org) -> dict:
    qs = wo_selectors.work_orders_for(membership, org).filter(assigned_to=membership)
    return {k: qs.filter(status__in=v).count() for k, v in VIEWS.items()}


def route_context(wo) -> dict:
    """M07 site / route card for one job (HPE 7.2 "route/site details"): real M01 data only - the site address,
    the asset's place in the location tree (building > zone > service area), the site contacts in escalation order,
    the default operating calendar and a map link. The caller has already passed the work-order visibility check,
    so the card never widens access (everything hangs off the order's own site / asset)."""
    from urllib.parse import quote_plus

    from apps.sites.models import OperatingCalendar, SiteContact, Zone

    site, asset = wo.site, wo.asset
    chain = []
    node = asset.zone
    while node is not None:
        chain.append(node)
        node = node.parent
    chain.reverse()
    address_parts = [p for p in (site.address, site.city, site.state_region, site.postal_code, site.country) if p]
    address = ", ".join(" ".join(p.split()) for p in address_parts)
    contacts = SiteContact.objects.for_organization(wo.organization).filter(site=site).order_by("escalation_order")
    cal = OperatingCalendar.objects.for_organization(wo.organization).filter(site=site, is_default=True).first()
    days = dict(zip(range(1, 8), ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"), strict=True))
    hours = None
    if cal is not None:
        when = "24 hours" if cal.is_24x7 else (
            f"{cal.start_time:%H:%M}-{cal.end_time:%H:%M}" if cal.start_time and cal.end_time else "")
        hours = {"name": cal.name, "days": ", ".join(days[d] for d in sorted(cal.working_days or []) if d in days),
                 "hours": when}
    return {
        "site": site, "address": address, "timezone": site.timezone,
        "location_path": chain,
        "service_areas": [z for z in chain if z.zone_type == Zone.ZoneType.SERVICE_AREA],
        "contacts": list(contacts), "calendar": hours,
        "map_url": f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}" if address else "",
    }
