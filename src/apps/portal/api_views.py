"""M13 REST API. Client endpoints (``/api/v1/portal/*``) expose a deliberately small, client-safe projection of the
caller's OWN requests; staff endpoint ``/api/v1/portal-accounts/`` manages portal clients. Privileged ERP endpoints
(work orders, stock, SLA, audit ...) stay closed to clients because their roles hold no such permissions."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.apiutils import ID_PARAM, paginate, query_param
from apps.core.exceptions import NotFound, ValidationFailed
from apps.incidents.models import ServiceRequest
from apps.tenancy.api import TenantAPIMixin

from . import selectors, services
from .models import PortalAccount


class ClientRequestSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    client_status = serializers.SerializerMethodField()
    visit = serializers.SerializerMethodField()

    class Meta:
        model = ServiceRequest
        fields = ["id", "number", "kind", "title", "description", "severity", "asset", "asset_tag", "asset_name",
                  "status", "client_status", "visit", "created_at", "resolved_at", "confirmed_at", "closed_at"]
        read_only_fields = fields

    def get_client_status(self, obj) -> dict:
        s = selectors.client_status(obj)
        return {"label": s["label"], "text": s["text"]}

    def get_visit(self, obj) -> dict | None:
        v = selectors.visit_for(obj)
        if v is None:
            return None
        return {"stage": v.stage, "planned_start": v.planned_start, "planned_end": v.planned_end,
                "technician": v.technician, "number": v.number}


class ClientAssetSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    asset_tag = serializers.CharField()
    name = serializers.CharField()
    site = serializers.CharField(source="site.code")


class SubmitSerializer(serializers.Serializer):
    asset = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=ServiceRequest.Kind.choices, required=False)
    urgency = serializers.ChoiceField(choices=[(u, u) for u in services.URGENCIES], required=False)
    files = serializers.ListField(child=serializers.FileField(), required=False)


class PortalReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class AttachSerializer(serializers.Serializer):
    file = serializers.FileField()


@extend_schema(parameters=[ID_PARAM])
class PortalRequestViewSet(TenantAPIMixin, viewsets.ViewSet):
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_map = {"list": "portal.request.view", "retrieve": "portal.request.view",
                      "create": "portal.request.create", "confirm": "portal.request.confirm",
                      "reopen": "portal.request.confirm", "attachments": "portal.request.create"}

    def _mine(self, request, pk):
        return selectors.get_my_request(request.membership, pk)

    @extend_schema(parameters=[query_param("q", "number / title / equipment"),
                               query_param("stage", "open | action | closed")],
                   responses=ClientRequestSerializer(many=True))
    def list(self, request):
        qs = selectors.filter_requests(selectors.my_requests(request.membership), request.query_params)
        return paginate(request, qs, ClientRequestSerializer)

    @extend_schema(responses=ClientRequestSerializer)
    def retrieve(self, request, pk=None):
        return Response(ClientRequestSerializer(self._mine(request, pk)).data)

    @extend_schema(request=SubmitSerializer, responses={201: ClientRequestSerializer})
    def create(self, request):
        ser = SubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        asset = selectors.granted_assets(request.membership).filter(pk=d.pop("asset")).first()
        if asset is None:
            raise NotFound("Asset not found.")
        d.pop("files", None)
        sr = services.submit_request(request.membership, asset=asset, uploads=request.FILES.getlist("files"),
                                     request=request, **d)
        return Response(ClientRequestSerializer(sr).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=ClientRequestSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        sr = services.confirm(request.membership, self._mine(request, pk), request=request)
        return Response(ClientRequestSerializer(sr).data)

    @extend_schema(request=PortalReasonSerializer, responses=ClientRequestSerializer)
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        ser = PortalReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sr = services.reopen(request.membership, self._mine(request, pk), reason=ser.validated_data["reason"],
                             request=request)
        return Response(ClientRequestSerializer(sr).data)

    @extend_schema(request={"multipart/form-data": AttachSerializer}, responses={201: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"])
    def attachments(self, request, pk=None):
        sr = self._mine(request, pk)  # ownership first: a foreign id is a 404 whatever the payload
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationFailed("A file is required.", code="file_required")
        att = services.add_attachment(request.membership, sr, upload, request=request)
        return Response({"id": str(att.pk), "name": att.original_name, "size": att.size},
                        status=status.HTTP_201_CREATED)


class PortalAssetViewSet(TenantAPIMixin, viewsets.ViewSet):
    permission_map = {"list": "portal.request.view"}

    @extend_schema(responses=ClientAssetSerializer(many=True))
    def list(self, request):
        return paginate(request, selectors.granted_assets(request.membership), ClientAssetSerializer)


class AccountSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="membership.user.email", read_only=True)
    assets = serializers.SerializerMethodField()

    class Meta:
        model = PortalAccount
        fields = ["id", "membership", "email", "company", "is_active", "assets", "created_at"]
        read_only_fields = fields

    def get_assets(self, obj) -> list[str]:
        return [g.asset.asset_tag for g in obj.grants.select_related("asset")]


class AccountCreateSerializer(serializers.Serializer):
    membership = serializers.UUIDField()
    company = serializers.CharField(max_length=150, required=False, allow_blank=True)


class PortalAssetRefSerializer(serializers.Serializer):
    asset = serializers.UUIDField()


@extend_schema(parameters=[ID_PARAM])
class PortalAccountViewSet(TenantAPIMixin, viewsets.ViewSet):
    permission_map = {"list": "portal.manage", "retrieve": "portal.manage", "create": "portal.manage",
                      "enable": "portal.manage", "disable": "portal.manage", "grant": "portal.manage",
                      "revoke": "portal.manage"}

    def _acct(self, request, pk):
        from apps.sites.selectors import scoped_get

        return scoped_get(PortalAccount.objects.for_organization(request.organization).select_related(
            "membership__user"), pk, "Portal client")

    def _asset(self, request, pk):
        from apps.assets.models import Asset

        try:
            return Asset.objects.for_organization(request.organization).get(pk=pk)
        except Asset.DoesNotExist as exc:
            raise NotFound("Asset not found.") from exc

    @extend_schema(responses=AccountSerializer(many=True))
    def list(self, request):
        qs = PortalAccount.objects.for_organization(request.organization).select_related("membership__user")
        return paginate(request, qs, AccountSerializer)

    @extend_schema(responses=AccountSerializer)
    def retrieve(self, request, pk=None):
        return Response(AccountSerializer(self._acct(request, pk)).data)

    @extend_schema(request=AccountCreateSerializer, responses={201: AccountSerializer})
    def create(self, request):
        from apps.tenancy.models import Membership

        ser = AccountCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        m = Membership.objects.for_organization(request.organization).filter(pk=ser.validated_data["membership"]).first()
        if m is None:
            raise NotFound("Member not found.")
        acct = services.enable_account(request.organization, m, company=ser.validated_data.get("company", ""),
                                       actor=request.user, request=request)
        return Response(AccountSerializer(acct).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=AccountSerializer)
    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        return Response(AccountSerializer(services.set_account_active(
            self._acct(request, pk), True, actor=request.user, request=request)).data)

    @extend_schema(request=None, responses=AccountSerializer)
    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        return Response(AccountSerializer(services.set_account_active(
            self._acct(request, pk), False, actor=request.user, request=request)).data)

    @extend_schema(request=PortalAssetRefSerializer, responses=AccountSerializer)
    @action(detail=True, methods=["post"])
    def grant(self, request, pk=None):
        ser = PortalAssetRefSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        acct = self._acct(request, pk)
        services.grant_asset(acct, self._asset(request, ser.validated_data["asset"]), actor=request.user,
                             request=request)
        return Response(AccountSerializer(acct).data)

    @extend_schema(request=PortalAssetRefSerializer, responses=AccountSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        ser = PortalAssetRefSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        acct = self._acct(request, pk)
        services.revoke_asset(acct, self._asset(request, ser.validated_data["asset"]), actor=request.user,
                              request=request)
        return Response(AccountSerializer(acct).data)
