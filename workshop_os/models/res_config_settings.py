import base64
import hashlib
import io
import logging
import re
import time

import requests
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.image import base64_to_image, image_process

_logger = logging.getLogger(__name__)
PARAM = "workshop_os."


def _hex_color(value, default):
    """Only a #rrggbb colour reaches the CSS, whatever was typed in the setting."""
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value or "") else default


def _text_on(color):
    """Dark or white text, whichever reads better on the given background (WCAG luminance)."""
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return "#111827" if luminance > 0.36 else "#ffffff"


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
    workshop_app_icon = fields.Image("App icon", max_width=512, max_height=512,
                                     help="Square image shown when the app is installed on a phone.")
    workshop_logo_dark = fields.Image("Logo for dark backgrounds", max_width=1024, max_height=1024,
                                      help="Full logo shown on the dark screens: customer page and office dashboard. "
                                           "The company logo stays on documents, login and light screens.")
    workshop_login_background = fields.Char(
        "Login background", default="#0F1115",
        help="Colour behind the login card; the button takes the accent colour.")
    workshop_login_theme = fields.Selection(
        [("light", "Light card"), ("dark", "Dark card")], string="Login card", default="light", required=True,
        help="Dark uses the logo for dark backgrounds; light uses the company logo.")
    workshop_logo_mark = fields.Image("Symbol", max_width=512, max_height=512,
                                      help="The logo without text, for small places: the mechanic app header "
                                           "and the phone icon when no app icon is set.")

    def _workshop_brand(self):
        """Branding the dark screens need, each image falling back to the next best one."""
        self.ensure_one()
        return {
            "name": self.name,
            "accent": self.workshop_accent_color or "#E8B21E",
            "logo_dark": f"/workshop_os/logo/{self.id}/dark" if (self.workshop_logo_dark or self.logo) else False,
            "mark": f"/workshop_os/logo/{self.id}/mark" if (self.workshop_logo_mark or self.workshop_logo_dark or self.logo) else False,
            "has_logo_dark": bool(self.workshop_logo_dark),
            "has_mark": bool(self.workshop_logo_mark or self.workshop_logo_dark),
        }

    def _workshop_login_logo(self):
        """The dark theme shows the logo made for dark backgrounds, when there is one."""
        self.ensure_one()
        if self.workshop_login_theme == "dark" and self.workshop_logo_dark:
            return f"/workshop_os/logo/{self.id}/dark"
        return False

    def _workshop_login_css(self):
        """Login, sign-up and password-reset pages in the shop's colours, light or dark."""
        self.ensure_one()
        background = _hex_color(self.workshop_login_background, "#0F1115")
        accent = _hex_color(self.workshop_accent_color, "#E8B21E")
        on_accent = _text_on(accent)
        card = ".o_database_list"
        rules = [
            f"body.bg-100, #wrapwrap {{ background: radial-gradient(1100px 620px at 50% -12%, "
            f"color-mix(in srgb, {background} 78%, #ffffff), {background} 58%, "
            f"color-mix(in srgb, {background} 70%, #000000)) fixed !important; min-height: 100vh; }}",
            f"{card}.card {{ border-radius: 18px; margin-top: 7vh; max-width: 360px !important; "
            f"box-shadow: 0 28px 70px rgba(0, 0, 0, .38); }}",
            f"{card} .btn-primary {{ background: {accent} !important; border-color: {accent} !important; "
            f"color: {on_accent} !important; font-weight: 700; }}",
            f"{card} .btn-primary:hover, {card} .btn-primary:focus {{ filter: brightness(.94); }}",
            f"{card} .form-control:focus {{ border-color: {accent}; "
            f"box-shadow: 0 0 0 .2rem color-mix(in srgb, {accent} 30%, transparent); }}",
        ]
        if self.workshop_login_theme == "dark":
            rules += [
                f"{card}.card {{ background: #16181d !important; color: #e5e7eb; "
                f"border: 1px solid rgba(255, 255, 255, .07) !important; }}",
                # Odoo paints the card body in translucent white on top of the card.
                f"{card} .card-body {{ background: transparent !important; color: #e5e7eb; }}",
                f"{card} .list-group-item {{ background: #0b0c0f !important; border-color: #2a2d35 !important; "
                f"color: #e5e7eb !important; }}",
                f"{card} .list-group-item-action:hover {{ background: #1c1f26 !important; }}",
                f"{card} .border-top, {card} .border-bottom {{ border-color: rgba(255, 255, 255, .08) !important; }}",
                f"{card} label, {card} .col-form-label {{ color: #d1d5db; font-size: .78rem; font-weight: 700; "
                f"text-transform: uppercase; letter-spacing: .06em; }}",
                f"{card} .form-control {{ background: #0b0c0f; border-color: #2a2d35; color: #f3f4f6; }}",
                f"{card} .form-control::placeholder {{ color: #6b7280; }}",
                f"{card} .form-control:focus {{ background: #0b0c0f; color: #f3f4f6; }}",
                f"{card} .input-group .btn, {card} .btn-secondary, {card} .btn-light, {card} .btn.border "
                f"{{ background: #0b0c0f !important; border-color: #2a2d35 !important; color: #e5e7eb !important; }}",
                f"{card} .btn-primary {{ background: linear-gradient(180deg, {accent}, "
                f"color-mix(in srgb, {accent} 78%, #000000)) !important; }}",
                f"{card} a, {card} .btn-link {{ color: {accent} !important; }}",
                # Odoo's own .card-body .text-muted rule is very specific: the ID inside :is() outweighs it.
                f":is(#wrapwrap, body) {card} .text-muted, :is(#wrapwrap, body) {card} small, "
                f":is(#wrapwrap, body) {card} em {{ color: #9ca3af !important; }}",
            ]
        else:
            rules += [
                f"{card}.card {{ background: #ffffff !important; }}",
                f"{card} a {{ color: color-mix(in srgb, {background} 85%, #000000); }}",
            ]
        return Markup(" ".join(rules))

    def _workshop_app_icon_png(self, size, rounded=True):
        """Phone icon: the uploaded one, or the symbol centred on the app's dark tile."""
        self.ensure_one()
        if self.workshop_app_icon:
            return image_process(base64.b64decode(self.workshop_app_icon), size=(size, size), output_format="PNG")
        if not self.workshop_logo_mark:
            return None
        from PIL import Image, ImageDraw  # noqa: PLC0415
        tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        box = (0, 0, size - 1, size - 1)
        colour, border = (22, 24, 30, 255), (58, 63, 75, 255)
        if rounded:
            ImageDraw.Draw(tile).rounded_rectangle(box, radius=round(size * 0.22), fill=colour, outline=border,
                                                   width=max(1, size // 128))
        else:
            ImageDraw.Draw(tile).rectangle(box, fill=colour)
        mark = base64_to_image(self.workshop_logo_mark).convert("RGBA")
        mark.thumbnail((round(size * 0.74), round(size * 0.74)), Image.LANCZOS)
        tile.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
        output = io.BytesIO()
        tile.save(output, "PNG", optimize=True)
        return output.getvalue()

    @api.model
    def _workshop_brazil_defaults(self):
        """Without demo data a new database is "My Company", in USD, with no time zone: make it a Brazilian shop.

        Runs on install and on every update, so it only fills what is still at Odoo's defaults.
        """
        brazil, brl, usd = self.env.ref("base.br"), self.env.ref("base.BRL"), self.env.ref("base.USD")
        brl.active = True
        booked = self.env["res.company"]
        if "account.move" in self.env:  # a currency with entries behind it must not change
            booked = booked.browse([company.id for company, in self.env["account.move"].sudo()._read_group([], ["company_id"])])
        for company in self.sudo().search([]):
            if not company.country_id:
                company.country_id = brazil
            if company.country_id == brazil and company.currency_id == usd and company not in booked:
                company.currency_id = brl
        # country_id of a company is not searchable: filter in Python.
        companies = self.sudo().search([]).filtered(lambda c: c.country_id == brazil)
        users = self.env["res.users"].sudo().with_context(active_test=False).search(
            [("tz", "=", False), ("company_id", "in", companies.ids)])
        (companies.partner_id.filtered(lambda p: not p.tz) | users.partner_id).write({"tz": "America/Sao_Paulo"})


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    workshop_warranty_text = fields.Text(related="company_id.workshop_warranty_text", readonly=False)
    workshop_terms_text = fields.Text(related="company_id.workshop_terms_text", readonly=False)
    workshop_accent_color = fields.Char(related="company_id.workshop_accent_color", readonly=False)
    workshop_app_icon = fields.Image(related="company_id.workshop_app_icon", readonly=False)
    workshop_logo_dark = fields.Image(related="company_id.workshop_logo_dark", readonly=False)
    workshop_logo_mark = fields.Image(related="company_id.workshop_logo_mark", readonly=False)
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

