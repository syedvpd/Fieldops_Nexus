"""M03 Asset Hierarchy: integrity rules, services, API, tenant isolation."""
import pytest
from django.db import IntegrityError, transaction

from apps.assets import hierarchy, services
from apps.assets.models import AssetComponent
from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, ValidationFailed

pytestmark = pytest.mark.django_db


def actions(org):
    return list(AuditLog.objects.filter(organization=org).values_list("action", flat=True))


@pytest.fixture
def trio(org_a, site_a1, make_asset):
    return [make_asset(org_a, site_a1, t) for t in ("G-1", "E-1", "P-1")]


def test_add_child_tree_and_ancestors(org_a, owner_a, trio):
    gen, engine, pump = trio
    hierarchy.add_component(gen, engine, relationship_type="ASSEMBLY", actor=owner_a)
    hierarchy.add_component(engine, pump, relationship_type="REPLACEABLE_PART", quantity=2, part_number="PN-9",
                            actor=owner_a)
    tree = hierarchy.build_tree(gen)
    assert [n["asset"].asset_tag for n in hierarchy.flatten(tree)] == ["G-1", "E-1", "P-1"]
    assert tree["children"][0]["children"][0]["link"].quantity == 2
    assert [a.asset_tag for a in hierarchy.ancestors(pump)] == ["E-1", "G-1"]
    assert hierarchy.root_of(pump).pk == gen.pk
    assert hierarchy.validate_tree(gen) == {"valid": True, "nodes": 3, "issues": []}
    assert actions(org_a).count("asset.component_added") == 2


def test_self_parent_rejected(owner_a, trio):
    with pytest.raises(ValidationFailed) as exc:
        hierarchy.add_component(trio[0], trio[0], actor=owner_a)
    assert exc.value.code == "self_parent"


def test_cycles_rejected_on_add_and_move(owner_a, trio):
    a, b, c = trio
    hierarchy.add_component(a, b, actor=owner_a)
    link_bc = hierarchy.add_component(b, c, actor=owner_a)
    with pytest.raises(ValidationFailed) as exc:
        hierarchy.add_component(c, a, actor=owner_a)  # A -> B -> C -> A
    assert exc.value.code == "hierarchy_cycle"
    link_ab = AssetComponent.objects.get(child=b)
    with pytest.raises(ValidationFailed) as exc:
        hierarchy.move_component(link_ab, c, actor=owner_a)  # moving B under its own descendant C
    assert exc.value.code == "hierarchy_cycle"
    assert AssetComponent.objects.get(child=b).parent_id == a.pk  # unchanged
    assert link_bc.parent_id == b.pk


def test_child_has_one_parent_and_can_be_moved(org_a, owner_a, trio):
    a, b, c = trio
    hierarchy.add_component(a, c, actor=owner_a)
    with pytest.raises(Conflict) as exc:
        hierarchy.add_component(b, c, actor=owner_a)
    assert exc.value.code == "already_has_parent"
    link = AssetComponent.objects.get(child=c)
    hierarchy.move_component(link, b, actor=owner_a)
    assert AssetComponent.objects.get(child=c).parent_id == b.pk
    with pytest.raises(Conflict):
        hierarchy.move_component(AssetComponent.objects.get(child=c), b, actor=owner_a)  # no change
    assert "asset.component_moved" in actions(org_a)


def test_same_site_and_same_organization_required(org_a, org_b, site_a1, site_a2, site_b1, make_asset, owner_a):
    a = make_asset(org_a, site_a1, "S-1")
    other_site = make_asset(org_a, site_a2, "S-2")
    foreign = make_asset(org_b, site_b1, "S-3")
    with pytest.raises(ValidationFailed) as exc:
        hierarchy.add_component(a, other_site, actor=owner_a)
    assert exc.value.code == "site_mismatch"
    with pytest.raises(ValidationFailed) as exc:
        hierarchy.add_component(a, foreign, actor=owner_a)
    assert exc.value.code == "cross_tenant"
    assert not AssetComponent.objects.unscoped().exists()


