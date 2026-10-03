from django.urls import path

from . import views

app_name = "audit"
urlpatterns = [
    path("audit/", views.AuditListView.as_view(), name="list"),
    path("audit/<uuid:pk>/", views.AuditDetailView.as_view(), name="detail"),
]
