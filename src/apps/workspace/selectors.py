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
