import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.rbac import services as rbac
from apps.tenancy import services as tenancy
from apps.tenancy.models import Membership

User = get_user_model()
PASSWORD = "Correct-Horse-Battery-9"  # test-only value


@pytest.fixture
def platform_admin(db):
    return User.objects.create_user(email="root@platform.test", password=PASSWORD, full_name="Root Admin",
                                    is_platform_admin=True)


def _activate(membership):
    membership.status = Membership.Status.ACTIVE
    membership.save(update_fields=["status"])
    u = membership.user
    u.set_password(PASSWORD)
    u.save()
    return membership


@pytest.fixture
def make_org(platform_admin):
    def _make(name, owner_email):
        org, m = tenancy.create_organization(name=name, owner_email=owner_email, owner_name=f"{name} Owner",
                                             actor=platform_admin)
        _activate(m)
        return org
    return _make


@pytest.fixture
def make_member(db):
    def _make(org, email, role_key, *, active=True):
        user = User.objects.filter(email=email).first() or User.objects.create_user(
            email=email, password=PASSWORD, full_name=email.split("@")[0])
        m = Membership(organization=org, user=user,
                       status=Membership.Status.ACTIVE if active else Membership.Status.SUSPENDED)
        m.save()
        rbac.set_membership_roles(m, [rbac.system_role_by_key(org, role_key)], actor=None, system=True)
        return m
    return _make


@pytest.fixture
def org_a(make_org):
    return make_org("Alpha Industries", "owner@alpha.test")


@pytest.fixture
def org_b(make_org):
    return make_org("Beta Utilities", "owner@beta.test")


@pytest.fixture
def owner_a(org_a):
    return User.objects.get(email="owner@alpha.test")


@pytest.fixture
def owner_b(org_b):
    return User.objects.get(email="owner@beta.test")


@pytest.fixture
def tech_a(org_a, make_member):
    return make_member(org_a, "tech@alpha.test", "technician").user


@pytest.fixture
def tech_b(org_b, make_member):
    return make_member(org_b, "tech@beta.test", "technician").user


@pytest.fixture
def api():
    return APIClient()


def api_as(user, org=None):
    c = APIClient()
    c.force_authenticate(user=user)
    if org is not None:
        c.credentials(HTTP_X_ORGANIZATION=org.slug)
    return c


@pytest.fixture
def as_user():
    return api_as


# --- Phase 1 helpers (sites / assets) -----------------------------------------------------------------------


@pytest.fixture
def make_site(db):
    from apps.sites import services as site_services

    def _make(org, code, name=None, **kw):
        return site_services.create_site(org, actor=None, code=code, name=name or f"Site {code}", **kw)
    return _make


@pytest.fixture
def make_zone(db):
    from apps.sites import services as site_services

    def _make(site, name, parent=None, **kw):
        return site_services.create_zone(site, actor=None, parent=parent, name=name, **kw)
    return _make


@pytest.fixture
def make_category(db):
    from apps.assets import services as asset_services

    def _make(org, name="Pump"):
        from apps.assets.models import AssetCategory
        existing = AssetCategory.objects.for_organization(org).filter(name__iexact=name).first()
        return existing or asset_services.create_category(org, name=name, actor=None)
    return _make


@pytest.fixture
def make_asset(db, make_category):
    from apps.assets import services as asset_services

    def _make(org, site, tag, *, zone=None, category=None, **kw):
        return asset_services.create_asset(
            org, site=site, zone=zone, category=category or make_category(org), actor=None,
            asset_tag=tag, name=kw.pop("name", f"Asset {tag}"), **kw)
    return _make


@pytest.fixture
def make_scoped_member(db):
    """Member whose role(s) apply only to the given sites."""
    def _make(org, email, role_key, sites):
        user = User.objects.filter(email=email).first() or User.objects.create_user(
            email=email, password=PASSWORD, full_name=email.split("@")[0])
        m = Membership(organization=org, user=user, status=Membership.Status.ACTIVE)
        m.save()
        role = rbac.system_role_by_key(org, role_key)
        rbac.set_membership_assignments(m, [(role, s) for s in sites], actor=None, system=True)
        return m
    return _make


@pytest.fixture
def site_a1(org_a, make_site):
    return make_site(org_a, "A1")


@pytest.fixture
def site_a2(org_a, make_site):
    return make_site(org_a, "A2")


@pytest.fixture
def site_b1(org_b, make_site):
    return make_site(org_b, "B1")
