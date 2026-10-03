"""Permission catalog registry. Each app declares its permissions in ``<app>/permissions.py`` by calling
``register()``; ``rbac.apps`` autodiscovers those modules. Codes are ``<resource>.<action>`` (further
dots allowed, e.g. ``asset.history.view``). The DB table is a synced mirror (post_migrate)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    code: str
    module: str
    description: str
    site_scoped: bool = False  # may be granted per site (MembershipRole.site); False = organization-wide only


_REGISTRY: dict[str, PermissionDef] = {}


def register(module: str, code: str, description: str, *, site_scoped: bool = False) -> None:
    existing = _REGISTRY.get(code)
    if existing and existing.module != module:
        raise ValueError(f"Permission {code} already registered by module {existing.module}.")
    _REGISTRY[code] = PermissionDef(code, module, description, site_scoped)


def all_defs() -> list[PermissionDef]:
    return sorted(_REGISTRY.values(), key=lambda d: (d.module, d.code))


def all_codes() -> set[str]:
    return set(_REGISTRY)


def site_scoped_codes() -> set[str]:
    return {c for c, d in _REGISTRY.items() if d.site_scoped}


def is_registered(code: str) -> bool:
    return code in _REGISTRY
