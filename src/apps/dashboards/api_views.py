"""M14 REST API: ``GET /api/v1/dashboards/<section>/?site=&from=&to=``. Same metrics module as the pages; each
section needs ``report.view`` plus the view permission of its data (``my-work`` needs ``work_order.view_assigned``).
Aggregates are restricted to the caller's site scope, so totals can never reveal other sites or tenants."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response

from apps.core.apiutils import ID_PARAM, query_param
from apps.core.exceptions import NotFound, PermissionDenied
from apps.tenancy.api import TenantAPIMixin

from . import metrics

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
