from apps.ui.navigation import NavItem, register

register(NavItem("My Jobs", "workspace:jobs", "work_order.view_assigned", "wrench", "Operations", 5, "/app/workspace"))
