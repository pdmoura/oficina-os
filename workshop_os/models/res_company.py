import base64
import io
import re

from markupsafe import Markup
from PIL import Image

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.image import base64_to_image, image_process

# Attachment the backend asset bundles read the brand colours from (see data/ir_asset_data.xml).
BACKEND_THEME_URL = "/_custom/workshop_os/brand_variables.scss"


def _hex_color(value, default):
    """Only a #rrggbb colour reaches the CSS, whatever was typed in the setting."""
    return value if re.fullmatch(r"#[0-9a-fA-F]{6}", value or "") else default


def _luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(one, other):
    """WCAG contrast ratio between two #rrggbb colours (1 to 21)."""
    light, dark = sorted((_luminance(one), _luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _mix(color, other, weight):
    """`weight` of `color` blended with the rest of `other`, as #rrggbb."""
    channels = (round(int(color[i:i + 2], 16) * weight + int(other[i:i + 2], 16) * (1 - weight)) for i in (1, 3, 5))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _text_on(color):
    """Dark or white text, whichever reads better on the given background (WCAG luminance)."""
    return "#111827" if _luminance(color) > 0.36 else "#ffffff"


def _readable_on_white(color):
    """The colour, darkened just enough to be read as text on white (WCAG AA, 4.5:1)."""
    for step in range(0, 101, 2):
        candidate = _mix(color, "#000000", 1 - step / 100)
        if _contrast(candidate, "#ffffff") >= 4.5:
            return candidate
    return "#000000"


class ResCompany(models.Model):
    _inherit = "res.company"

    workshop_warranty_text = fields.Text(
        "Warranty text", translate=True, default=lambda self: self._workshop_default_warranty_text())
    workshop_terms_text = fields.Text(
        "Approval terms", translate=True, help="Shown to the customer on the approval page.",
        default=lambda self: self._workshop_default_terms_text())
    workshop_accent_color = fields.Char("Accent colour", default="#E8B21E",
                                        help="Buttons and highlights across the system, the mechanic app and the "
                                             "customer pages.")
    workshop_app_icon = fields.Image("App icon", max_width=512, max_height=512,
                                     help="Square image shown when the app is installed on a phone.")
    workshop_logo_dark = fields.Image("Logo for dark backgrounds", max_width=1024, max_height=1024,
                                      help="Full logo shown on the dark screens: customer page and office dashboard. "
                                           "The company logo stays on documents, login and light screens.")
    workshop_login_background = fields.Char(
        "Background colour", default="#0F1115",
        help="The system's top bar and the page behind the login card.")
    workshop_login_theme = fields.Selection(
        [("light", "Light card"), ("dark", "Dark card")], string="Login card", default="light", required=True,
        help="Dark uses the logo for dark backgrounds; light uses the company logo.")
    workshop_logo_mark = fields.Image("Symbol", max_width=512, max_height=512,
                                      help="The logo without text, for small places: the mechanic app header "
                                           "and the phone icon when no app icon is set.")
    workshop_logo_mark_light = fields.Image(
        "Symbol for light backgrounds", max_width=512, max_height=512,
        help="The symbol shown in the light theme of the mechanic app and the dashboard.")
    workshop_favicon = fields.Binary(
        "Browser icon", attachment=True,
        help="Icon of the browser tab and of phone shortcuts, as .ico or .png. An .ico may hold several sizes: "
             "each one is used as it is wherever that size is asked for.")
    workshop_og_image = fields.Image(
        "Link preview image", max_width=1200, max_height=1200,
        help="Shown when a link to the system or to a work order is shared (WhatsApp, e-mail...). 1200×630 fits best.")

    @api.constrains("workshop_favicon")
    def _check_workshop_favicon(self):
        for company in self.filtered("workshop_favicon"):
            try:
                image_format = Image.open(io.BytesIO(base64.b64decode(company.workshop_favicon))).format
            except (OSError, ValueError, Image.DecompressionBombError):
                image_format = None
            if image_format not in ("ICO", "PNG"):
                raise ValidationError(self.env._("The browser icon must be an .ico or .png image."))

    def write(self, vals):
        result = super().write(vals)
        if {"workshop_accent_color", "workshop_login_background"} & vals.keys():
            self.env["res.company"]._workshop_apply_backend_theme()
        return result

    def _workshop_app_name(self):
        """Name of the installed app and of the browser tab: the configured web app name, or the company's."""
        self.ensure_one()
        return self.env["ir.config_parameter"].sudo().get_param("web.web_app_name") or self.name or "Oficina"

    def _workshop_icon_version(self):
        """Changes whenever the company is saved, so browsers fetch the icons again after a new upload."""
        self.ensure_one()
        return int(self.write_date.timestamp()) if self.write_date else 0

    def _workshop_favicon_url(self):
        """Tab icon: the shop's own browser icon, or the app icon made from its symbol."""
        self.ensure_one()
        if self.workshop_favicon:
            return f"/workshop_os/favicon.ico?v={self._workshop_icon_version()}"
        return "/workshop_os/app-icon/64"

    def _workshop_favicon_png(self, size):
        """The browser icon as a PNG of `size`: the .ico's own frame of that size when it has one, else resized."""
        self.ensure_one()
        if not self.workshop_favicon:
            return None
        image = Image.open(io.BytesIO(base64.b64decode(self.workshop_favicon)))
        if image.format == "ICO":
            sizes = image.ico.sizes()
            image = image.ico.getimage((size, size) if (size, size) in sizes else max(sizes))
        image = image.convert("RGBA")
        if image.size != (size, size):
            image = image.resize((size, size), Image.LANCZOS)
        output = io.BytesIO()
        image.save(output, "PNG", optimize=True)
        return output.getvalue()

    def _workshop_favicon_ico(self):
        """The browser icon as an .ico: the uploaded file itself, or the uploaded PNG in the usual tab sizes."""
        self.ensure_one()
        data = base64.b64decode(self.workshop_favicon)
        image = Image.open(io.BytesIO(data))
        if image.format == "ICO":
            return data
        output = io.BytesIO()
        image.convert("RGBA").save(output, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])
        return output.getvalue()

    def _workshop_share_meta(self, title=None, description=None):
        """What a shared link shows (WhatsApp, e-mail...), in the workshop's own language."""
        self.ensure_one()
        company = self.with_context(lang=self.partner_id.lang or self.env.lang)
        return {
            "site_name": self.name,
            "title": title or company.env._("%s | Work order system", self.name),
            "description": description or company.env._("Professional work order system of %s.", self.name),
            "locale": company.env.lang or "en_US",
            "image": self.workshop_og_image and (
                f"{self.get_base_url()}/workshop_os/og-image/{self.id}?v={self._workshop_icon_version()}"),
        }

    def _workshop_brand(self):
        """Branding the app screens need, each image falling back to the next best one."""
        self.ensure_one()
        accent = _hex_color(self.workshop_accent_color, "#E8B21E")
        any_logo = self.workshop_logo_dark or self.logo
        return {
            "name": self.name,
            "accent": accent,
            "accent_ink": _text_on(accent),
            # In the light theme the accent also colours text on white: darkened until it reads.
            "accent_text": _readable_on_white(accent),
            "logo_dark": f"/workshop_os/logo/{self.id}/dark" if any_logo else False,
            "logo_light": f"/workshop_os/logo/{self.id}/light" if any_logo else False,
            "mark": f"/workshop_os/logo/{self.id}/mark" if (self.workshop_logo_mark or any_logo) else False,
            "mark_light": f"/workshop_os/logo/{self.id}/mark_light" if (
                self.workshop_logo_mark_light or self.workshop_logo_mark or any_logo) else False,
            "has_logo_dark": bool(self.workshop_logo_dark),
            "has_logo_light": bool(self.logo),
            "has_mark": bool(self.workshop_logo_mark or self.workshop_logo_dark),
            "has_mark_light": bool(self.workshop_logo_mark_light or self.workshop_logo_mark),
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

    def _workshop_theme_scss(self):
        """Odoo's own SCSS variables in the shop's colours: buttons, tabs, filters, checkboxes and the top bar.

        Filled surfaces take the accent as it is, with dark or white text on top. Text and thin lines on white
        take the accent darkened until it reads (WCAG AA), so a yellow brand never turns into yellow text.
        """
        self.ensure_one()
        accent = _hex_color(self.workshop_accent_color, "#E8B21E")
        bar = _hex_color(self.workshop_login_background, "#0F1115")
        on_accent, on_bar, readable = _text_on(accent), _text_on(bar), _readable_on_white(accent)
        hover = _mix(accent, "#000000", 0.88)
        return "\n".join([
            "// Generated from Settings > Workshop > Brand; saving those settings rewrites it.",
            f"$o-community-color: {accent};",
            f"$o-enterprise-color: {accent};",
            f"$o-brand-odoo: {accent};",
            f"$o-brand-primary: {accent};",
            f"$o-action: {readable};",
            f"$o-main-link-color: {readable};",
            f"$primary: {readable};",
            f"$form-check-input-checked-bg-color: {readable};",
            f"$o-navbar-background: {bar};",
            f"$o-navbar-border-bottom: 1px solid {_mix(bar, on_bar, 0.9)};",
            f"$o-navbar-entry-color: rgba({on_bar}, .86);",
            f"$o-navbar-entry-color--hover: {on_bar};",
            f"$o-navbar-entry-bg--hover: rgba({on_bar}, .08);",
            '$o-btns-bs-override: ("primary": (',
            f"    background: {accent}, border: {accent}, color: {on_accent},",
            f"    hover-background: {hover}, hover-border: {hover}, hover-color: {on_accent},",
            f"    active-background: {_mix(accent, '#ffffff', 0.14)}, active-border: {readable}, active-color: {readable},",
            "));",
            "",
        ])

    @api.model
    def _workshop_apply_backend_theme(self):
        """Store the brand variables where the asset bundles read them; the bundles rebuild only when they change.

        One set of assets serves the whole database, so the main company's colours paint it.
        """
        company = self.env.ref("base.main_company", raise_if_not_found=False) or self.sudo().search([], limit=1)
        raw = company.sudo()._workshop_theme_scss().encode()
        attachments = self.env["ir.attachment"].sudo()
        theme = attachments.search([("url", "=", BACKEND_THEME_URL), ("type", "=", "binary")], limit=1)
        if theme.raw == raw:
            return
        if theme:
            theme.raw = raw
        else:
            attachments.create({"name": "brand_variables.scss", "url": BACKEND_THEME_URL, "type": "binary",
                                "mimetype": "text/scss", "raw": raw})
        self.env.registry.clear_cache("assets")

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
        # The default texts are written in English when the column is created: add every installed language's
        # translation while the text is still the untouched default.
        languages = [code for code, _name in self.env["res.lang"].get_installed() if code != "en_US"]
        for field_name, default in (("workshop_warranty_text", "_workshop_default_warranty_text"),
                                    ("workshop_terms_text", "_workshop_default_terms_text")):
            english = getattr(self.with_context(lang="en_US"), default)()
            for company in self.sudo().with_context(lang="en_US").search([]):
                if company[field_name] == english:
                    company.update_field_translations(field_name, {
                        lang: getattr(company.with_context(lang=lang), default)() for lang in languages
                        if company.with_context(lang=lang)[field_name] == english
                    })

    def _workshop_default_warranty_text(self):
        return self.env._("Services under a 90-day warranty, as set by the Brazilian Consumer Protection Code.")

    def _workshop_default_terms_text(self):
        return self.env._("By approving, I authorise the listed services and their payment as agreed.")
