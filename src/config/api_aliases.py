"""HPE-named API paths. The HPE document lists mandatory API groups by short names (``/schedules/``, ``/checklists/``,
``/stock/``, ``/reserve/``, ``/issue/``, ``/return/``, ``/slas/``, ``/breaches/``, ``/escalations/``,
``/generate-work-orders/``, ``/client/requests/``). The canonical, documented routes keep their descriptive names
(``/maintenance-schedules/`` ...); these aliases are the SAME viewsets (same authentication, RBAC, tenant and site
scope) under the HPE names, hidden from the OpenAPI schema to avoid duplicate operations."""
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response

from apps.checklists.api_views import ChecklistTemplateViewSet
from apps.core.exceptions import PermissionDenied
from apps.inventory.api_views import StockBalanceViewSet, WorkOrderPartViewSet
from apps.maintenance import services as maintenance_services
from apps.maintenance.api_views import MaintenanceScheduleViewSet
from apps.portal.api_views import PortalRequestViewSet
from apps.rbac import services as rbac
from apps.sla import selectors as sla_selectors
from apps.sla.api_views import BreachSerializer, SLABreachViewSet, SLAProfileViewSet
from apps.tenancy.api import TenantAPIMixin


def alias(cls):
    return extend_schema(exclude=True)(type(f"{cls.__name__}Alias", (cls,), {"__doc__": cls.__doc__}))


ScheduleAlias = alias(MaintenanceScheduleViewSet)
ChecklistAlias = alias(ChecklistTemplateViewSet)
StockAlias = alias(StockBalanceViewSet)
SLAAlias = alias(SLAProfileViewSet)
BreachAlias = alias(SLABreachViewSet)
ClientRequestAlias = alias(PortalRequestViewSet)


def _line_action(name: str, permission: str):
    """``POST /api/v1/<name>/ {"part_line": <id>, ...}`` = ``POST /work-order-parts/<id>/<name>/``."""
    target = {"return": "return_stock"}.get(name, name)

    class LineAction(WorkOrderPartViewSet):
        permission_map = {"create": permission}

        def create(self, request):
            return getattr(WorkOrderPartViewSet, target)(self, request, pk=request.data.get("part_line"))

    LineAction.__name__ = f"{name.title()}Alias"
    return alias(LineAction)


ReserveAlias = _line_action("reserve", "inventory.reserve")
IssueAlias = _line_action("issue", "inventory.issue")
ReturnAlias = _line_action("return", "inventory.return")


@extend_schema(exclude=True)
class EscalationAlias(SLABreachViewSet):
    """``/escalations/``: breaches that have been escalated (level above zero)."""

    def list(self, request):
        from apps.core.apiutils import paginate

        qs = sla_selectors.filter_breaches(sla_selectors.breaches_for(request.membership, request.organization),
                                           request.query_params).filter(escalation_level__gt=0)
        return paginate(request, qs, BreachSerializer)


@extend_schema(exclude=True)
class GenerateWorkOrdersAlias(TenantAPIMixin, viewsets.ViewSet):
    """``POST /generate-work-orders/``: runs the PM generator for the organization now (idempotent; the same
    service the Celery scheduler uses). Needs ``maintenance.generate`` organization-wide."""

    permission_map = {"create": "maintenance.generate"}

    def create(self, request):
        if not rbac.has_permission(request.membership, "maintenance.generate"):
            raise PermissionDenied("Generating for every site needs the organization-wide permission.")
        return Response(maintenance_services.run_for_organization(request.organization))
