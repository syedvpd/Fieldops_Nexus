"""RBAC service layer: permission sync, system-role seeding, authorization checks, role management.

Authorization decision (docs/blueprint/06):
    identity + org membership + permission + tenant object + scope + valid state
``has_permission`` answers the *permission* term for an already-verified, active membership; the tenant
object term is enforced by ``TenantManager``; the state term by ``core.workflow``.
"""
from __future__ import annotations

from fnmatch import fnmatchcase

from django.db import transaction

from apps.audit import services as audit
from apps.core.exceptions import Conflict, PermissionDenied, ValidationFailed

from . import catalog
from .models import MembershipRole, Permission, Role, RolePermission
from .role_templates import BY_KEY, TEMPLATES

# --- catalog / system roles ------------------------------------------------------------------


def sync_permissions() -> int:
    """Mirrors the in-code catalog into the Permission table. Returns number of rows created."""
    existing = {p.code: p for p in Permission.objects.all()}
    created = 0
    for d in catalog.all_defs():
        row = existing.get(d.code)
        if row is None:
            Permission.objects.create(code=d.code, module=d.module, description=d.description)
            created += 1
        elif (row.module, row.description) != (d.module, d.description):
            row.module, row.description = d.module, d.description
            row.save(update_fields=["module", "description", "updated_at"])
    return created


def _template_codes(template) -> set[str]:
    codes = catalog.all_codes()
    return {c for c in codes if any(fnmatchcase(c, p) for p in template.patterns)}


@transaction.atomic
def seed_system_roles(org) -> dict[str, Role]:
    """Creates any missing system roles for ``org`` and ADDS missing template permissions."""
    sync_permissions()
    perm_by_code = {p.code: p for p in Permission.objects.all()}
    roles: dict[str, Role] = {}
    for tpl in TEMPLATES:
        role = Role.objects.unscoped().filter(organization=org, system_key=tpl.key).first()
        if role is None:
            role = Role(organization=org, name=tpl.name, description=tpl.description,
                        system_key=tpl.key, is_owner=tpl.is_owner)
            role.save()
        have = set(role.role_permissions.values_list("permission__code", flat=True))
        for code in sorted(_template_codes(tpl) - have):
            RolePermission.objects.create(role=role, permission=perm_by_code[code])
        roles[tpl.key] = role
    return roles


def sync_all_organizations() -> int:
    from apps.tenancy.models import Organization

    count = 0
    for org in Organization.objects.all():
        seed_system_roles(org)
        count += 1
    return count


# --- checks ----------------------------------------------------------------------------------


def membership_permissions(membership) -> frozenset[str]:
    """All permission codes held by an ACTIVE membership (cached on the instance per request)."""
    cached = getattr(membership, "_perm_cache", None)
    if cached is not None:
        return cached
    if not membership.is_active:
        perms: frozenset[str] = frozenset()
    else:
        roles = Role.objects.unscoped().filter(
            organization_id=membership.organization_id, membership_roles__membership=membership
        )
        if roles.filter(is_owner=True).exists():
            perms = frozenset(catalog.all_codes())
        else:
            perms = frozenset(
                RolePermission.objects.filter(role__in=roles).values_list("permission__code", flat=True)
            )
    membership._perm_cache = perms
    return perms


def has_permission(membership, code: str) -> bool:
    if membership is None:
        return False
    if not catalog.is_registered(code):
        raise ValueError(f"Unknown permission code '{code}' (not in catalog).")
    return code in membership_permissions(membership)


def is_owner(membership) -> bool:
    if membership is None or not membership.is_active:
        return False
    return MembershipRole.objects.filter(membership=membership, role__is_owner=True).exists()


# --- owner protection ----------------------------------------------------------------------