def test_depth_is_limited(org_a, site_a1, make_asset, owner_a):
    nodes = [make_asset(org_a, site_a1, f"D-{i}") for i in range(hierarchy.MAX_DEPTH + 1)]
    for parent, child in zip(nodes, nodes[1:hierarchy.MAX_DEPTH], strict=False):
        hierarchy.add_component(parent, child, actor=owner_a)
    with pytest.raises(ValidationFailed) as exc:
        hierarchy.add_component(nodes[hierarchy.MAX_DEPTH - 1], nodes[hierarchy.MAX_DEPTH], actor=owner_a)
    assert exc.value.code == "hierarchy_too_deep"


def test_terminal_assets_cannot_join_or_leave(org_a, owner_a, trio):
    a, b, c = trio
    link = hierarchy.add_component(a, b, actor=owner_a)
    for act in ("start_maintenance", "mark_out_of_service", "retire"):
        services.change_status(c, action=act, reason="eol", actor=owner_a)
    with pytest.raises(Conflict) as exc:
        hierarchy.add_component(a, c, actor=owner_a)
    assert exc.value.code == "asset_terminal"
    for act in ("start_maintenance", "mark_out_of_service", "dispose"):
        services.change_status(b, action=act, reason="eol", actor=owner_a)
    with pytest.raises(Conflict):
        hierarchy.remove_component(AssetComponent.objects.get(pk=link.pk), actor=owner_a)


def test_remove_update_and_audit(org_a, owner_a, trio):
    a, b, _ = trio
    link = hierarchy.add_component(a, b, actor=owner_a)
    hierarchy.update_component(link, actor=owner_a, quantity=4, relationship_type="ASSEMBLY", notes="n")
    link.refresh_from_db()
    assert (link.quantity, link.relationship_type) == (4, "ASSEMBLY")
    with pytest.raises(ValidationFailed):
        hierarchy.update_component(link, actor=owner_a, quantity=0)
    hierarchy.remove_component(link, actor=owner_a)
    assert not AssetComponent.objects.exists()
    assert {"asset.component_added", "asset.component_updated", "asset.component_removed"} <= set(actions(org_a))


def test_moving_site_blocked_while_in_hierarchy(org_a, site_a2, owner_a, trio):
    a, b, _ = trio
    hierarchy.add_component(a, b, actor=owner_a)
    for asset in (a, b):
        with pytest.raises(Conflict) as exc:
            services.update_asset(asset, actor=owner_a, site=site_a2)
        assert exc.value.code == "asset_in_hierarchy"


def test_database_constraints(org_a, trio):
    a, b, c = trio
    with pytest.raises(IntegrityError), transaction.atomic():
        AssetComponent(organization=org_a, parent=a, child=a).save()
    AssetComponent(organization=org_a, parent=a, child=b).save()
    with pytest.raises(IntegrityError), transaction.atomic():
        AssetComponent(organization=org_a, parent=c, child=b).save()  # a child can have only one parent
    with pytest.raises(IntegrityError), transaction.atomic():
        AssetComponent(organization=org_a, parent=a, child=c, quantity=0).save()


def test_tree_query_count_is_bounded_by_depth(org_a, site_a1, make_asset, owner_a, django_assert_max_num_queries):
    root = make_asset(org_a, site_a1, "BQ-0")
    for i in range(10):
        child = make_asset(org_a, site_a1, f"BQ-{i + 1}")
        hierarchy.add_component(root, child, actor=owner_a)
    with django_assert_max_num_queries(hierarchy.MAX_DEPTH):
        assert len(hierarchy.flatten(hierarchy.build_tree(root))) == 11


# --- API ---------------------------------------------------------------------------------------------------------


