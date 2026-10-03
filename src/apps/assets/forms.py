from django import forms

from apps.sites.models import Site, Zone
from apps.tenancy.models import Membership
from apps.ui.forms import BootstrapFormMixin

from .models import AssetCategory, AssetComponent, AssetDocument


class _ZoneChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.site.code} · {obj.name}"


class _OwnerChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.user.display_name


class AssetForm(BootstrapFormMixin, forms.Form):
    asset_tag = forms.CharField(max_length=40, label="Asset tag", help_text="Human-readable ID, unique in the organization.")
    name = forms.CharField(max_length=200)
    category = forms.ModelChoiceField(queryset=AssetCategory.objects.none())
    site = forms.ModelChoiceField(queryset=Site.objects.none())
    zone = _ZoneChoice(queryset=Zone.objects.none(), required=False, label="Location (building / zone)",
                       empty_label="(none)")
    manufacturer = forms.CharField(max_length=100, required=False)
    model = forms.CharField(max_length=100, required=False)
    serial_number = forms.CharField(max_length=100, required=False)
    purchase_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    commission_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                                      label="Commissioning date")
    owner = _OwnerChoice(queryset=Membership.objects.none(), required=False, label="Owner / custodian",
                         empty_label="(none)")
    warranty_ref = forms.CharField(max_length=200, required=False, label="Warranty reference",
                                   help_text="Free-text reference; coverage tracking arrives with the warranty module.")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    reason = forms.CharField(max_length=500, required=False, label="Reason for location change",
                             help_text="Recorded in the location history when the site or location changes.")

    def __init__(self, *args, sites, org, creating=True, **kwargs):
        super().__init__(*args, **kwargs)
        site_qs = sites.filter(status="ACTIVE").order_by("code")
        self.fields["site"].queryset = site_qs
        self.fields["zone"].queryset = Zone.objects.for_organization(org).filter(
            site__in=site_qs, status="ACTIVE").select_related("site").order_by("site__code", "name")
        self.fields["category"].queryset = AssetCategory.objects.for_organization(org).filter(is_active=True)
        self.fields["owner"].queryset = Membership.objects.for_organization(org).filter(
            status=Membership.Status.ACTIVE).select_related("user").order_by("user__full_name")
        if creating:
            del self.fields["reason"]
        self.fields["zone"].widget.attrs["data-site-filter"] = "1"
        self.fields["site"].widget.attrs["data-site-select"] = "1"

    def clean(self):
        data = super().clean()
        site, zone = data.get("site"), data.get("zone")
        if site and zone and zone.site_id != site.pk:
            self.add_error("zone", "This location does not belong to the selected site.")
        return data


class RelationshipFields(forms.Form):
    relationship_type = forms.ChoiceField(choices=AssetComponent.Relationship.choices, initial="COMPONENT")
    quantity = forms.IntegerField(min_value=1, initial=1)
    part_number = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(max_length=300, required=False)


class NewChildForm(BootstrapFormMixin, RelationshipFields):
    """Extra fields shown on the create-asset form when registering a child of an existing asset."""


class ComponentAddForm(BootstrapFormMixin, RelationshipFields):
    child = forms.ModelChoiceField(queryset=None, label="Existing asset")

    def __init__(self, *args, candidates, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["child"].queryset = candidates
        self.order_fields(["child", "relationship_type", "quantity", "part_number", "notes"])


class ComponentMoveForm(BootstrapFormMixin, forms.Form):
    parent = forms.ModelChoiceField(queryset=None, label="New parent")

    def __init__(self, *args, candidates, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = candidates


class DocumentForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField()
    title = forms.CharField(max_length=150, required=False)
    doc_type = forms.ChoiceField(choices=AssetDocument.DocType.choices, initial="OTHER", label="Type")


class MeterForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(max_length=80, help_text="e.g. Run hours")
    unit = forms.CharField(max_length=20, help_text="e.g. h, km, cycles")


class ReadingForm(BootstrapFormMixin, forms.Form):
    value = forms.DecimalField(max_digits=16, decimal_places=3, min_value=0)
    read_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
                                  input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"],
                                  label="Reading time (blank = now)")
    notes = forms.CharField(max_length=300, required=False)


class CategoryForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(max_length=100)
    description = forms.CharField(max_length=300, required=False)
    is_active = forms.BooleanField(required=False, initial=True, label="Active")
