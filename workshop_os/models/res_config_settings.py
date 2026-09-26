import hashlib
import logging
import time

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
PARAM = "workshop_os."


class ResCompany(models.Model):
    _inherit = "res.company"

    workshop_warranty_text = fields.Text(
        "Warranty text", translate=True,
        default="Serviços com garantia de 90 dias, conforme o Código de Defesa do Consumidor.",
    )
    workshop_terms_text = fields.Text(
        "Approval terms", translate=True,
        help="Shown to the customer on the approval page.",
        default="Ao aprovar, autorizo a execução dos serviços listados e o pagamento conforme combinado.",
    )
    workshop_accent_color = fields.Char("Accent colour", default="#E8B21E",
                                        help="Highlight colour of the mechanic app and the customer pages.")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    workshop_warranty_text = fields.Text(related="company_id.workshop_warranty_text", readonly=False)
    workshop_terms_text = fields.Text(related="company_id.workshop_terms_text", readonly=False)
    workshop_accent_color = fields.Char(related="company_id.workshop_accent_color", readonly=False)
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


class WorkshopOrderPhotoStorage(models.Model):
    _inherit = "workshop.order.photo"

    @api.model
    def _cloudinary_config(self):
        get = self.env["ir.config_parameter"].sudo().get_param
        if get(PARAM + "photo_storage") != "cloudinary":
            return {}
        config = {
            "cloud_name": get(PARAM + "cloudinary_cloud_name"),
            "api_key": get(PARAM + "cloudinary_api_key"),
            "api_secret": get(PARAM + "cloudinary_api_secret"),
            "folder": get(PARAM + "cloudinary_folder") or "oficina",
        }
        return config if all(config.values()) else {}

    @staticmethod
    def _cloudinary_sign(params, secret):
        payload = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] not in (None, ""))
        return hashlib.sha1((payload + secret).encode()).hexdigest()

    @api.model
    def upload_ticket(self):
        """What the app needs to send a photo: a signed Cloudinary upload, or 'database' for direct upload to Odoo.

        The API secret never leaves the server; the browser only gets a short-lived signature.
        """
        config = self._cloudinary_config()
        if not config:
            return {"storage": "database"}
        params = {"folder": config["folder"], "timestamp": int(time.time())}
        return {
            "storage": "cloudinary",
            "url": f"https://api.cloudinary.com/v1_1/{config['cloud_name']}/image/upload",
            "api_key": config["api_key"],
            "signature": self._cloudinary_sign(params, config["api_secret"]),
            **params,
        }

    @api.model
    def add_photo(self, order_id, values):
        """Register a photo taken in the app. values: Cloudinary result (secure_url, public_id) or {data, name}."""
        order = self.env["workshop.order"].browse(order_id)
        order.check_access("write")
        vals = {"order_id": order.id, "kind": values.get("kind") or "entry", "caption": values.get("caption") or False}
        if values.get("secure_url"):
            url = values["secure_url"]
            vals.update(url=url, public_id=values.get("public_id"),
                        thumb_url=url.replace("/upload/", "/upload/c_fill,w_360,h_360,q_auto,f_auto/"))
        elif values.get("data"):
            attachment = self.env["ir.attachment"].create({
                "name": values.get("name") or f"{order.name}.jpg",
                "datas": values["data"],
                "res_model": "workshop.order",
                "res_id": order.id,
                "mimetype": "image/jpeg",
            })
            attachment.generate_access_token()
            vals.update(attachment_id=attachment.id,
                        url=f"/web/image/{attachment.id}?access_token={attachment.access_token}",
                        thumb_url=f"/web/image/{attachment.id}/360x360?access_token={attachment.access_token}")
        else:
            raise UserError(_("No image received."))
        self.create(vals)
        return order.app_read()

    def unlink(self):
        config = self._cloudinary_config()
        for photo in self.filtered("public_id"):
            if not config:
                break
            params = {"public_id": photo.public_id, "timestamp": int(time.time())}
            try:
                requests.post(
                    f"https://api.cloudinary.com/v1_1/{config['cloud_name']}/image/destroy",
                    data={**params, "api_key": config["api_key"],
                          "signature": self._cloudinary_sign(params, config["api_secret"])},
                    timeout=10,
                )
            except requests.RequestException:
                _logger.warning("Could not delete %s from Cloudinary", photo.public_id)
        self.attachment_id.unlink()
        return super().unlink()

