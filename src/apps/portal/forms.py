from django import forms

from apps.assets.models import Asset
from apps.ui.forms import BootstrapFormMixin


class _AssetChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.asset_tag} · {obj.name} ({obj.site.code})"


class NewRequestForm(BootstrapFormMixin, forms.Form):
    asset = _AssetChoice(queryset=Asset.objects.none(), label="Which equipment?", empty_label="Select equipment")
    kind = forms.ChoiceField(choices=[("INCIDENT", "Something is broken or not working"),
                                      ("SERVICE_REQUEST", "I need a service / request something")],
                             widget=forms.RadioSelect, initial="INCIDENT", label="What kind of request?")
    title = forms.CharField(max_length=200, label="Short summary")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}),
                                 label="Describe the problem",
                                 help_text="What happened, when, and anything we should know before we visit.")
    urgency = forms.ChoiceField(choices=[("LOW", "Low: can wait"), ("MEDIUM", "Medium: affects work"),
                                         ("HIGH", "High: work has stopped")], initial="MEDIUM")

    def __init__(self, *args, assets, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = assets


class ReasonForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(max_length=300, label="What is still wrong?",
                             widget=forms.Textarea(attrs={"rows": 3}))


class AccountForm(BootstrapFormMixin, forms.Form):
    membership = forms.ChoiceField(label="Client user")
    company = forms.CharField(max_length=150, required=False, label="Company / department")

    def __init__(self, *args, members=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["membership"].choices = [("", "Select a client user")] + [
            (str(m.pk), f"{m.user.display_name} · {m.user.email}") for m in members]


class GrantForm(BootstrapFormMixin, forms.Form):
    asset = _AssetChoice(queryset=Asset.objects.none())

    def __init__(self, *args, assets, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = assets
