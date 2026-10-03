"""M13 HTML views. Client pages: login -> ACTIVE membership -> portal permission -> enabled portal account ->
ownership-scoped lookup (404) -> service. Staff pages (portal.manage) enable clients and grant assets."""
from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views import View

from apps.core.exceptions import DomainError
from apps.rbac import services as rbac
from apps.sites.views import or404
from apps.tenancy.models import Membership
from apps.ui.mixins import TenantPermissionMixin

from . import selectors, services
from .forms import AccountForm, GrantForm, NewRequestForm, ReasonForm
from .models import PortalAccount


class ClientBase(TenantPermissionMixin, View):
    required_permission = "portal.request.view"

    def account_ok(self, request):
        return selectors.my_account(request.membership) is not None and selectors.my_account(
            request.membership).is_active


def _ctx(request, **extra):
    m = request.membership
    return {"can_create": rbac.has_permission(m, "portal.request.create"),
            "can_confirm": rbac.has_permission(m, "portal.request.confirm"), **extra}


class DashboardView(ClientBase):
    def get(self, request):
        m = request.membership
        recent = list(selectors.my_requests(m).order_by("-created_at")[:5])
        for sr in recent:
            sr.cs = selectors.client_status(sr)
        return render(request, "portal/dashboard.html", _ctx(
            request, nav="home", counts=selectors.counts(m), recent=recent, enabled=self.account_ok(request),
            assets=selectors.granted_assets(m).count()))


class RequestListView(ClientBase):
    def get(self, request):
        qs = selectors.filter_requests(selectors.my_requests(request.membership), request.GET)
        page = Paginator(qs, 10).get_page(request.GET.get("page"))
        for sr in page:
            sr.cs = selectors.client_status(sr)
        return render(request, "portal/requests.html", _ctx(request, nav="requests", page=page, filters=request.GET))


class NewRequestView(ClientBase):
    required_permission = "portal.request.create"

    def _form(self, request, data=None):
        return NewRequestForm(data, assets=selectors.granted_assets(request.membership),
                              initial={"asset": request.GET.get("asset")} if data is None else None)

    def get(self, request):
        return render(request, "portal/new.html", _ctx(request, nav="new", form=self._form(request),
                                                       enabled=self.account_ok(request)))

    def post(self, request):
        form = self._form(request, request.POST)
        if form.is_valid():
            try:
                sr = services.submit_request(request.membership, uploads=request.FILES.getlist("files"),
                                             request=request, **form.cleaned_data)
                messages.success(request, f"Request {sr.number} submitted. We will keep you updated here.")
                return redirect("portal:request", pk=sr.pk)
            except DomainError as exc:
                form.add_error(None, exc.message)
        return render(request, "portal/new.html", _ctx(request, form=form, enabled=self.account_ok(request)),
                      status=400)


class RequestDetailView(ClientBase):
    def get(self, request, pk, status=200, reopen_form=None):
        m = request.membership
        sr = or404(selectors.get_my_request, m, pk)
        sr.cs = selectors.client_status(sr)
        return render(request, "portal/detail.html", _ctx(
            request, sr=sr, visit=selectors.visit_for(sr), timeline=selectors.timeline(sr),
            files=selectors.my_attachments(m, sr), steps=selectors.STEPS,
            reopen_form=reopen_form or ReasonForm(),
            can_attach=sr.status not in ("CONFIRMED", "CLOSED", "REJECTED") and rbac.has_permission(
                m, "portal.request.create")), status=status)


