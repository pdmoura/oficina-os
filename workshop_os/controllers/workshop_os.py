import re

from PIL import Image

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools.image import base64_to_image

from odoo.addons.workshop_os.models.res_company import _hex_color


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
            "accent": _hex_color(order.company_id.workshop_accent_color, "#E8B21E"),
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
                raise UserError(request.env._("Invalid signature."))
            signature_b64 = match.group(1)
            try:
                base64_to_image(signature_b64)
            except (UserError, ValueError, Image.DecompressionBombError) as error:
                raise UserError(request.env._("Invalid signature.")) from error
        ids = [int(i) for i in line_ids] if line_ids is not None else None
        order._customer_decide(bool(approve), name, signature=signature_b64, line_ids=ids)
        return {"state": order.state}


class WorkshopBrand(http.Controller):

    @http.route("/workshop_os/app-icon/<int:size>", type="http", auth="public", sitemap=False, readonly=True)
    def app_icon(self, size):
        """The company's own icon when it set one, the product icon otherwise."""
        size = min(max(size, 32), 512)
        # iOS rounds the corners itself and paints transparent ones black: give it a full square.
        png = request.env.company.sudo()._workshop_app_icon_png(size, rounded=size != 180)
        if png:
            return request.make_response(png, [("Content-Type", "image/png"), ("Cache-Control", "public, max-age=3600")])
        return request.redirect(f"/workshop_os/static/img/app_icon_{512 if size > 192 else 192}.png")

    @http.route("/workshop_os/favicon.ico", type="http", auth="public", sitemap=False, readonly=True)
    def favicon(self, **kwargs):
        """The workshop's own browser icon; without one, the app icon made from its symbol."""
        company = request.env.company.sudo()
        if not company.workshop_favicon:
            return request.redirect("/workshop_os/app-icon/64")
        return request.make_response(company._workshop_favicon_ico(),
                                     [("Content-Type", "image/x-icon"), ("Cache-Control", "public, max-age=86400")])

    @http.route("/workshop_os/icon/<int:size>", type="http", auth="public", sitemap=False, readonly=True)
    def browser_icon(self, size, **kwargs):
        """PNG sizes of the browser icon (tab and phone shortcuts)."""
        size = min(max(size, 16), 256)
        png = request.env.company.sudo()._workshop_favicon_png(size)
        if png is None:
            return request.redirect(f"/workshop_os/app-icon/{size}")
        return request.make_response(png, [("Content-Type", "image/png"), ("Cache-Control", "public, max-age=86400")])

    @http.route("/workshop_os/og-image/<int:company_id>", type="http", auth="public", sitemap=False, readonly=True)
    def og_image(self, company_id, **kwargs):
        """Picture of shared links: public, because link previews are fetched without a session."""
        company = request.env["res.company"].sudo().browse(company_id).exists()
        if not company.workshop_og_image:
            raise request.not_found()
        stream = request.env["ir.binary"]._get_image_stream_from(company, "workshop_og_image")
        return stream.get_response(max_age=86400)

    @http.route("/workshop_os/logo/<int:company_id>/<string:variant>", type="http", auth="public",
                sitemap=False, readonly=True)
    def company_logo(self, company_id, variant, **kwargs):
        """Public logos of the app screens, each variant falling back to the next best image.

        "dark"/"light": the full logo for a dark or light background; "mark"/"mark_light": the symbol.
        """
        company = request.env["res.company"].sudo().browse(company_id).exists()
        fallbacks = {
            "dark": ["workshop_logo_dark", "logo"],
            "light": ["logo", "workshop_logo_dark"],
            "mark": ["workshop_logo_mark", "workshop_logo_dark", "logo"],
            "mark_light": ["workshop_logo_mark_light", "workshop_logo_mark", "logo", "workshop_logo_dark"],
        }
        if not company or variant not in fallbacks:
            raise request.not_found()
        field = next((f for f in fallbacks[variant] if company[f]), None)
        if not field:
            raise request.not_found()
        size = 256 if variant.startswith("mark") else 640
        stream = request.env["ir.binary"]._get_image_stream_from(company, field, width=size, height=size)
        return stream.get_response(max_age=3600)