def owner_memberships(org, *, exclude=None):
    from apps.tenancy.models import Membership

    qs = Membership.objects.unscoped().filter(
        organization=org,
        status__in=[Membership.Status.ACTIVE, Membership.Status.INVITED],
        membership_roles__role__is_owner=True,
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.distinct()


def assert_not_last_owner(membership):
    if is_owner(membership) or MembershipRole.objects.filter(membership=membership, role__is_owner=True).exists():
        if not owner_memberships(membership.organization, exclude=membership).exists():
            raise Conflict(
                "An organization must keep at least one Owner.", code="last_owner",
            )


# --- membership role assignment ----------------------------------------------------------------


@transaction.atomic
def set_membership_roles(membership, roles: list[Role], *, actor, request=None, system: bool = False):
    """Replaces the roles of a membership. Only Owners may grant or revoke the Owner role."""
    org = membership.organization
    for r in roles:
        if r.organization_id != org.pk:
            raise ValidationFailed("Role belongs to a different organization.", code="cross_tenant_role")
    current = {mr.role_id: mr for mr in MembershipRole.objects.filter(membership=membership).select_related("role")}
    new_ids = {r.pk for r in roles}
    touches_owner = any(r.is_owner for r in roles if r.pk not in current) or any(
        mr.role.is_owner for rid, mr in current.items() if rid not in new_ids
    )
    if touches_owner and not system:
        actor_membership = _membership_of(actor, org)
        if not is_owner(actor_membership):
            raise PermissionDenied("Only an Owner can grant or revoke the Owner role.", code="owner_only")
    removed_owner = any(mr.role.is_owner for rid, mr in current.items() if rid not in new_ids)
    if removed_owner and not any(r.is_owner for r in roles):
        assert_not_last_owner(membership)

    before = sorted(mr.role.name for mr in current.values())
    for rid, mr in current.items():
        if rid not in new_ids:
            mr.delete()
    for r in roles:
        if r.pk not in current:
            MembershipRole.objects.create(membership=membership, role=r)
    membership._perm_cache = None
    after = sorted(r.name for r in roles)
    if before != after:
        audit.record("membership.roles_changed", actor=actor, organization=org, target=membership,
                     before={"roles": before}, after={"roles": after}, request=request)


def _membership_of(user, org):
    from apps.tenancy.models import Membership

    if user is None:
        return None
    return Membership.objects.unscoped().filter(user=user, organization=org).first()


# --- role management -------------------------------------------------------------------------


@transaction.atomic
def create_role(org, *, name: str, description: str, permission_codes: list[str], actor, request=None) -> Role:
    name = name.strip()
    if not name:
        raise ValidationFailed("Role name is required.")
    if Role.objects.unscoped().filter(organization=org, name__iexact=name).exists():
        raise Conflict("A role with this name already exists.", code="duplicate_role")
    role = Role(organization=org, name=name, description=description.strip())
    role.save()
    _apply_permissions(role, permission_codes)
    audit.record("role.created", actor=actor, organization=org, target=role,
                 after={"name": name, "permissions": sorted(permission_codes)}, request=request)
    return role


@transaction.atomic
def update_role(role: Role, *, name: str, description: str, permission_codes: list[str], actor, request=None):
    if role.is_owner:
        raise PermissionDenied("The Owner role is locked.", code="role_locked")
    name = name.strip()
    if not name:
        raise ValidationFailed("Role name is required.")
    if role.is_system and name != role.name:
        raise ValidationFailed("System roles cannot be renamed.", code="system_role")
    if Role.objects.unscoped().filter(organization=role.organization, name__iexact=name).exclude(pk=role.pk).exists():
        raise Conflict("A role with this name already exists.", code="duplicate_role")
    before = {"name": role.name, "description": role.description,
              "permissions": sorted(role.role_permissions.values_list("permission__code", flat=True))}
    role.name, role.description = name, description.strip()
    role.save()
    _apply_permissions(role, permission_codes)
    audit.record("role.updated", actor=actor, organization=role.organization, target=role, before=before,
                 after={"name": name, "description": role.description, "permissions": sorted(permission_codes)},
                 request=request)
    # cached permission sets of in-flight requests are per-request only; nothing global to invalidate


def _apply_permissions(role: Role, codes: list[str]):
    codes = set(codes)
    unknown = codes - catalog.all_codes()
    if unknown:
        raise ValidationFailed("Unknown permissions.", details={"unknown": sorted(unknown)})
    perm_by_code = {p.code: p for p in Permission.objects.filter(code__in=codes)}
    existing = {rp.permission.code: rp for rp in role.role_permissions.select_related("permission")}
    for code, rp in existing.items():
        if code not in codes:
            rp.delete()
    for code in codes - set(existing):
        RolePermission.objects.create(role=role, permission=perm_by_code[code])


@transaction.atomic
def delete_role(role: Role, *, actor, request=None):
    if role.is_system:
        raise PermissionDenied("System roles cannot be deleted.", code="system_role")
    if role.membership_roles.exists():
        raise Conflict("Role is assigned to users; reassign them first.", code="role_in_use")
    snap = {"name": role.name}
    org = role.organization
    pk = role.pk
    role.delete()
    audit.record("role.deleted", actor=actor, organization=org, target_repr=f"Role {snap['name']} ({pk})",
                 before=snap, request=request)


def system_role_by_key(org, key: str) -> Role:
    if key not in BY_KEY:
        raise KeyError(key)
    return Role.objects.unscoped().get(organization=org, system_key=key)
