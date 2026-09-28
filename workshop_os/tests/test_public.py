import base64
import io
import json

from PIL import Image

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPublicPage(HttpCase):

    def setUp(self):
        super().setUp()
        fleet = self.env["res.partner"].create({"name": "Public Fleet", "is_company": True})
        vehicle = self.env["workshop.vehicle"].create({"plate": "PUB1C23", "partner_id": fleet.id, "model": "FH 540"})
        service = self.env["workshop.service"].create({"name": "Harness repair", "list_price": 220})
        self.order = self.env["workshop.order"].create({
            "partner_id": fleet.id, "vehicle_id": vehicle.id,
            "line_ids": [Command.create(self.env["workshop.order.line"]._vals_from_service(service))],
        })

    def test_page_and_decision(self):
        response = self.url_open(f"/os/{self.order.access_token}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("PUB1C23", response.text)
        self.assertIn('<html lang="en-US">', response.text, "a BCP 47 tag, or Intl.NumberFormat throws in the page")
        self.assertIn("Harness repair", response.text)

        self.assertEqual(self.url_open("/os/not-a-real-token-at-all").status_code, 404)

        payload = {"jsonrpc": "2.0", "method": "call", "params": {
            "approve": True, "name": "Fleet manager", "line_ids": self.order.line_ids.ids, "signature": None}}
        response = self.url_open(f"/os/{self.order.access_token}/decision", data=json.dumps(payload),
                                 headers={"Content-Type": "application/json"})
        self.assertEqual(response.json()["result"], {"state": "approved"})
        self.assertEqual(self.order.approved_by, "Fleet manager")

    def test_bad_signature_is_refused(self):
        payload = {"jsonrpc": "2.0", "method": "call", "params": {
            "approve": True, "name": "X", "signature": "data:text/html;base64,PHNjcmlwdD4="}}
        response = self.url_open(f"/os/{self.order.access_token}/decision", data=json.dumps(payload),
                                 headers={"Content-Type": "application/json"})
        self.assertIn("error", response.json())
        self.assertEqual(self.order.state, "draft")

    def test_installed_app_opens_each_role_on_its_screen(self):
        # Odoo's home routes by role (see test_login_opens_the_workshop_by_role): mechanic app or dashboard.
        manifest = self.url_open("/web/manifest.webmanifest").json()
        self.assertEqual(manifest["start_url"], "/odoo")
        self.assertEqual(manifest["icons"][0]["src"], "/workshop_os/app-icon/192")

    def test_company_logo_is_public(self):
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        company = self.env.company
        company.write({"logo": pixel, "workshop_logo_dark": False})
        light = self.url_open(f"/workshop_os/logo/{company.id}/dark")
        self.assertEqual(light.status_code, 200, "falls back to the company logo, without a session")
        company.workshop_logo_dark = pixel
        self.assertEqual(self.url_open(f"/workshop_os/logo/{company.id}/dark").status_code, 200)
        self.assertEqual(self.url_open("/workshop_os/logo/999999/dark").status_code, 404)
        for variant in ("light", "mark", "mark_light"):
            self.assertEqual(self.url_open(f"/workshop_os/logo/{company.id}/{variant}").status_code, 200, variant)
        self.assertEqual(self.url_open(f"/workshop_os/logo/{company.id}/other").status_code, 404)

    def test_light_theme_has_its_own_symbol(self):
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        company = self.env.company
        company.write({"workshop_logo_mark": pixel, "workshop_logo_mark_light": False, "workshop_accent_color": "#E8B21E"})
        brand = company._workshop_brand()
        self.assertEqual(brand["mark_light"], f"/workshop_os/logo/{company.id}/mark_light")
        self.assertTrue(brand["has_mark_light"], "falls back to the dark-theme symbol")
        self.assertEqual(brand["accent_ink"], "#111827", "dark text on a gold accent")
        self.assertNotEqual(brand["accent_text"].lower(), "#e8b21e", "text in the light theme uses a darker gold")

    def test_browser_tab_shows_the_shop(self):
        self.env["ir.config_parameter"].sudo().set_param("web.web_app_name", "SV Test")
        page = self.url_open("/web/login").text
        self.assertIn("<title>SV Test</title>", page)
        self.assertIn('href="/workshop_os/app-icon/64"', page, "the shop's icon, not Odoo's favicon")
        self.authenticate("admin", "admin")
        info = self.make_jsonrpc_request("/web/session/get_session_info", {})
        self.assertEqual(info["workshop_app_name"], "SV Test", "the web client puts it after the page name")

    def test_browser_icon_keeps_each_size_as_drawn(self):
        # An .ico with a 16px and a 57px frame of different colours: each size is served from its own frame.
        small, large = Image.new("RGBA", (16, 16), (255, 0, 0, 255)), Image.new("RGBA", (57, 57), (0, 0, 255, 255))
        data = io.BytesIO()
        large.save(data, format="ICO", sizes=[(16, 16), (57, 57)], append_images=[small])
        self.env.company.workshop_favicon = base64.b64encode(data.getvalue())
        page = self.url_open("/web/login").text
        self.assertIn('sizes="57x57" href="/workshop_os/icon/57?v=', page)
        self.assertNotIn("/workshop_os/app-icon/64", page)
        favicon = self.url_open("/workshop_os/favicon.ico")
        self.assertEqual((favicon.headers["Content-Type"], favicon.content), ("image/x-icon", data.getvalue()))
        for size, colour in ((57, (0, 0, 255, 255)), (16, (255, 0, 0, 255)), (40, (0, 0, 255, 255))):
            icon = Image.open(io.BytesIO(self.url_open(f"/workshop_os/icon/{size}").content))
            self.assertEqual((icon.size, icon.convert("RGBA").getpixel((5, 5))), ((size, size), colour), size)
        with self.assertRaises(ValidationError):
            self.env.company.workshop_favicon = base64.b64encode(b"not an image")

    def test_shared_links_show_the_shop(self):
        company = self.env.company
        company.workshop_og_image = base64.b64encode(self._png((1200, 630)))
        page = self.url_open("/web/login").text
        self.assertIn(f'property="og:image" content="{company.get_base_url()}/workshop_os/og-image/{company.id}?v=', page)
        self.assertIn(f'property="og:site_name" content="{company.name}"', page)
        self.assertEqual(self.url_open(f"/workshop_os/og-image/{company.id}").status_code, 200)
        order_page = self.url_open(f"/os/{self.order.access_token}").text
        self.assertIn(f'property="og:title" content="{self.order.name} · {company.name}"', order_page)
        self.assertIn("og:description", order_page)

    def _png(self, size):
        output = io.BytesIO()
        Image.new("RGB", size, (232, 178, 30)).save(output, "PNG")
        return output.getvalue()

    def test_login_page_takes_the_shop_colours(self):
        self.env.company.write({"workshop_login_background": "#002848", "workshop_accent_color": "#E8B21E"})
        page = self.url_open("/web/login").text
        self.assertIn("#002848", page)
        self.assertIn("background: #E8B21E", page)
        self.assertIn("color: #111827", page, "dark text on a gold button")
        self.assertIn("/web/binary/company_logo", page)
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        self.env.company.write({"workshop_login_theme": "dark", "workshop_logo_dark": pixel})
        dark = self.url_open("/web/login").text
        self.assertIn(f"/workshop_os/logo/{self.env.company.id}/dark", dark, "the dark card shows the dark logo")
        self.assertIn("background: #16181d", dark)
        self.env.company.workshop_login_background = "red; } body { display: none"
        self.assertNotIn("display: none", self.url_open("/web/login").text, "only #rrggbb reaches the CSS")

    def test_app_icon_follows_the_company(self):
        default = self.url_open("/workshop_os/app-icon/192", allow_redirects=False)
        self.assertEqual(default.status_code, 303)
        self.assertIn("/workshop_os/static/img/app_icon_192.png", default.headers["Location"])
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        self.env.company.workshop_app_icon = pixel
        custom = self.url_open("/workshop_os/app-icon/192")
        self.assertEqual(custom.status_code, 200)
        self.assertEqual(custom.headers["Content-Type"], "image/png")

    def test_app_icon_is_made_from_the_symbol(self):
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        self.env.company.write({"workshop_app_icon": False, "workshop_logo_mark": pixel})
        for size, corner_alpha in ((192, 0), (180, 255)):
            response = self.url_open(f"/workshop_os/app-icon/{size}")
            self.assertEqual(response.status_code, 200)
            icon = Image.open(io.BytesIO(response.content))
            self.assertEqual(icon.size, (size, size))
            self.assertEqual(icon.convert("RGBA").getpixel((0, 0))[3], corner_alpha, "iOS gets square corners")
