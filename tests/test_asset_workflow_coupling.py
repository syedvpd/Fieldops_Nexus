"""D-058: the work-order lifecycle drives the asset status through the asset state machine (HPE 8.4)."""
import pytest

from apps.assets import services as asset_services
from apps.assets.models import AssetStatusHistory
from apps.audit.models import AuditLog
from tests.phase3_support import finish_work, new_wo, step, wo_in_progress

pytestmark = pytest.mark.django_db


def status(asset):
    asset.refresh_from_db()
    return asset.status


def to_review(wo, p3):
    wo = finish_work(wo, p3)
    return step(wo, "start_review", p3, "sup")


def test_start_makes_asset_under_maintenance_and_close_restores_active(p3):
    wo = wo_in_progress(p3, work_type="CORRECTIVE")
    assert status(p3["asset"]) == "UNDER_MAINTENANCE"
    h = AssetStatusHistory.objects.filter(asset=p3["asset"], source="work_order")
    assert [(x.from_status, x.to_status) for x in h] == [("ACTIVE", "UNDER_MAINTENANCE")]
    assert AuditLog.objects.filter(action="asset.status_changed", metadata__source="work_order").exists()
    wo = to_review(wo, p3)
    assert status(p3["asset"]) == "UNDER_MAINTENANCE"  # completion alone does not release the asset
    step(wo, "close", p3, "sup")
    assert status(p3["asset"]) == "ACTIVE"
    assert AssetStatusHistory.objects.filter(asset=p3["asset"], source="work_order").count() == 2


def test_hold_and_rework_do_not_duplicate_history(p3):
    wo = wo_in_progress(p3, work_type="PREVENTIVE")
    wo = step(wo, "hold", p3, "tech", reason="waiting for a part")
    wo = step(wo, "resume", p3, "tech")
    wo = to_review(wo, p3)
    wo = step(wo, "reject_review", p3, "sup", reason="redo the test")
    assert status(p3["asset"]) == "UNDER_MAINTENANCE"
    assert AssetStatusHistory.objects.filter(asset=p3["asset"], source="work_order").count() == 1


def test_inspection_work_does_not_change_status(p3):
    wo_in_progress(p3, work_type="INSPECTION")
    assert status(p3["asset"]) == "ACTIVE"


def test_out_of_service_asset_is_never_overwritten(p3):
    asset = p3["asset"]
    asset_services.change_status(asset, action="start_maintenance", reason="manual", actor=p3["ops"].user)
    asset_services.change_status(asset, action="mark_out_of_service", reason="beyond repair", actor=p3["ops"].user)
    wo = wo_in_progress(p3, work_type="CORRECTIVE")
    assert status(asset) == "OUT_OF_SERVICE"
    step(to_review(wo, p3), "close", p3, "sup")
    assert status(asset) == "OUT_OF_SERVICE"
    assert not AssetStatusHistory.objects.filter(asset=asset, source="work_order").exists()


def test_manual_under_maintenance_is_not_reverted_by_a_work_order_close(p3):
    asset = p3["asset"]
    asset_services.change_status(asset, action="start_maintenance", reason="manual overhaul", actor=p3["ops"].user)
    wo = wo_in_progress(p3, work_type="CORRECTIVE")
    step(to_review(wo, p3), "close", p3, "sup")
    assert status(asset) == "UNDER_MAINTENANCE"


def test_asset_stays_under_maintenance_while_another_order_runs(p3):
    first = wo_in_progress(p3, work_type="CORRECTIVE", tech="tech")
    second = wo_in_progress(p3, work_type="PREVENTIVE", tech="tech2")
    step(to_review(first, p3), "close", p3, "sup")
    assert status(p3["asset"]) == "UNDER_MAINTENANCE"
    second = step(finish_work(second, p3, tech="tech2"), "start_review", p3, "sup")
    step(second, "close", p3, "sup")
    assert status(p3["asset"]) == "ACTIVE"


def test_cancelled_before_start_leaves_asset_active(p3):
    wo = new_wo(p3, work_type="CORRECTIVE")
    step(wo, "cancel", p3, "planner", reason="duplicate")
    assert status(p3["asset"]) == "ACTIVE"
