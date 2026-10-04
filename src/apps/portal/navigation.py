from apps.ui.navigation import NavItem, register

register(NavItem("Portal clients", "portal:accounts", "portal.manage", "users", "Service", 50,
                 "/app/portal/accounts"))
