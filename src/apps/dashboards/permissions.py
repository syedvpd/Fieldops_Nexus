"""M14 permissions. ``report.view`` unlocks the manager dashboards (role templates already list it); each section
additionally needs the view permission of the data it summarises (for example ``inventory.view``), and the
visible sites are the INTERSECTION of both scopes. Technicians use the "My work" view, which needs only
``work_order.view_assigned`` and shows nothing but their own jobs."""
from apps.rbac.catalog import register

register("dashboards", "report.view", "View operational dashboards and KPIs", site_scoped=True)
