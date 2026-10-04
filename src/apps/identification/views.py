"""M12 HTML views: label panel / printable label / label images, scan page (camera optional, typed-token fallback),
resolution page and scan-to-request. Resolution authorizes AFTER the lookup (see services)."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.assets import selectors as asset_selectors
from apps.core.exceptions import DomainError
from apps.rbac import services as rbac
from apps.sites.views import need, or404
from apps.tenancy import selectors as tenancy
from apps.ui.forms import BootstrapFormMixin
from apps.ui.mixins import TenantPermissionMixin

from . import selectors, services
from .models import AssetIdentifier


class ReasonForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(max_length=300)


class ReportForm(BootstrapFormMixin, forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    severity = forms.ChoiceField(choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"),
                                          ("CRITICAL", "Critical")], initial="MEDIUM")


class QBase(TenantPermissionMixin, View):
    required_permission = "qr.view"


def _base(request) -> str:
    return request.build_absolute_uri("/")[:-1]


def _asset(request, asset_id, code="qr.view"):
    asset = or404(asset_selectors.get_asset, request.membership, request.organization, asset_id)
    need(request, code, asset.site_id)
    return asset


class AssetPanelView(QBase):
    """HTMX fragment of the asset page: current labels + history + actions."""

    def get(self, request, asset_id, status=200):
        asset = _asset(request, asset_id)
        m, org = request.membership, request.organization
        rows = list(selectors.for_asset(m, org, asset))
        active = {r.kind: r for r in rows if r.is_active}
        return render(request, "identification/_panel.html", {
            "asset": asset, "active": active, "history": [r for r in rows if not r.is_active][:10],
            "kinds": AssetIdentifier.Kind.choices, "reason_form": ReasonForm(),
            "scans": selectors.recent_scans(org, asset), "terminal": asset.status in services.TERMINAL,
            "can_generate": rbac.has_permission(m, "qr.generate", asset.site_id)}, status=status)


class AssetPanelActionView(QBase):
    required_permission = "qr.generate"
    http_method_names = ["post"]

    def post(self, request, asset_id, action):
        asset = _asset(request, asset_id, "qr.generate")
        m, org = request.membership, request.organization
        try:
            if action == "generate":
                services.generate(asset, request.POST.get("kind", ""), actor=request.user, request=request)
                msg = "Label generated."
            else:
                ident = or404(selectors.get_identifier, m, org, request.POST.get("identifier"))
                if ident.asset_id != asset.pk:
                    raise Http404
                form = ReasonForm(request.POST)
                if not form.is_valid():
                    raise DomainError("A reason is required.")
                if action == "revoke":
                    services.revoke(ident, reason=form.cleaned_data["reason"], actor=request.user, request=request)
                    msg = "Label revoked: its token no longer resolves."
                elif action == "replace":
                    services.regenerate(ident, reason=form.cleaned_data["reason"], actor=request.user,
                                        request=request)
                    msg = "Label replaced: print the new one; the old token no longer resolves."
                else:
                    raise Http404
            messages.success(request, msg)
        except DomainError as exc:
            messages.error(request, exc.message)
        return redirect(f"/app/assets/{asset.pk}/?tab=labels")


class LabelPageView(QBase):
    """Printable label sheet: QR + barcode with the human-readable asset tag."""

    def get(self, request, asset_id):
        asset = _asset(request, asset_id)
        m, org = request.membership, request.organization
        qr = selectors.active_for_asset(m, org, asset, "QR")
        bc = selectors.active_for_asset(m, org, asset, "BARCODE")
        return render(request, "identification/label.html", {
            "asset": asset, "qr": qr, "barcode": bc,
            "qr_svg": services.qr_svg(services.scan_url(qr.token, _base(request))) if qr else "",
            "barcode_svg": services.barcode_svg(bc.token) if bc else ""})


class LabelImageView(QBase):
    def get(self, request, asset_id, kind, fmt):
        asset = _asset(request, asset_id)
        ident = selectors.active_for_asset(request.membership, request.organization, asset, kind.upper())
        if ident is None:
            raise Http404
        name = f"{asset.asset_tag}-{kind}".replace(" ", "_")
        if kind == "qr":
            url = services.scan_url(ident.token, _base(request))
            body, ctype = (services.qr_svg(url), "image/svg+xml") if fmt == "svg" else (services.qr_png(url),
                                                                                         "image/png")
        elif fmt == "svg":
            body, ctype = services.barcode_svg(ident.token), "image/svg+xml"
        else:
            raise Http404
        resp = HttpResponse(body, content_type=ctype)
        resp["Cache-Control"] = "private, no-store"
        if request.GET.get("download"):
            resp["Content-Disposition"] = f'attachment; filename="{name}.{fmt}"'
        return resp


class ScanPageView(LoginRequiredMixin, View):
    """Camera (progressive, isolated JS) or typed token -> resolution page."""

    def _check(self, request):
        if getattr(request, "tenant_error", None) or getattr(request, "membership", None) is None:
            raise PermissionDenied

    def get(self, request):
        self._check(request)
        return render(request, "identification/scan.html")

    def post(self, request):
        self._check(request)
        token = services.extract_token(request.POST.get("token", ""))
        if not services.TOKEN_RE.match(token):
            messages.error(request, "That does not look like a FieldOps label code.")
            return render(request, "identification/scan.html", status=400)
        return redirect("identification:resolve", token=token)


class ResolveView(LoginRequiredMixin, View):
    def _res(self, request, token):
        if getattr(request, "tenant_error", None) or getattr(request, "membership", None) is None:
            raise PermissionDenied
        return services.resolve(request.user, token, request.membership, request=request)

    def get(self, request, token):
        res = self._res(request, token)
        if res.outcome == "THROTTLED":
            return render(request, "identification/not_found.html", {"throttled": True}, status=429)
        if res.outcome in ("UNKNOWN", "FORBIDDEN"):
            return render(request, "identification/not_found.html", status=404)
        if res.other_org:  # the label belongs to another of the user's own organizations: select it
            request.session[tenancy.SESSION_KEY] = str(res.membership.organization_id)
            messages.info(request, f"Switched to {res.membership.organization.name} for this label.")
            return redirect("identification:resolve", token=token)
        m = res.membership
        asset = res.asset
        return render(request, "identification/resolved.html", {
            "res": res, "asset": asset, "revoked": res.outcome == "REVOKED",
            "form": ReportForm(),
            "can_report": res.outcome == "RESOLVED" and not res.asset_inactive and rbac.has_permission(
                m, "incident.create", asset.site_id)})

    def post(self, request, token):
        res = self._res(request, token)
        if res.outcome == "THROTTLED":
            return render(request, "identification/not_found.html", {"throttled": True}, status=429)
        if res.outcome in ("UNKNOWN", "FORBIDDEN"):
            return render(request, "identification/not_found.html", status=404)
        form = ReportForm(request.POST)
        if form.is_valid():
            try:
                sr = services.report_from_scan(res, actor=request.user, request=request, **form.cleaned_data)
                messages.success(request, f"{sr.number} created for {res.asset.asset_tag}.")
                return redirect("incidents:detail", pk=sr.pk)
            except DomainError as exc:
                form.add_error(None, exc.message)
        return render(request, "identification/resolved.html", {
            "res": res, "asset": res.asset, "revoked": res.outcome == "REVOKED", "form": form,
            "can_report": True}, status=400)
