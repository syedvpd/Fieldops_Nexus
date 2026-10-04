"""Gap closure M02 / M03: asset document removal and component relationship edit (service, API, UI, RBAC, tenant)."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from rest_framework.test import APIClient

from apps.assets import hierarchy
from apps.assets import services as asset_services
from apps.assets.models import AssetComponent
from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, ValidationFailed

pytestmark = pytest.mark.django_db


@pytest.fixture
def p3(p3, make_member):
    """Phase 3 organization where ``ops`` is an asset manager (owns the registry, documents and hierarchy)."""
    return {**p3, "ops": make_member(p3["org"], "am@alpha.test", "asset_manager")}


def pdf(name="manual.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n%fake manual body\n", content_type="application/pdf")


@pytest.fixture
def doc(p3):
    return asset_services.add_document(p3["asset"], pdf(), title="Pump manual", doc_type="MANUAL",
                                       actor=p3["ops"].user)


def web(user):
    c = Client()
    c.force_login(user)
    return c


def test_remove_document_hides_it_blocks_download_and_audits(p3, doc):
    from apps.assets.selectors import documents_for

    asset_services.remove_document(doc, reason="superseded by v2", actor=p3["ops"].user)
    doc.refresh_from_db()
    assert not doc.is_active and doc.removed_by == p3["ops"].user and doc.removed_reason == "superseded by v2"
    assert not documents_for(p3["org"], p3["asset"]).exists()
    assert documents_for(p3["org"], p3["asset"], include_removed=True).count() == 1
    assert AuditLog.objects.filter(action="asset.document_removed", organization=p3["org"]).exists()
    assert web(p3["ops"].user).get(f"/app/files/{doc.attachment_id}/download/").status_code in (403, 404)


def test_remove_document_needs_reason_and_is_not_repeatable(p3, doc):
    with pytest.raises(ValidationFailed):
        asset_services.remove_document(doc, reason=" ", actor=p3["ops"].user)
    asset_services.remove_document(doc, reason="obsolete", actor=p3["ops"].user)
    with pytest.raises(Conflict):
        asset_services.remove_document(doc, reason="again", actor=p3["ops"].user)


def test_remove_document_api_and_rbac(p3, doc, org_b, make_member):
    owner = APIClient()
    owner.force_authenticate(user=p3["ops"].user)
    owner.credentials(HTTP_X_ORGANIZATION=p3["org"].slug)
    url = f"/api/v1/assets/{p3['asset'].pk}/documents/{doc.pk}/remove/"
    tech = APIClient()
    tech.force_authenticate(user=p3["tech"].user)
    tech.credentials(HTTP_X_ORGANIZATION=p3["org"].slug)
    assert tech.post(url, {"reason": "nope"}, format="json").status_code == 403
    stranger = make_member(org_b, "am@beta.test", "asset_manager")
    other = APIClient()
    other.force_authenticate(user=stranger.user)
    other.credentials(HTTP_X_ORGANIZATION=org_b.slug)
    assert other.post(url, {"reason": "nope"}, format="json").status_code == 404
    r = owner.post(url, {"reason": "wrong asset"}, format="json")
    assert r.status_code == 200 and r.json()["is_active"] is False
    listing = owner.get(f"/api/v1/assets/{p3['asset'].pk}/documents/").json()
    assert listing["results"] == []


def test_remove_document_ui(p3, doc):
    c = web(p3["ops"].user)
    r = c.post(f"/app/assets/documents/{doc.pk}/remove/", {"reason": "duplicate upload"})
    assert r.status_code == 302
    doc.refresh_from_db()
    assert not doc.is_active
    assert web(p3["tech"].user).post(f"/app/assets/documents/{doc.pk}/remove/", {"reason": "x y z"}).status_code == 403


def test_component_relationship_edit_ui_persists_and_audits(p3, make_asset):
    child = make_asset(p3["org"], p3["site"], "P3-MOTOR")
    link = hierarchy.add_component(p3["asset"], child, actor=p3["ops"].user)
    c = web(p3["ops"].user)
    r = c.post(f"/app/components/{link.pk}/edit/",
               {"relationship_type": "REPLACEABLE_PART", "quantity": 3, "part_number": "BRG-6204", "notes": "spare"})
    assert r.status_code == 302
    link = AssetComponent.objects.get(pk=link.pk)
    assert (link.relationship_type, link.quantity, link.part_number) == ("REPLACEABLE_PART", 3, "BRG-6204")
    assert AuditLog.objects.filter(action="asset.component_updated", organization=p3["org"]).exists()
    page = c.get(f"/app/assets/{child.pk}/?tab=hierarchy").content.decode()
    assert "Edit relationship" in page and "BRG-6204" in page
    bad = c.post(f"/app/components/{link.pk}/edit/", {"relationship_type": "COMPONENT", "quantity": 0})
    assert bad.status_code == 302 and AssetComponent.objects.get(pk=link.pk).quantity == 3


def test_component_edit_refused_for_wrong_role_and_other_tenant(p3, make_asset, org_b, make_member):
    child = make_asset(p3["org"], p3["site"], "P3-MOTOR2")
    link = hierarchy.add_component(p3["asset"], child, actor=p3["ops"].user)
    data = {"relationship_type": "COMPONENT", "quantity": 2}
    assert web(p3["tech"].user).post(f"/app/components/{link.pk}/edit/", data).status_code in (403, 404)
    stranger = make_member(org_b, "am@beta.test", "asset_manager")
    assert web(stranger.user).post(f"/app/components/{link.pk}/edit/", data).status_code == 404
