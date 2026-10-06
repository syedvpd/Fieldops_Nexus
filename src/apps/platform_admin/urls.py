from django.urls import path

from . import views

app_name = "platform_admin"
def _s(name):
    return views.SectionView.as_view(section=name)


def _d(kind, section):
    return views.DetailView.as_view(kind=kind, section=section)


urlpatterns = [
    path("", _s("overview"), name="overview"),
    path("sites/", _s("sites"), name="sites"),
    path("sites/<uuid:pk>/", _d("site_detail", "sites"), name="site_detail"),
    path("users/", _s("users"), name="users"),
    path("roles/", _s("roles"), name="roles"),
    path("assets/", _s("assets"), name="assets"),
    path("assets/<uuid:pk>/", _d("asset_detail", "assets"), name="asset_detail"),
    path("service-operations/", _s("service_ops"), name="service_ops"),
    path("service-operations/<uuid:pk>/", _d("service_detail", "service_ops"), name="service_detail"),
    path("work-orders/", _s("work_orders"), name="work_orders"),
    path("work-orders/<uuid:pk>/", _d("work_order_detail", "work_orders"), name="work_order_detail"),
    path("maintenance/", _s("maintenance"), name="maintenance"),
    path("inventory/", _s("inventory"), name="inventory"),
    path("sla/", _s("sla"), name="sla"),
    path("dashboards/", _s("dashboards"), name="dashboards"),
    path("settings/", _s("settings"), name="settings"),
    path("security/", _s("security"), name="security"),
    path("profile/", _s("profile"), name="profile"),
    path("organizations/", views.OrganizationListView.as_view(), name="organizations"),
    path("organizations/new/", views.OrganizationCreateView.as_view(), name="organization_create"),
    path("organizations/<uuid:pk>/", views.OrganizationDetailView.as_view(), name="organization_detail"),
    path("audit/", views.PlatformAuditView.as_view(), name="audit"),
]
