"""M12 REST API (``/api/v1/asset-identifiers`` and ``/api/v1/scan``).

Label management: object lookup in organization + ``qr.view`` site scope (404), permission for the asset's site
(403), service. Scan: the token only locates; the caller must then be able to see the asset."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.assets import selectors as asset_selectors
from apps.core import openapi_schemas as oas
from apps.core.apiutils import ID_PARAM, paginate, query_param, require_permission
from apps.core.exceptions import NotFound, RateLimited
from apps.incidents.models import ServiceRequest
from apps.tenancy.api import TenantAPIMixin

from . import selectors, services
from .models import AssetIdentifier


class IdentifierSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    scan_url = serializers.SerializerMethodField()

    class Meta:
        model = AssetIdentifier
        fields = ["id", "asset", "asset_tag", "kind", "token", "scan_url", "is_active", "revoked_at",
                  "revoked_reason", "created_at"]
        read_only_fields = fields

    def get_scan_url(self, obj) -> str:
        req = self.context.get("request")
        return services.scan_url(obj.token, req.build_absolute_uri("/")[:-1] if req else "")


class GenerateSerializer(serializers.Serializer):
    asset = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=AssetIdentifier.Kind.choices)


class IdentifierReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class ScanResolveSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=300)


class ReportSerializer(ScanResolveSerializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=ServiceRequest.Kind.choices, required=False)
    severity = serializers.ChoiceField(choices=ServiceRequest.Severity.choices, required=False)


class ScanAssetSerializer(serializers.Serializer):
    outcome = serializers.CharField()
    asset = serializers.UUIDField(source="asset.pk", allow_null=True)
    asset_tag = serializers.CharField(source="asset.asset_tag", allow_null=True)
    name = serializers.CharField(source="asset.name", allow_null=True)
    status = serializers.CharField(source="asset.status", allow_null=True)
    site = serializers.CharField(source="asset.site.code", allow_null=True)
    asset_inactive = serializers.BooleanField()
    kind = serializers.CharField(source="identifier.kind", allow_null=True)


def _validated(cls, request):
    ser = cls(data=request.data)
    ser.is_valid(raise_exception=True)
    return dict(ser.validated_data)


@extend_schema(parameters=[ID_PARAM])
class IdentifierViewSet(TenantAPIMixin, viewsets.ViewSet):
    permission_map = {"list": "qr.view", "retrieve": "qr.view", "create": "qr.generate", "revoke": "qr.generate",
                      "replace": "qr.generate"}

    def _ident(self, request, pk, code=None) -> AssetIdentifier:
        ident = selectors.get_identifier(request.membership, request.organization, pk)
        if code:
            require_permission(request.membership, code, ident.asset.site_id)
        return ident

    @extend_schema(parameters=[query_param("asset", "asset id", OpenApiTypes.UUID),
                               query_param("active", "1 / 0")], responses=IdentifierSerializer(many=True))
    def list(self, request):
        qs = selectors.identifiers_for(request.membership, request.organization)
        asset = (request.query_params.get("asset") or "").strip()
        if asset:
            parsed = selectors.uuid_or_none(asset)
            qs = qs.filter(asset_id=parsed) if parsed else qs.none()
        active = (request.query_params.get("active") or "").strip()
        if active in ("1", "0"):
            qs = qs.filter(is_active=active == "1")
        return paginate(request, qs, IdentifierSerializer)  # scan_url is path-relative in lists

    @extend_schema(responses=IdentifierSerializer)
    def retrieve(self, request, pk=None):
        return Response(IdentifierSerializer(self._ident(request, pk), context={"request": request}).data)

    @extend_schema(request=GenerateSerializer, responses={201: IdentifierSerializer})
    def create(self, request):
        d = _validated(GenerateSerializer, request)
        asset = asset_selectors.get_asset(request.membership, request.organization, d["asset"])
        require_permission(request.membership, "qr.generate", asset.site_id)
        ident = services.generate(asset, d["kind"], actor=request.user, request=request)
        return Response(IdentifierSerializer(ident, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=IdentifierReasonSerializer, responses=IdentifierSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        ident = self._ident(request, pk, "qr.generate")
        d = _validated(IdentifierReasonSerializer, request)
        return Response(IdentifierSerializer(services.revoke(ident, reason=d["reason"], actor=request.user,
                                                             request=request),
                                             context={"request": request}).data)

    @extend_schema(request=IdentifierReasonSerializer, responses={201: IdentifierSerializer})
    @action(detail=True, methods=["post"])
    def replace(self, request, pk=None):
        ident = self._ident(request, pk, "qr.generate")
        d = _validated(IdentifierReasonSerializer, request)
        new = services.regenerate(ident, reason=d["reason"], actor=request.user, request=request)
        return Response(IdentifierSerializer(new, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)


class ScanViewSet(TenantAPIMixin, viewsets.ViewSet):
    permission_map = {"resolve": "asset.view", "report": "incident.create"}

    @extend_schema(request=ScanResolveSerializer, responses=ScanAssetSerializer)
    @action(detail=False, methods=["post"])
    def resolve(self, request):
        """Token (or scanned URL) -> asset summary. Unknown, foreign, revoked or invisible tokens never reveal the
        asset; an unknown / foreign token is a plain 404."""
        d = _validated(ScanResolveSerializer, request)
        res = services.resolve(request.user, d["token"], request.membership, request=request)
        if res.outcome == "THROTTLED":
            raise RateLimited("Too many failed scans. Try again in a few minutes.")
        if res.outcome in ("UNKNOWN", "FORBIDDEN"):
            raise NotFound("Label not found.")
        body = ScanAssetSerializer(res).data
        return Response(body, status=status.HTTP_200_OK if res.outcome == "RESOLVED" else status.HTTP_410_GONE)

    @extend_schema(request=ReportSerializer, responses={201: oas.ScanReportResult})
    @action(detail=False, methods=["post"])
    def report(self, request):
        """Scan-to-service-event: opens an M05 incident / service request for the scanned asset."""
        d = _validated(ReportSerializer, request)
        token = d.pop("token")
        res = services.resolve(request.user, token, request.membership, request=request)
        if res.outcome == "THROTTLED":
            raise RateLimited("Too many failed scans. Try again in a few minutes.")
        if res.outcome in ("UNKNOWN", "FORBIDDEN"):
            raise NotFound("Label not found.")
        sr = services.report_from_scan(res, actor=request.user, request=request, **d)
        return Response({"id": str(sr.pk), "number": sr.number, "status": sr.status, "asset": str(sr.asset_id)},
                        status=status.HTTP_201_CREATED)
