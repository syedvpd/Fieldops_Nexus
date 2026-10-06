from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.tenancy import selectors


class LoginThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


@extend_schema(
    tags=["auth"], summary="Log in: obtain JWT access and refresh tokens",
    description="Authenticate a FieldOps Nexus user and obtain JWT access/refresh tokens.\n\n"
                "Send `email` and `password` (both required). Copy `access`, click **Authorize** and paste it into "
                "`jwtAuth`. The access token lasts 15 minutes; renew it with `/auth/token/refresh/`.\n\n"
                "Errors: `401` invalid credentials or inactive account (the same response, by design); "
                "`400` missing field; `429` too many attempts (10/min).",
    examples=[OpenApiExample("Login request", request_only=True,
                             value={"email": "tech@alpha.test", "password": "YOUR_PASSWORD"}),
              OpenApiExample("Login response", response_only=True,
                             value={"access": "<JWT access token>", "refresh": "<JWT refresh token>"})])
class TokenObtain(LoginThrottleMixin, TokenObtainPairView):
    authentication_classes: list = []
    permission_classes: list = []


@extend_schema(
    tags=["auth"], summary="Renew the access token",
    description="Exchange a valid refresh token for a new access token. Refresh tokens rotate: the response also "
                "carries a new `refresh`, and the old one is then unusable. `401` when the refresh token is "
                "invalid or expired (log in again).",
    examples=[OpenApiExample("Refresh request", request_only=True, value={"refresh": "YOUR_REFRESH_TOKEN"}),
              OpenApiExample("Refresh response", response_only=True,
                             value={"access": "NEW_ACCESS_TOKEN", "refresh": "NEW_REFRESH_TOKEN"})])
class TokenRefresh(LoginThrottleMixin, TokenRefreshView):
    authentication_classes: list = []
    permission_classes: list = []


class MeOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    is_platform_admin = serializers.BooleanField()
    organizations = MeOrganizationSerializer(many=True)


class MeView(APIView):
    """The authenticated identity and the organizations they can act in. Not tenant-scoped."""

    @extend_schema(
        tags=["auth"], summary="Current user and organization memberships", responses=MeSerializer,
        description="Returns the authenticated user and the organizations they can act in. Call it right after login "
                    "to verify identity and membership; the `slug` values are what `X-Organization` accepts. "
                    "Not tenant-scoped, so it needs no organization header.",
        examples=[OpenApiExample("Me", response_only=True, value={
            "id": "00000000-0000-0000-0000-000000000001", "email": "tech@alpha.test", "full_name": "Alex Technician",
            "is_platform_admin": False,
            "organizations": [{"id": "00000000-0000-0000-0000-000000000002", "slug": "alpha", "name": "Alpha Corp"}]})])
    def get(self, request):
        u = request.user
        return Response({
            "id": str(u.pk), "email": u.email, "full_name": u.full_name,
            "is_platform_admin": u.is_platform_admin,
            "organizations": [
                {"id": str(m.organization_id), "slug": m.organization.slug, "name": m.organization.name}
                for m in selectors.active_memberships(u)
            ],
        })