class RequestActionView(ClientBase):
    http_method_names = ["post"]

    def post(self, request, pk, action):
        m = request.membership
        sr = or404(selectors.get_my_request, m, pk)
        try:
            if action == "confirm":
                services.confirm(m, sr, request=request)
                messages.success(request, "Thank you: the resolution is confirmed.")
            elif action == "reopen":
                form = ReasonForm(request.POST)
                if not form.is_valid():
                    return self._redisplay(request, pk, form)
                services.reopen(m, sr, reason=form.cleaned_data["reason"], request=request)
                messages.success(request, "We have reopened your request.")
            elif action == "attach":
                files = request.FILES.getlist("files")
                if not files:
                    raise DomainError("Choose a file to upload.")
                for up in files[: services.MAX_FILES]:
                    services.add_attachment(m, sr, up, request=request)
                messages.success(request, "File added to your request.")
            else:
                messages.error(request, "Unknown action.")
        except DomainError as exc:
            messages.error(request, exc.message)
        return redirect("portal:request", pk=pk)

    def _redisplay(self, request, pk, form):
        view = RequestDetailView()
        view.setup(request)
        return view.get(request, pk, status=400, reopen_form=form)


# --- staff: portal clients -------------------------------------------------------------------------------------------


class AccountsView(TenantPermissionMixin, View):
    required_permission = "portal.manage"

    def _eligible(self, org):
        out = []
        have = set(PortalAccount.objects.for_organization(org).values_list("membership_id", flat=True))
        for m in Membership.objects.for_organization(org).filter(status=Membership.Status.ACTIVE).select_related(
                "user"):
            if m.pk not in have and services._is_client_only(m):
                out.append(m)
        return out

    def get(self, request, form=None, status=200):
        org = request.organization
        accounts = list(PortalAccount.objects.for_organization(org).select_related("membership__user").annotate(
            n_assets=Count("grants")))
        return render(request, "portal/accounts.html", {
            "accounts": accounts, "form": form or AccountForm(members=self._eligible(org))}, status=status)

    def post(self, request):
        org = request.organization
        form = AccountForm(request.POST, members=self._eligible(org))
        if form.is_valid():
            try:
                m = Membership.objects.for_organization(org).get(pk=form.cleaned_data["membership"])
                services.enable_account(org, m, company=form.cleaned_data["company"], actor=request.user,
                                        request=request)
                messages.success(request, "Portal client enabled. Now grant the assets they may report on.")
                return redirect("portal:accounts")
            except (DomainError, Membership.DoesNotExist) as exc:
                form.add_error(None, getattr(exc, "message", "Choose an active client user."))
        return self.get(request, form, 400)


class AccountDetailView(TenantPermissionMixin, View):
    required_permission = "portal.manage"

    def _acct(self, request, pk):
        return or404(_get_account, request.organization, pk)

    def get(self, request, pk, form=None, status=200):
        from apps.assets.models import Asset

        acct = self._acct(request, pk)
        org = request.organization
        granted_ids = [g.asset_id for g in acct.grants.all()]
        assets = Asset.objects.for_organization(org).exclude(pk__in=granted_ids).exclude(
            status__in=("RETIRED", "DISPOSED")).select_related("site").order_by("asset_tag")
        return render(request, "portal/account.html", {
            "acct": acct, "grants": acct.grants.select_related("asset__site").order_by("asset__asset_tag"),
            "form": form or GrantForm(assets=assets)}, status=status)

    def post(self, request, pk):
        from apps.assets.models import Asset

        acct = self._acct(request, pk)
        org = request.organization
        action = request.POST.get("action")
        try:
            if action in ("enable", "disable"):
                services.set_account_active(acct, action == "enable", actor=request.user, request=request)
                messages.success(request, "Portal access updated.")
            elif action in ("grant", "revoke"):
                asset = Asset.objects.for_organization(org).filter(pk=request.POST.get("asset") or None).first() \
                    if _is_uuid(request.POST.get("asset")) else None
                if asset is None:
                    raise DomainError("Choose an asset.")
                if action == "grant":
                    services.grant_asset(acct, asset, actor=request.user, request=request)
                else:
                    services.revoke_asset(acct, asset, actor=request.user, request=request)
                messages.success(request, "Asset access updated.")
            else:
                messages.error(request, "Unknown action.")
        except DomainError as exc:
            messages.error(request, exc.message)
        return redirect("portal:account", pk=acct.pk)


def _is_uuid(value) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _get_account(org, pk):
    from apps.sites.selectors import scoped_get

    return scoped_get(PortalAccount.objects.for_organization(org).select_related("membership__user"), pk,
                      "Portal client")
