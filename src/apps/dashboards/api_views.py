"""M14 REST API: ``GET /api/v1/dashboards/<section>/?site=&from=&to=``. Same metrics module as the pages; each
section needs ``report.view`` plus the view permission of its data (``my-work`` needs ``work_order.view_assigned``).
Aggregates are restricted to the caller's site scope, so totals can never reveal other sites or tenants."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, viewsets
from rest_framework.response import Response

from apps.core.apiutils import ID_PARAM, query_param
from apps.core.exceptions import NotFound, PermissionDenied
from apps.tenancy.api import TenantAPIMixin

from . import metrics
from .models import ReportSnapshot

PARAMS = [query_param("site", "site id (must be within your scope)", OpenApiTypes.UUID),
          query_param("from", "first day, YYYY-MM-DD (default: 29 days before 'to')", OpenApiTypes.DATE),
          query_param("to", "last day, YYYY-MM-DD (default: today)", OpenApiTypes.DATE)]


@extend_schema(parameters=[ID_PARAM])
class DashboardViewSet(TenantAPIMixin, viewsets.ViewSet):
    # the section decides the real permission in retrieve(); any member passes the coarse gate
    permission_map = {"list": "report.view", "retrieve": "__member__"}

    @extend_schema(responses=OpenApiTypes.OBJECT, parameters=PARAMS, operation_id="dashboards_sections")
    def list(self, request):
        """Sections the caller may open."""
        return Response({"sections": metrics.visible_sections(request.membership),
                         "my_work": metrics_can_my_work(request.membership), "definitions": metrics.KPI_DEFINITIONS})

    @extend_schema(responses=OpenApiTypes.OBJECT, parameters=PARAMS, operation_id="dashboards_section")
    def retrieve(self, request, pk=None):
        if pk == "my-work":
            if not metrics_can_my_work(request.membership):
                raise PermissionDenied("You do not have permission to view this dashboard.")
            f = metrics.parse_filters({k: v for k, v in request.query_params.items() if k != "site"},
                                      request.membership, request.organization)
            return Response({"filters": _filters(f), "data": metrics.my_work(request.membership,
                                                                              request.organization, f)})
        if pk not in metrics.SECTIONS:
            raise NotFound("Dashboard not found.")
        _label, fn, codes = metrics.SECTIONS[pk]
        if not metrics.can_see(request.membership, *codes):
            raise PermissionDenied("You do not have permission to view this dashboard.")
        f = metrics.parse_filters(request.query_params, request.membership, request.organization)
        return Response({"filters": _filters(f), "data": fn(request.membership, request.organization, f)})


def metrics_can_my_work(membership) -> bool:
    from apps.rbac import services as rbac

    return rbac.has_permission_anywhere(membership, "work_order.view_assigned")


def _filters(f):
    return {"site": str(f.site.pk) if f.site else None, "from": f.from_date.isoformat(), "to": f.to_date.isoformat()}


class ReportSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSnapshot
        fields = ["id", "kind", "period_from", "period_to", "payload", "taken_at"]
        read_only_fields = fields


class ReportSnapshotViewSet(TenantAPIMixin, viewsets.ReadOnlyModelViewSet):
    """Frozen organization-wide figures. They cover every site, so only members holding ``report.view`` for the whole
    organization may read them, and only the sections whose data permission they also hold organization-wide (a
    site-scoped report user sees the live, scoped dashboards instead)."""

    serializer_class = ReportSnapshotSerializer
    permission_map = {"list": "__member__", "retrieve": "__member__"}
    filterset_fields: list = []

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        from apps.rbac import services as rbac

        if not rbac.has_permission(request.membership, "report.view"):
            raise PermissionDenied("Organization-wide report access is required for snapshots.")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ReportSnapshot.objects.none()
        from apps.rbac import services as rbac

        # a snapshot is only as visible as the live section: report.view AND the section's data permission, both
        # organization-wide (frozen figures cover every site)
        kinds = [k for k, (_label, _fn, codes) in metrics.SECTIONS.items()
                 if all(rbac.has_permission(self.request.membership, c) for c in codes)]
        qs = ReportSnapshot.objects.for_organization(self.request.organization).filter(kind__in=kinds)
        kind = self.request.query_params.get("kind")
        return qs.filter(kind=kind) if kind else qs
