from apps.ui.navigation import NavItem, register

register(NavItem("Scan asset label", "identification:scan", "asset.view", "qr-code", "Assets", 40,
                 "/app/identification/scan"))
