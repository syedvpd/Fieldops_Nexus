from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = "apps.portal"
    label = "portal"

    def ready(self):
        from apps.files import access
        from apps.rbac import services as rbac

        def can_read_request_file(membership, request_obj, attachment=None) -> bool:
            # staff: follows the request's site scope (unchanged M05 rule)
            if rbac.has_permission(membership, "incident.view", request_obj.site_id):
                return True
            # portal client: only evidence THEY uploaded to THEIR OWN request
            return bool(
                attachment is not None
                and rbac.has_permission(membership, "portal.request.view")
                and request_obj.reported_by_id == membership.pk
                and attachment.uploaded_by_id == membership.user_id)

        access.register("incidents.servicerequest", can_read_request_file)  # supersedes the M05 registration
