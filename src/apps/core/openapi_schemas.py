"""Response-shape serializers used only to document hand-built JSON responses in the OpenAPI contract."""
from rest_framework import serializers


class _Bucket(serializers.Serializer):
    met = serializers.IntegerField()
    met_late = serializers.IntegerField()
    breached = serializers.IntegerField()
    pending = serializers.IntegerField()
    not_applicable = serializers.IntegerField()
    compliance_percent = serializers.FloatField(allow_null=True)


class SLAMetrics(serializers.Serializer):
    trackings = serializers.IntegerField()
    active = serializers.IntegerField()
    paused = serializers.IntegerField()
    response = _Bucket()
    resolution = _Bucket()
    breaches_total = serializers.IntegerField()
    breaches_open = serializers.IntegerField()
    breaches_open_by_priority = serializers.DictField(child=serializers.IntegerField())
    breaches_escalated = serializers.IntegerField()
    targets = serializers.ListField(child=serializers.CharField())


class SLAProcessResult(serializers.Serializer):
    checked = serializers.IntegerField()
    warnings = serializers.IntegerField()
    breaches = serializers.IntegerField()
    escalations = serializers.IntegerField()
    errors = serializers.IntegerField()


class _AssetChange(serializers.Serializer):
    field = serializers.CharField()
    old = serializers.JSONField(allow_null=True)
    new = serializers.JSONField(allow_null=True)


class _AssetChangeRow(serializers.Serializer):
    id = serializers.UUIDField()
    action = serializers.CharField()
    actor = serializers.CharField(help_text="Actor email, or 'system'")
    occurred_at = serializers.DateTimeField()
    changes = _AssetChange(many=True)
    metadata = serializers.JSONField()


class AssetChangeLog(serializers.Serializer):
    count = serializers.IntegerField()
    results = _AssetChangeRow(many=True)


class _TreeIssue(serializers.Serializer):
    code = serializers.CharField(help_text="cross_tenant | site_mismatch | hierarchy_cycle | hierarchy_too_deep")
    asset = serializers.CharField(help_text="asset_tag")


class TreeValidation(serializers.Serializer):
    valid = serializers.BooleanField()
    nodes = serializers.IntegerField()
    issues = _TreeIssue(many=True)


class LinkValidation(serializers.Serializer):
    valid = serializers.BooleanField()
    code = serializers.CharField(required=False, help_text="Present when valid is false")
    message = serializers.CharField(required=False, help_text="Present when valid is false")


class _ChecklistRequirement(serializers.Serializer):
    template = serializers.UUIDField()
    name = serializers.CharField()
    version = serializers.IntegerField()
    required = serializers.BooleanField()
    state = serializers.CharField()
    inspection = serializers.UUIDField(allow_null=True)


class ChecklistRequirements(serializers.Serializer):
    work_order = serializers.UUIDField()
    blockers = serializers.ListField(child=serializers.CharField())
    checklists = _ChecklistRequirement(many=True)


class ScanReportResult(serializers.Serializer):
    id = serializers.UUIDField(help_text="New service request id")
    number = serializers.CharField()
    status = serializers.CharField()
    asset = serializers.UUIDField()


class GeneratedNothing(serializers.Serializer):
    generated = serializers.BooleanField(help_text="false: no occurrence was due / already generated")


class PortalStatus(serializers.Serializer):
    number = serializers.CharField()
    status = serializers.CharField()
    client_status = serializers.CharField()
    visit = serializers.JSONField(allow_null=True)


class PortalAttachmentResult(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    size = serializers.IntegerField()


class WorkOrderClosure(serializers.Serializer):
    closable = serializers.BooleanField()
    blockers = serializers.ListField(child=serializers.CharField())


class DashboardFilters(serializers.Serializer):
    site = serializers.UUIDField(allow_null=True)
    from_ = serializers.DateField(source="from")
    to = serializers.DateField()


class DashboardSections(serializers.Serializer):
    sections = serializers.ListField(child=serializers.JSONField(), help_text="Sections the caller may open")
    my_work = serializers.BooleanField()
    definitions = serializers.DictField(child=serializers.CharField(), help_text="KPI key -> definition")


class DashboardSection(serializers.Serializer):
    filters = DashboardFilters()
    data = serializers.DictField(help_text="Section-specific KPIs/series (see /dashboards/ definitions)")
