"""M12 permissions (role templates already grant ``qr.*`` to asset managers, ``*.view`` to operations / auditors).
Scanning needs no permission of its own: after resolution the caller must be able to see the asset (``asset.view``
with site scope), which is the authorization decision."""
from apps.rbac.catalog import register

register("identification", "qr.view", "View, print and download asset QR / barcode labels", site_scoped=True)
register("identification", "qr.generate", "Generate, replace and revoke asset QR / barcode labels",
         site_scoped=True)
