from django.urls import path

from . import views

app_name = "portal"
urlpatterns = [
    path("portal/", views.DashboardView.as_view(), name="dashboard"),
    path("portal/requests/", views.RequestListView.as_view(), name="requests"),
    path("portal/requests/new/", views.NewRequestView.as_view(), name="new"),
    path("portal/requests/<uuid:pk>/", views.RequestDetailView.as_view(), name="request"),
    path("portal/requests/<uuid:pk>/<str:action>/", views.RequestActionView.as_view(), name="request_action"),
    path("portal/accounts/", views.AccountsView.as_view(), name="accounts"),
    path("portal/accounts/<uuid:pk>/", views.AccountDetailView.as_view(), name="account"),
]