def test_api_hierarchy_flow(as_user, owner_a, org_a, trio):
    gen, engine, pump = trio
    c = as_user(owner_a, org_a)
    r = c.post(f"/api/v1/assets/{gen.pk}/components/", {"child": str(engine.pk), "relationship_type": "ASSEMBLY"},
               format="json")
    assert r.status_code == 201, r.content
    link_id = r.json()["id"]
    assert c.post(f"/api/v1/assets/{engine.pk}/components/", {"child": str(pump.pk), "quantity": 3},
                  format="json").status_code == 201
    kids = c.get(f"/api/v1/assets/{gen.pk}/components/").json()
    assert kids["count"] == 1 and kids["results"][0]["child_tag"] == "E-1"
    tree = c.get(f"/api/v1/assets/{engine.pk}/tree/").json()
    assert [p["asset_tag"] for p in tree["path"]] == ["G-1"]
    assert tree["tree"]["children"][0]["asset_tag"] == "P-1" and tree["tree"]["children"][0]["quantity"] == 3
    assert c.get(f"/api/v1/assets/{pump.pk}/").json()["parent"]["asset_tag"] == "E-1"
    assert c.get(f"/api/v1/assets/{gen.pk}/validate/").json()["valid"] is True
    assert c.get(f"/api/v1/asset-components/?parent={gen.pk}").json()["count"] == 1
    # re-parent pump under generator, then patch + delete
    assert c.post(f"/api/v1/asset-components/{AssetComponent.objects.get(child=pump).pk}/move/",
                  {"parent": str(gen.pk)}, format="json").status_code == 200
    assert c.patch(f"/api/v1/asset-components/{link_id}/", {"quantity": 2}, format="json").json()["quantity"] == 2
    assert c.delete(f"/api/v1/asset-components/{link_id}/").status_code == 204
    assert AssetComponent.objects.filter(child=engine).count() == 0


def test_api_rejections(as_user, owner_a, org_a, trio):
    a, b, c3 = trio
    c = as_user(owner_a, org_a)
    c.post(f"/api/v1/assets/{a.pk}/components/", {"child": str(b.pk)}, format="json")
    c.post(f"/api/v1/assets/{b.pk}/components/", {"child": str(c3.pk)}, format="json")
    r = c.post(f"/api/v1/assets/{c3.pk}/components/", {"child": str(a.pk)}, format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "hierarchy_cycle"
    r = c.post(f"/api/v1/assets/{a.pk}/components/", {"child": str(a.pk)}, format="json")
    assert r.status_code == 400 and r.json()["error"]["code"] == "self_parent"
    r = c.post(f"/api/v1/assets/{a.pk}/components/", {"child": str(c3.pk)}, format="json")
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_has_parent"
    dry = c.post(f"/api/v1/assets/{c3.pk}/validate-link/", {"child": str(a.pk)}, format="json").json()
    assert dry == {"valid": False, "code": "hierarchy_cycle", "message": dry["message"]}
    assert c.post(f"/api/v1/assets/{a.pk}/components/", {"child": "bad"}, format="json").status_code == 400
    assert AssetComponent.objects.count() == 2  # nothing leaked through the rejected calls


def test_api_cross_tenant_child_is_not_found(as_user, owner_a, org_a, org_b, site_b1, make_asset, trio):
    foreign = make_asset(org_b, site_b1, "XT-1")
    r = as_user(owner_a, org_a).post(f"/api/v1/assets/{trio[0].pk}/components/", {"child": str(foreign.pk)},
                                     format="json")
    assert r.status_code == 404
    assert not AssetComponent.objects.unscoped().exists()


def test_api_rbac_for_hierarchy(as_user, tech_a, org_a, trio):
    a, b, _ = trio
    tech = as_user(tech_a, org_a)  # asset.view only
    assert tech.post(f"/api/v1/assets/{a.pk}/components/", {"child": str(b.pk)}, format="json").status_code == 403
    assert tech.post(f"/api/v1/assets/{a.pk}/validate-link/", {"child": str(b.pk)}, format="json").status_code == 403
    assert tech.get(f"/api/v1/assets/{a.pk}/tree/").status_code == 200
    assert AssetComponent.objects.count() == 0
