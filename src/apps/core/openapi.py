"""OpenAPI contract helpers (drf-spectacular): pagination envelope on ViewSet lists, and a post-processing hook that
makes the generated document match the real API (tenant header, uniform error envelope, no phantom path params)."""
import inspect
import re

from drf_spectacular.openapi import AutoSchema

from apps.core.api import StandardPagination

ORG_HEADER_REF = "#/components/parameters/OrganizationHeader"
ERROR_REF = "#/components/schemas/ErrorResponse"

ERROR_SCHEMA = {
    "type": "object",
    "description": "Uniform error envelope returned for every non-2xx JSON response.",
    "properties": {"error": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "example": "validation_failed"},
            "message": {"type": "string", "example": "Validation failed."},
            "details": {"type": "object", "additionalProperties": {},
                        "description": "For validation errors: {\"fields\": {<field>: [messages]}}."},
            "request_id": {"type": "string", "nullable": True, "description": "Correlates with server logs."},
        },
        "required": ["code", "message", "details"],
    }},
    "required": ["error"],
}

ORG_HEADER_PARAM = {
    "in": "header", "name": "X-Organization", "required": False,
    "schema": {"type": "string"},
    "description": "Active organization slug (or id). Optional when the user has exactly one active membership; "
                   "required to disambiguate users with several. It only SELECTS among the caller's own "
                   "memberships (403 `not_a_member` otherwise); it never grants access.",
}

ERROR_TEXT = {
    "400": "Validation or business-rule error (`validation_failed` or a domain code).",
    "401": "Missing, expired or invalid JWT (`not_authenticated`).",
    "403": "Authenticated but not permitted (missing permission, site scope, or not a member of the organization).",
    "404": "Object not found, or not visible in the caller's active organization / site scope.",
    "409": "Conflict: the object is not in a state that allows this action (`invalid_transition`).",
}


class FieldOpsAutoSchema(AutoSchema):
    """ViewSets here page their lists through ``apps.core.apiutils.paginate`` rather than a GenericAPIView, so
    drf-spectacular would document a bare array. Wrap exactly the actions whose code paginates."""

    def _get_paginator(self):
        paginator = super()._get_paginator()
        if paginator is not None:
            return paginator
        view = self.view
        func = getattr(view, getattr(view, "action", None) or "", None)
        try:
            src = inspect.getsource(func) if func else ""
        except (OSError, TypeError):
            src = ""
        return StandardPagination() if ("paginate(" in src or "paginate_queryset(" in src) else None


    def _permission(self):
        view = self.view
        pmap = getattr(view, "permission_map", None)
        if pmap is None:
            return getattr(view, "required_permission", None)
        action = getattr(view, "action", None) or self.method.lower()
        return pmap.get(f"{action}:{self.method.lower()}") or pmap.get(action) or getattr(view, "required_permission", None)

    def get_summary(self):
        summary = super().get_summary()
        if summary:
            return summary
        action = getattr(self.view, "action", None) or self.method.lower()
        verbs = {"list": "List", "retrieve": "Get", "create": "Create", "partial_update": "Update",
                 "update": "Replace", "destroy": "Delete", "get": "Get", "post": "Run"}
        noun = (self.view.__class__.__name__.removesuffix("ViewSet").removesuffix("View"))
        noun = re.sub(r"(?<!^)(?=[A-Z])", " ", noun).lower()
        return f"{verbs[action]} {noun}" if action in verbs else f"{action.replace('_', ' ').capitalize()} ({noun})"

    def get_description(self):
        text = super().get_description() or ""
        perm = self._permission()
        if perm and perm != "__member__":
            note = f"**Permission:** `{perm}` (checked against the caller's role, organization and site scope)."
            return f"{text}\n\n{note}" if text else note
        return text


def postprocess(result, generator, request, public):
    comps = result.setdefault("components", {})
    comps.setdefault("schemas", {})["ErrorResponse"] = ERROR_SCHEMA
    comps.setdefault("parameters", {})["OrganizationHeader"] = ORG_HEADER_PARAM
    schemes = comps.setdefault("securitySchemes", {})
    if "jwtAuth" in schemes:
        schemes["jwtAuth"]["description"] = ("API access token from POST /api/v1/auth/token/. Paste only the token; "
                                             "Swagger sends `Authorization: Bearer <token>`. Expires in 15 minutes.")
    if "cookieAuth" in schemes:
        schemes["cookieAuth"]["description"] = ("Django browser session used by the web UI (and Swagger when you are "
                                                "logged in to the site). Accepted by the same endpoints, but API "
                                                "consumers should use jwtAuth.")
    err = {code: {"description": text, "content": {"application/json": {"schema": {"$ref": ERROR_REF}}}}
           for code, text in ERROR_TEXT.items()}

    for path, item in result["paths"].items():
        in_path = set(re.findall(r"{(\w+)}", path))
        for method, op in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            # class-level ID_PARAM leaks onto collection operations: keep only params that exist in the URL
            op["parameters"] = [p for p in op.get("parameters", []) if p["in"] != "path" or p["name"] in in_path]
            responses = op.setdefault("responses", {})
            secured = bool(op.get("security"))
            wanted = []
            if secured:
                op["parameters"].append({"$ref": ORG_HEADER_REF})
                wanted += ["401", "403"]
                if in_path:
                    wanted.append("404")
            if method in ("post", "put", "patch") or "token" in path:
                wanted.append("400")
            if secured and in_path and method in ("post", "patch", "delete"):
                wanted.append("409")
            if "token" in path:
                wanted.append("401")
            for code in wanted:
                responses.setdefault(code, err[code])
            if not op["parameters"]:
                del op["parameters"]
    return result
