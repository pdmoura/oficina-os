from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        if self.env.user._is_internal():
            # Browser tabs read "<page> - <shop>" instead of Odoo's name.
            info["workshop_app_name"] = self.env.company.sudo()._workshop_app_name()
        return info
