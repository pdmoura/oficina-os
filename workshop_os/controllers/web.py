from odoo.http import request

from odoo.addons.web.controllers.webmanifest import WebManifest


class WorkshopManifest(WebManifest):
    """Installable app named and coloured after the workshop, opening straight on the mechanic app."""

    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        name = request.env.company.sudo()._workshop_app_name()
        manifest.update({
            "name": name,
            "short_name": name[:12],
            "start_url": "/odoo/mechanic-app",
            "background_color": "#0F1115",
            "theme_color": "#0F1115",
            "icons": [
                {"src": "/workshop_os/app-icon/192", "sizes": "192x192", "type": "image/png"},
                {"src": "/workshop_os/app-icon/512", "sizes": "512x512", "type": "image/png"},
            ],
        })
        return manifest
