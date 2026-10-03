from django import forms

from apps.checklists.models import Finding
from apps.ui.forms import BootstrapFormMixin


class NoteForm(BootstrapFormMixin, forms.Form):
    body = forms.CharField(min_length=3, max_length=2000, label="Note",
                           widget=forms.Textarea(attrs={"rows": 3, "placeholder": "What did you find or do?"}))


class FindingForm(BootstrapFormMixin, forms.Form):
    description = forms.CharField(min_length=3, widget=forms.Textarea(attrs={"rows": 2}), label="Finding")
    severity = forms.ChoiceField(choices=Finding.Severity.choices, initial="MEDIUM")
    item = forms.UUIDField(required=False, widget=forms.HiddenInput)
