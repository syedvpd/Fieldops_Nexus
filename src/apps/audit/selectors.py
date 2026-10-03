from django.db.models import Q
from django.utils.dateparse import parse_date

from .models import AuditLog


def filter_logs(qs, params):
    action = (params.get("action") or "").strip()
    q = (params.get("q") or "").strip()
    frm = parse_date(params.get("from") or "")
    to = parse_date(params.get("to") or "")
    if action:
        qs = qs.filter(action__startswith=action)
    if q:
        qs = qs.filter(Q(actor_email__icontains=q) | Q(target_repr__icontains=q))
    if frm:
        qs = qs.filter(occurred_at__date__gte=frm)
    if to:
        qs = qs.filter(occurred_at__date__lte=to)
    return qs


def organization_logs(org):
    return AuditLog.objects.for_organization(org).select_related("actor")
