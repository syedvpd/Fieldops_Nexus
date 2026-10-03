from rest_framework import serializers, viewsets

from apps.tenancy.api import TenantAPIMixin

from . import selectors
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "occurred_at", "action", "actor_email", "target_type", "target_id", "target_repr",
                  "before", "after", "metadata", "request_id"]


class AuditLogViewSet(TenantAPIMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only. Writes happen only through service-layer audit.record()."""

    serializer_class = AuditLogSerializer
    permission_map = {"list": "audit.view", "retrieve": "audit.view"}
    filterset_fields: list = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.objects.none()
        return selectors.filter_logs(selectors.organization_logs(self.request.organization),
                                     self.request.query_params)
