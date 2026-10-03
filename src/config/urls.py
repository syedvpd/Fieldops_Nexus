from django.conf.urls.static import static  # noqa: F401
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import SimpleRouter

from apps.assets.api_views import (
    AssetCategoryViewSet,
    AssetViewSet,
    ComponentViewSet,
    MeterViewSet,
)
from apps.audit.api_views import AuditLogViewSet
from apps.checklists.api_views import (
    ChecklistTemplateViewSet,
    FindingViewSet,
    InspectionViewSet,
)
from apps.contracts.api_views import (
    AgreementViewSet,
    CoverageCheckViewSet,
    CoverageViewSet,
    ProviderViewSet,
)
from apps.core import health
from apps.dashboards.api_views import DashboardViewSet, ReportSnapshotViewSet
from apps.identification.api_views import IdentifierViewSet, ScanViewSet
from apps.incidents.api_views import ServiceRequestViewSet
from apps.inventory.api_views import (
    PartReservationViewSet,
    PartViewSet,
    StockBalanceViewSet,
    StockMovementViewSet,
    WarehouseViewSet,
    WorkOrderPartViewSet,
)
from apps.maintenance.api_views import (
    MaintenanceCycleViewSet,
    MaintenancePlanViewSet,
    MaintenanceScheduleViewSet,
)
from apps.notifications.api_views import NotificationViewSet
from apps.platform_admin.api_views import PlatformOrganizationViewSet
from apps.portal.api_views import PortalAccountViewSet, PortalAssetViewSet, PortalRequestViewSet
from apps.rbac.api_views import PermissionViewSet, RoleViewSet
from apps.sites.api_views import (
    CalendarViewSet,
    ContactViewSet,
    HolidayViewSet,
    SiteViewSet,
    ZoneViewSet,
)
from apps.sla.api_views import (
    SLABreachViewSet,
    SLAMetricsView,
    SLAProfileViewSet,
    SLATrackingViewSet,
)
from apps.tenancy.api_views import MemberViewSet, OrganizationViewSet
from apps.workorders.api_views import WorkOrderViewSet
from config import api_aliases

router = SimpleRouter()
router.register("members", MemberViewSet, basename="member")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("audit-logs", AuditLogViewSet, basename="auditlog")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("sites", SiteViewSet, basename="site")
router.register("zones", ZoneViewSet, basename="zone")
router.register("calendars", CalendarViewSet, basename="calendar")
router.register("calendar-holidays", HolidayViewSet, basename="calendar-holiday")
router.register("site-contacts", ContactViewSet, basename="site-contact")
router.register("assets", AssetViewSet, basename="asset")
router.register("asset-categories", AssetCategoryViewSet, basename="asset-category")
router.register("asset-components", ComponentViewSet, basename="asset-component")
router.register("meters", MeterViewSet, basename="meter")
router.register("service-requests", ServiceRequestViewSet, basename="service-request")
router.register("work-orders", WorkOrderViewSet, basename="work-order")
router.register("checklist-templates", ChecklistTemplateViewSet, basename="checklist-template")
router.register("inspections", InspectionViewSet, basename="inspection")
router.register("findings", FindingViewSet, basename="finding")
router.register("parts", PartViewSet, basename="part")
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("stock-balances", StockBalanceViewSet, basename="stock-balance")
router.register("stock-movements", StockMovementViewSet, basename="stock-movement")
router.register("part-reservations", PartReservationViewSet, basename="part-reservation")
router.register("work-order-parts", WorkOrderPartViewSet, basename="work-order-part")
router.register("maintenance-plans", MaintenancePlanViewSet, basename="maintenance-plan")
router.register("maintenance-schedules", MaintenanceScheduleViewSet, basename="maintenance-schedule")
router.register("maintenance-cycles", MaintenanceCycleViewSet, basename="maintenance-cycle")
router.register("contract-providers", ProviderViewSet, basename="contract-provider")
router.register("coverage-agreements", AgreementViewSet, basename="coverage-agreement")
router.register("coverage-checks", CoverageCheckViewSet, basename="coverage-check")
router.register("coverage", CoverageViewSet, basename="coverage")
router.register("asset-identifiers", IdentifierViewSet, basename="asset-identifier")
router.register("scan", ScanViewSet, basename="scan")
router.register("portal/requests", PortalRequestViewSet, basename="portal-request")
router.register("portal/assets", PortalAssetViewSet, basename="portal-asset")
router.register("portal-accounts", PortalAccountViewSet, basename="portal-account")
router.register("dashboards", DashboardViewSet, basename="dashboard")
router.register("report-snapshots", ReportSnapshotViewSet, basename="report-snapshot")
# HPE-named aliases of the canonical routes (same viewsets, hidden from the schema)
router.register("schedules", api_aliases.ScheduleAlias, basename="alias-schedule")
router.register("generate-work-orders", api_aliases.GenerateWorkOrdersAlias, basename="alias-generate")
router.register("checklists", api_aliases.ChecklistAlias, basename="alias-checklist")
router.register("stock", api_aliases.StockAlias, basename="alias-stock")
router.register("reserve", api_aliases.ReserveAlias, basename="alias-reserve")
router.register("issue", api_aliases.IssueAlias, basename="alias-issue")
router.register("return", api_aliases.ReturnAlias, basename="alias-return")
router.register("slas", api_aliases.SLAAlias, basename="alias-sla")
router.register("breaches", api_aliases.BreachAlias, basename="alias-breach")
router.register("escalations", api_aliases.EscalationAlias, basename="alias-escalation")
router.register("client/requests", api_aliases.ClientRequestAlias, basename="alias-client-request")
router.register("sla-profiles", SLAProfileViewSet, basename="sla-profile")
router.register("sla-trackings", SLATrackingViewSet, basename="sla-tracking")
router.register("sla-breaches", SLABreachViewSet, basename="sla-breach")
router.register("platform/organizations", PlatformOrganizationViewSet, basename="platform-organization")

api_v1 = [
    path("auth/", include("apps.accounts.api_urls")),
    path("organization/", OrganizationViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
         name="organization"),
    path("", include(router.urls)),
    path("sla-metrics/", SLAMetricsView.as_view(), name="sla-metrics"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

urlpatterns = [
    path("health/live/", health.live, name="health_live"),
    path("health/ready/", health.ready, name="health_ready"),
    path("api/v1/", include(api_v1)),
    path("accounts/", include("apps.accounts.urls")),
    path("platform/", include("apps.platform_admin.urls")),
    path("app/", include("apps.tenancy.urls")),
    path("app/", include("apps.rbac.urls")),
    path("app/", include("apps.audit.urls")),
    path("app/", include("apps.notifications.urls")),
    path("app/", include("apps.files.urls")),
    path("app/", include("apps.sites.urls")),
    path("app/", include("apps.assets.urls")),
    path("app/", include("apps.incidents.urls")),
    path("app/", include("apps.workorders.urls")),
    path("app/", include("apps.inventory.urls")),
    path("app/", include("apps.maintenance.urls")),
    path("app/", include("apps.sla.urls")),
    path("app/", include("apps.contracts.urls")),
    path("app/", include("apps.identification.urls")),
    path("app/", include("apps.portal.urls")),
    path("app/", include("apps.dashboards.urls")),
    path("app/", include("apps.checklists.urls")),
    path("app/", include("apps.workspace.urls")),
    path("", include("apps.ui.urls")),
]

handler403 = "apps.ui.views.forbidden"
handler404 = "apps.ui.views.not_found"
handler500 = "apps.ui.views.server_error"
