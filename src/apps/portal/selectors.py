"""M13 read side. Everything starts from the caller's organization AND ownership (``reported_by`` = the caller's
membership). Work-order data is reduced to a client-safe view model: stage, planned window and the technician's
display name once dispatched; never notes, labor, parts, costs, SLA internals or audit."""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType

from apps.files.models import Attachment
from apps.incidents.models import ServiceRequest, ServiceRequestHistory
from apps.sites.selectors import scoped_get
from apps.workorders.models import WorkOrder

from .models import PortalAccount, PortalAssetGrant

CLIENT_STATUS = {
    "NEW": ("Received", "We have your request and will review it shortly.", 1),
    "TRIAGED": ("Under review", "Your request is being reviewed.", 1),
    "APPROVED": ("Approved", "Approved; a visit is being arranged.", 2),
    "WORK_ORDER_CREATED": ("Scheduled", "A job has been created for your request.", 2),
    "IN_SERVICE": ("Work in progress", "A technician is working on it.", 3),
    "RESOLVED": ("Resolved: please confirm", "The work is finished. Please confirm that the problem is fixed.", 4),
    "CONFIRMED": ("Confirmed", "Thank you for confirming. We are closing the request.", 5),
    "CLOSED": ("Closed", "This request is closed.", 5),
    "REJECTED": ("Declined", "We could not take this request forward.", 5),
}
STEPS = ("Received", "Approved", "In service", "Resolved", "Closed")
VISIT_STAGE = {"DRAFT": "Being prepared", "PLANNED": "Planned", "ASSIGNED": "Technician assigned",
               "DISPATCHED": "Technician on the way", "IN_PROGRESS": "Work in progress", "ON_HOLD": "Temporarily paused",
               "COMPLETED": "Work completed", "SUPERVISOR_REVIEW": "Quality check", "CLOSED": "Completed"}


def client_status(sr):
    label, text, step = CLIENT_STATUS.get(sr.status, (sr.status.title(), "", 1))
    return {"code": sr.status, "label": label, "text": text, "step": step}


def my_account(membership):
    return PortalAccount.objects.for_organization(membership.organization).filter(membership=membership).first()


def granted_assets(membership):
    acct = my_account(membership)
    if acct is None or not acct.is_active:
        from apps.assets.models import Asset

        return Asset.objects.none()
    from apps.assets.models import Asset

    ids = PortalAssetGrant.objects.for_organization(membership.organization).filter(account=acct).values("asset_id")
    return Asset.objects.for_organization(membership.organization).filter(pk__in=ids).exclude(
        status__in=("RETIRED", "DISPOSED")).select_related("site").order_by("asset_tag")


def my_requests(membership):
    return ServiceRequest.objects.for_organization(membership.organization).filter(
        reported_by=membership).select_related("asset", "site")


def get_my_request(membership, pk) -> ServiceRequest:
    return scoped_get(my_requests(membership), pk, "Request")


def filter_requests(qs, params):
    q = (params.get("q") or "").strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q) | Q(asset__asset_tag__icontains=q))
    stage = (params.get("stage") or "").strip()
    if stage == "open":
        qs = qs.exclude(status__in=("CLOSED", "REJECTED"))
    elif stage == "action":
        qs = qs.filter(status="RESOLVED")
    elif stage == "closed":
        qs = qs.filter(status__in=("CLOSED", "REJECTED"))
    return qs.order_by("-created_at")


@dataclass
class Visit:
    stage: str
    planned_start: object
    planned_end: object
    technician: str
    number: str


def visit_for(sr) -> Visit | None:
    """Latest live work order of the request, reduced to what a client may see."""
    wo = (WorkOrder.objects.for_organization(sr.organization).filter(source_request=sr)
          .exclude(status="CANCELLED").select_related("assigned_to__user").order_by("-created_at").first())
    if wo is None:
        return None
    show_tech = wo.assigned_to_id and wo.status in ("DISPATCHED", "IN_PROGRESS", "ON_HOLD", "COMPLETED",
                                                      "SUPERVISOR_REVIEW", "CLOSED")
    return Visit(stage=VISIT_STAGE.get(wo.status, wo.status.title()), planned_start=wo.planned_start,
                 planned_end=wo.planned_end, technician=wo.assigned_to.user.display_name if show_tech else "",
                 number=wo.number)


def timeline(sr):
    """Client-safe status history: status labels and times; reasons only where the client wrote or is owed them
    (their own reopen, the decision on a rejection)."""
    rows = []
    for h in ServiceRequestHistory.objects.for_organization(sr.organization).filter(request=sr).order_by(
            "created_at"):
        label = CLIENT_STATUS.get(h.to_status, (h.to_status.title(), "", 0))[0]
        reason = h.reason if h.action in ("reject", "reopen") else ""
        if rows and rows[-1]["label"] == label and not reason:
            continue
        rows.append({"label": label, "at": h.created_at, "reason": reason})
    return rows


def my_attachments(membership, sr):
    ct = ContentType.objects.get_for_model(ServiceRequest)
    return Attachment.objects.for_organization(sr.organization).filter(
        content_type=ct, object_id=str(sr.pk), uploaded_by=membership.user).order_by("created_at")


def counts(membership):
    from django.db.models import Count, Q

    return my_requests(membership).aggregate(
        total=Count("pk"),
        open=Count("pk", filter=~Q(status__in=("CLOSED", "REJECTED"))),
        action=Count("pk", filter=Q(status="RESOLVED")),
        closed=Count("pk", filter=Q(status__in=("CLOSED", "REJECTED"))))
