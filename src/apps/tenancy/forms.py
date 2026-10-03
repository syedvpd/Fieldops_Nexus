from django import forms

from apps.rbac.models import Role


class OrganizationForm(forms.Form):
    name = forms.CharField(max_length=150)
    legal_name = forms.CharField(max_length=200, required=False)
    timezone = forms.CharField(max_length=64)
    country = forms.CharField(max_length=2, required=False, help_text="ISO country code, e.g. IN")
    contact_email = forms.EmailField(required=False)
    contact_phone = forms.CharField(max_length=32, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)


def _role_field(org):
    return forms.ModelMultipleChoiceField(
        queryset=Role.objects.for_organization(org).order_by("name"),
        widget=forms.CheckboxSelectMultiple, label="Roles",
    )


class InviteForm(forms.Form):
    email = forms.EmailField()
    full_name = forms.CharField(max_length=150, required=False, help_text="Required for new accounts.")

    def __init__(self, *args, org, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"] = _role_field(org)


class MemberEditForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    job_title = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, org, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"] = _role_field(org)


class RoleForm(forms.Form):
    name = forms.CharField(max_length=80)
    description = forms.CharField(max_length=300, required=False)
