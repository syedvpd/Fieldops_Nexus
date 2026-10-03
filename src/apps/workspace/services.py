"""M07 service layer. The workspace owns only the technician's notes; every other action (lifecycle, labor,
material, evidence, checklists) is a call into the owning module's service (M06 ``workorders.services``, M08
``checklists.services``), so there is exactly one implementation of each rule."""
from __future__ import annotations

from django.db import transaction

from apps.audit import services as audit
from apps.core.exceptions import ValidationFailed
from apps.workorders import services as wos

from .models import WorkNote

MAX_NOTE = 2000


@transaction.atomic
def add_note(wo, *, body: str, actor, membership, request=None) -> WorkNote:
    from apps.workorders.models import WorkOrder

    wo = WorkOrder.objects.select_for_update().get(pk=wo.pk)
    wos.assert_recordable(wo, membership)  # same state / assignee rule as labor and material
    body = (body or "").strip()
    if len(body) < 3:
        raise ValidationFailed("Write a note of at least 3 characters.", code="note_required")
    if len(body) > MAX_NOTE:
        raise ValidationFailed(f"Keep the note under {MAX_NOTE} characters.", code="note_too_long")
    note = WorkNote(organization=wo.organization, work_order=wo, author=actor, body=body)
    note.save()
    audit.record("work_order.note_added", actor=actor, organization=wo.organization, target=wo,
                 metadata={"note": str(note.pk), "length": len(body)}, request=request)
    return note
