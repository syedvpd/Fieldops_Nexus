
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.views import View

from apps.ui.mixins import TenantPermissionMixin

from . import selectors


class AuditListView(TenantPermissionMixin, View):
    required_permission = "audit.view"

    def get(self, request):
        qs = selectors.filter_logs(selectors.organization_logs(request.organization), request.GET)
        page = Paginator(qs, 25).get_page(request.GET.get("page"))
        return render(request, "audit/list.html", {"page": page, "filters": request.GET})


class AuditDetailView(TenantPermissionMixin, View):
    required_permission = "audit.view"

    def get(self, request, pk):
        entry = selectors.organization_logs(request.organization).filter(pk=pk).first()
        if entry is None:
            raise Http404
        return render(request, "audit/detail.html", {"entry": entry})
