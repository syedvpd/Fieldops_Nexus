"""OpenAPI contract guard: the published schema must describe what the API really does (see docs/API_OPENAPI_SCHEMA_AUDIT.md)."""
import re

import pytest
from drf_spectacular.generators import SchemaGenerator

OPS = ("get", "post", "put", "patch", "delete")


@pytest.fixture(scope="module")
def schema():
    return SchemaGenerator().get_schema(request=None, public=True)


def _ops(schema):
    for path, item in schema["paths"].items():
        for method, op in item.items():
            if method in OPS:
                yield path, method, op


def _refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref":
                yield v
            else:
                yield from _refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _refs(v)


def _resolve(schema, ref):
    node = schema
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def test_every_ref_resolves(schema):
    for ref in set(_refs(schema)):
        assert _resolve(schema, ref) is not None, ref


def test_path_parameters_match_url(schema):
    for path, method, op in _ops(schema):
        declared = {p["name"] for p in op.get("parameters", []) if p.get("in") == "path"}
        assert declared == set(re.findall(r"{(\w+)}", path)), f"{method.upper()} {path}"


def test_token_endpoints_expose_request_bodies(schema):
    token = schema["paths"]["/api/v1/auth/token/"]["post"]
    body = _resolve(schema, token["requestBody"]["content"]["application/json"]["schema"]["$ref"])
    assert set(body["required"]) == {"email", "password"}
    refresh = schema["paths"]["/api/v1/auth/token/refresh/"]["post"]
    assert "refresh" in _resolve(schema, refresh["requestBody"]["content"]["application/json"]["schema"]["$ref"])["properties"]
    assert "/api/v1/auth/me/" in schema["paths"]


def test_protected_operations_advertise_jwt_and_errors(schema):
    assert "jwtAuth" in schema["components"]["securitySchemes"]
    for path, method, op in _ops(schema):
        if path.startswith("/api/v1/auth/token"):
            continue
        assert {"jwtAuth": []} in op["security"], f"{method.upper()} {path}"
        assert {"401", "403"} <= set(op["responses"]), f"{method.upper()} {path}"


def test_write_operations_have_typed_request_bodies(schema):
    bodyless = 0
    for path, method, op in _ops(schema):
        if method not in ("post", "put", "patch"):
            continue
        rb = op.get("requestBody")
        if rb is None:
            bodyless += 1  # explicit request=None actions (activate/disable/confirm...) take no body
            continue
        for ct, content in rb["content"].items():
            assert "$ref" in content["schema"], f"{method.upper()} {path} {ct} has an untyped body"
    assert bodyless < 40


def test_paginated_lists_document_the_envelope(schema):
    for path in ("/api/v1/work-orders/", "/api/v1/assets/", "/api/v1/members/", "/api/v1/sites/"):
        ok = schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in ok and _resolve(schema, ok["$ref"])["properties"].keys() >= {"count", "results"}, path


def test_no_generic_object_responses(schema):
    for path, method, op in _ops(schema):
        for code, resp in op["responses"].items():
            for content in resp.get("content", {}).values():
                s = content.get("schema", {})
                assert not (s.get("type") == "object" and not s.get("properties") and "$ref" not in s
                            and "additionalProperties" not in s), f"{method.upper()} {path} {code}"


def test_organization_header_documented_as_selector_only(schema):
    param = schema["components"]["parameters"]["OrganizationHeader"]
    assert param["name"] == "X-Organization" and "SELECTS" in param["description"]
