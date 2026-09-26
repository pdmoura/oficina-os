import re

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools.image import base64_to_image

from odoo.addons.web.controllers.webmanifest import WebManifest


class WorkshopPublic(http.Controller):

    @http.route("/os/<string:token>", type="http", auth="public", website=False, sitemap=False)
    def order_page(self, token, **kwargs):
        order = request.env["workshop.order"]._get_by_token(token)
        if not order:
            raise request.not_found()
        # The page speaks the customer's language (texts, dates and money), falling back to the workshop's.
        installed = dict(request.env["res.lang"].get_installed())
        lang = next((code for code in (order.partner_id.lang, order.company_id.partner_id.lang) if code in installed), None)
        if lang:
            request.update_context(lang=lang)
            order = order.with_context(lang=lang)
        stages = request.env["workshop.stage"].sudo().search([])
        return request.render("workshop_os.public_order_page", {
            "order": order,
            "company": order.company_id,
            "stages": stages,
            "lines": order.line_ids,
            "photos": order.photo_ids.filtered("show_to_customer"),
            "accent": order.company_id.workshop_accent_color or "#E8B21E",
            "html_lang": (lang or "pt_BR").replace("_", "-"),
        })

    @http.route("/os/<string:token>/decision", type="jsonrpc", auth="public", methods=["POST"], sitemap=False)
    def order_decision(self, token, approve, name, line_ids=None, signature=None):
        order = request.env["workshop.order"]._get_by_token(token)
        if not order:
            raise request.not_found()
        signature_b64 = None
        if signature:
            match = re.match(r"^data:image/png;base64,([A-Za-z0-9+/=]+)$", signature)
            if not match or len(match.group(1)) > 700_000:
                raise UserError("Invalid signature.")
            signature_b64 = match.group(1)
            try:
                base64_to_image(signature_b64)
            except Exception as error:
                raise UserError("Invalid signature.") from error
        ids = [int(i) for i in line_ids] if line_ids is not None else None
        order.customer_decide(bool(approve), name, signature=signature_b64, line_ids=ids)
        return {"state": order.state}


class WorkshopManifest(WebManifest):
    """Installable app named and coloured after the workshop, opening straight on the mechanic app."""

    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        company = request.env.company.sudo()
        name = request.env["ir.config_parameter"].sudo().get_param("web.web_app_name") or company.name or "Oficina"
        manifest.update({
            "name": name,
            "short_name": name[:12],
            "start_url": "/odoo/action-workshop_os.action_mechanic_app",
            "background_color": "#0F1115",
            "theme_color": "#0F1115",
            "icons": [
                {"src": "/workshop_os/static/img/app-icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/workshop_os/static/img/app-icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        })
        return manifest
