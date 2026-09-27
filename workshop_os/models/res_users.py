from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _on_webclient_bootstrap(self):
        # OdooBot's onboarding chat opens over the screen on the first login (all of it on a phone); a workshop
        # has no use for it, so it is switched off before OdooBot gets to start it.
        if self.odoobot_state != "disabled":
            self.sudo().odoobot_state = "disabled"
        return super()._on_webclient_bootstrap()
