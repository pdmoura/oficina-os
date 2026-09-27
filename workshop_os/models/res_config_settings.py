import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

PARAM = "workshop_os."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    workshop_warranty_text = fields.Text(related="company_id.workshop_warranty_text", readonly=False)
    workshop_terms_text = fields.Text(related="company_id.workshop_terms_text", readonly=False)
    workshop_accent_color = fields.Char(related="company_id.workshop_accent_color", readonly=False)
    workshop_app_icon = fields.Image(related="company_id.workshop_app_icon", readonly=False)
    workshop_logo_dark = fields.Image(related="company_id.workshop_logo_dark", readonly=False)
    workshop_logo_mark = fields.Image(related="company_id.workshop_logo_mark", readonly=False)
    workshop_logo_mark_light = fields.Image(related="company_id.workshop_logo_mark_light", readonly=False)
    workshop_login_background = fields.Char(related="company_id.workshop_login_background", readonly=False)
    workshop_login_theme = fields.Selection(related="company_id.workshop_login_theme", readonly=False)
    workshop_photo_storage = fields.Selection(
        [("database", "Database"), ("cloudinary", "Cloudinary")],
        string="Photo storage", config_parameter=PARAM + "photo_storage", default="database",
    )
    workshop_cloudinary_cloud_name = fields.Char("Cloud name", config_parameter=PARAM + "cloudinary_cloud_name")
    workshop_cloudinary_api_key = fields.Char("API key", config_parameter=PARAM + "cloudinary_api_key")
    workshop_cloudinary_api_secret = fields.Char("API secret", config_parameter=PARAM + "cloudinary_api_secret")
    workshop_cloudinary_folder = fields.Char("Folder", config_parameter=PARAM + "cloudinary_folder", default="oficina")

    def action_workshop_test_cloudinary(self):
        self.execute()
        config = self.env["workshop.order.photo"]._cloudinary_config()
        if not config:
            raise UserError(_("Fill in cloud name, API key and API secret first."))
        try:
            response = requests.get(
                f"https://api.cloudinary.com/v1_1/{config['cloud_name']}/usage",
                auth=(config["api_key"], config["api_secret"]), timeout=10,
            )
        except requests.RequestException as error:
            raise UserError(_("Could not reach Cloudinary: %s", error)) from error
        if response.status_code != 200:
            raise UserError(_("Cloudinary refused the credentials (HTTP %s).", response.status_code))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"type": "success", "message": _("Cloudinary connected.")}}
