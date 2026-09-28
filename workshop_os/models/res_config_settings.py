import time

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

PARAM = "workshop_os."
CLOUDINARY_FIELDS = ("workshop_cloudinary_cloud_name", "workshop_cloudinary_api_key",
                     "workshop_cloudinary_api_secret", "workshop_cloudinary_folder")
# 1x1 transparent PNG sent by the connection test.
TEST_PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    workshop_warranty_text = fields.Text(related="company_id.workshop_warranty_text", readonly=False)
    workshop_terms_text = fields.Text(related="company_id.workshop_terms_text", readonly=False)
    workshop_accent_color = fields.Char(related="company_id.workshop_accent_color", readonly=False)
    workshop_app_icon = fields.Image(related="company_id.workshop_app_icon", readonly=False)
    workshop_logo_dark = fields.Image(related="company_id.workshop_logo_dark", readonly=False)
    workshop_logo_mark = fields.Image(related="company_id.workshop_logo_mark", readonly=False)
    workshop_logo_mark_light = fields.Image(related="company_id.workshop_logo_mark_light", readonly=False)
    workshop_favicon = fields.Binary(related="company_id.workshop_favicon", readonly=False)
    workshop_og_image = fields.Image(related="company_id.workshop_og_image", readonly=False)
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

    @api.constrains("workshop_photo_storage", "workshop_cloudinary_api_key")
    def _check_workshop_cloudinary_api_key(self):
        for settings in self.filtered(lambda s: s.workshop_photo_storage == "cloudinary" and s.workshop_cloudinary_api_key):
            if not settings.workshop_cloudinary_api_key.strip().isdigit():
                raise ValidationError(_(
                    "The Cloudinary API key is the number in the “API Key” column (e.g. 123456789012345), "
                    "not the key's name."))

    def set_values(self):
        # Pasted values often carry spaces or line breaks; the folder has no slashes at either end.
        for settings in self:
            for name in CLOUDINARY_FIELDS:
                value = settings[name] and settings[name].strip()
                if name == "workshop_cloudinary_folder":
                    value = value and value.strip("/")
                if value != settings[name]:
                    settings[name] = value
        super().set_values()

    def action_workshop_test_cloudinary(self):
        """Checks the keys, then sends a 1-pixel photo the way the app does (signed, into the folder) and deletes it."""
        self.execute()
        Photo = self.env["workshop.order.photo"]
        config = Photo._cloudinary_config()
        if not config:
            raise UserError(_("Fill in cloud name, API key and API secret first."))
        api_url = f"https://api.cloudinary.com/v1_1/{config['cloud_name']}"
        self._workshop_cloudinary_call("get", f"{api_url}/usage", auth=(config["api_key"], config["api_secret"]))
        params = {"folder": config["folder"], "public_id": "connection-test", "timestamp": int(time.time())}
        photo = self._workshop_cloudinary_call("post", f"{api_url}/image/upload", data={
            **params, "file": TEST_PIXEL, "api_key": config["api_key"],
            "signature": Photo._cloudinary_sign(params, config["api_secret"]),
        })
        params = {"public_id": photo["public_id"], "timestamp": int(time.time())}
        self._workshop_cloudinary_call("post", f"{api_url}/image/destroy", data={
            **params, "api_key": config["api_key"], "signature": Photo._cloudinary_sign(params, config["api_secret"]),
        })
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "type": "success",
            "message": _("Cloudinary connected: a test photo went into the “%s” folder and was deleted.", config["folder"]),
        }}

    def _workshop_cloudinary_call(self, method, url, **kwargs):
        try:
            response = requests.request(method, url, timeout=15, **kwargs)
        except requests.RequestException as error:
            raise UserError(_("Could not reach Cloudinary: %s", error)) from error
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.ok and "error" not in body:
            return body
        reason = (body.get("error") or {}).get("message") or str(response.status_code)
        if "api_key" in reason:
            hint = _("The API key was not found: use the number in the “API Key” column, not the key's name.")
        elif "api_secret" in reason or "Signature" in reason:
            hint = _("The API secret does not match the API key: show it with the eye icon and copy it whole.")
        elif "cloud_name" in reason:
            hint = _("The cloud name does not match these keys: copy it from the top of the API Keys page.")
        else:
            hint = _("Check the values on Cloudinary's API Keys page.")
        raise UserError(_("Cloudinary refused the request (%(reason)s). %(hint)s", reason=reason, hint=hint))
