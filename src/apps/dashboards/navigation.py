from apps.ui.navigation import NavItem, register

register(NavItem("Dashboards", "dashboards:index", "report.view", "chart", "Insights", 10, "/app/dashboards"))
register(NavItem("My work summary", "dashboards:mine", "work_order.view_assigned", "chart", "Insights", 20,
                 "/app/dashboards/my-work"))
