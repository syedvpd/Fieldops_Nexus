"""M13 permissions. Client permissions are organization-wide on purpose: what a client may touch is decided by the
ownership rule (own requests) and explicit asset grants, never by site roles."""
from apps.rbac.catalog import register

register("portal", "portal.request.create", "Submit service requests in the client portal")
register("portal", "portal.request.view", "View own requests and their permitted progress in the client portal")
register("portal", "portal.request.confirm", "Confirm (or reject) the resolution of own requests")
register("portal", "portal.manage", "Enable portal clients and grant them assets")
