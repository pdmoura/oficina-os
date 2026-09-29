import re
from copy import deepcopy
from datetime import timedelta
from functools import partial
from pathlib import Path
from unittest.mock import Mock, patch

from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import file_path, mute_logger
from odoo.tools.translate import code_translations

from ..models.res_company import BACKEND_THEME_URL, _contrast, _readable_on_white
from ..models.workshop_vehicle import format_plate, normalize_plate
from .common import WorkshopCase


@tagged("post_install", "-at_install")
class TestVehicle(WorkshopCase):

    def test_plates_are_normalised_and_validated(self):
        self.assertEqual(normalize_plate(" abc-1d23 "), "ABC1D23")
        self.assertEqual(format_plate("abc1234"), "ABC-1234")
        self.assertEqual(format_plate("ABC1D23"), "ABC1D23")
        vehicle = self._vehicle("qwe-4567")
        self.assertEqual(vehicle.plate, "QWE4567")
        self.assertEqual(vehicle.plate_display, "QWE-4567")
        with self.assertRaises(ValidationError):
            self._vehicle("12ABCDE")

    def test_plate_is_unique_per_company(self):
        self._vehicle("RTA2B41")
        with self.assertRaises(Exception), self.cr.savepoint(), mute_logger("odoo.sql_db"):
            self._vehicle("rta-2b41")

    def test_find_by_plate_returns_the_open_order(self):
        order = self._order(self._vehicle("KJH9D12"))
        found = self.env["workshop.vehicle"].find_by_plate("kjh9d12")
        self.assertTrue(found["found"])
        self.assertEqual(found["open_order_id"], order.id)
        self.assertEqual(found["partner_id"], self.fleet.id)
        missing = self.env["workshop.vehicle"].find_by_plate("ZZZ9Z99")
        self.assertFalse(missing["found"])
        self.assertTrue(missing["valid"])


@tagged("post_install", "-at_install")
class TestOrderFlow(WorkshopCase):

    def test_app_create_registers_new_vehicles_and_reuses_open_orders(self):
        Order = self.env["workshop.order"].with_user(self.mechanic)
        result = Order.app_create({"plate": "xyz9k88", "partner_id": self.fleet.id, "brand": "Volvo",
                                   "odometer": "245.800", "service_ids": [self.service_a.id, self.service_b.id]})
        order = self.env["workshop.order"].browse(result["id"])
        self.assertFalse(result["existing"])
        self.assertEqual(order.vehicle_id.plate, "XYZ9K88")
        self.assertEqual(order.vehicle_id.partner_id, self.fleet)
        self.assertEqual(order.odometer, 245800)
        self.assertEqual(order.vehicle_id.odometer, 245800)
        self.assertEqual(len(order.line_ids), 2)
        self.assertEqual(order.amount_total, 300)
        self.assertEqual(order.hours_total, 1.5)
        self.assertEqual(order.user_id, self.mechanic)
        again = Order.app_create({"plate": "XYZ9K88"})
        self.assertEqual(again, {"id": order.id, "existing": True}, "one open order per vehicle")

    def test_contract_fleets_start_approved(self):
        vehicle = self._vehicle("OTR5E07", self.contract_fleet)
        # Done by a mechanic: the contract approves, not the mechanic's rights.
        order = self.env["workshop.order"].with_user(self.mechanic).create({
            "partner_id": vehicle.partner_id.id, "vehicle_id": vehicle.id,
            "line_ids": [Command.create(self.env["workshop.order.line"]._vals_from_service(self.service_a))],
        })
        self.assertEqual(order.state, "approved")
        order.app_add_services([self.service_b.id])
        self.assertTrue(all(line.approval == "approved" for line in order.line_ids.filtered(lambda l: l.service_id == self.service_b)))

    def test_stage_changes_are_timed(self):
        order = self._order()
        self.assertEqual(len(order.stage_log_ids), 1)
        order.stage_log_ids.date_start = fields.Datetime.now() - timedelta(hours=2)
        order.stage_id = self.stage_work
        logs = order.stage_log_ids.sorted("date_start")
        self.assertEqual(logs.stage_id, self.stage_office | self.stage_work)
        self.assertTrue(logs[0].date_end)
        self.assertAlmostEqual(logs[0].duration_hours, 2, delta=0.05)
        self.assertFalse(logs[1].date_end)
        order.stage_id = self.stage_work
        self.assertEqual(len(order.stage_log_ids), 2, "same stage again is not a new step")

    def test_late_orders(self):
        late = self._order(date_promised=fields.Datetime.now() - timedelta(hours=1))
        on_time = self._order(self._vehicle("PLM3C88"), date_promised=fields.Datetime.now() + timedelta(days=1))
        self.assertTrue(late.is_late)
        self.assertFalse(on_time.is_late)
        found = self.env["workshop.order"].search([("is_late", "=", True), ("id", "in", (late | on_time).ids)])
        self.assertEqual(found, late)

    def test_workflow_guards(self):
        order = self._order()
        with self.assertRaises(UserError):
            order.action_deliver()
        order.line_ids.unlink()
        with self.assertRaises(UserError):
            order.action_done()

    def test_app_offers_ready_only_with_services(self):
        order = self._order()
        actions = [a["action"] for a in order.with_user(self.mechanic)._app_state_actions()]
        self.assertEqual(actions, ["action_done"])
        order.line_ids.unlink()
        self.assertEqual(order.with_user(self.mechanic)._app_state_actions(), [])

    def test_mechanic_cannot_approve(self):
        order = self._order()
        with self.assertRaises(AccessError):
            order.with_user(self.mechanic).app_action("action_approve")
        order.with_user(self.office).app_action("action_approve")
        self.assertEqual(order.state, "approved")
        with self.assertRaises(AccessError):
            self.env["workshop.billing"].with_user(self.mechanic).search([])

    def test_office_decisions_hold_over_rpc(self):
        # Any public method can be called over RPC: the office-only steps are checked on the server, not by the buttons.
        order = self._order().with_user(self.mechanic)
        for call in (order.action_approve, order.action_reject, order.action_cancel, order.action_reopen,
                     lambda: order.write({"state": "approved"}),
                     lambda: order.write({"approved_by": "Customer"}),
                     lambda: order.line_ids.write({"approval": "approved"}),
                     lambda: self.env["workshop.order"].with_user(self.mechanic).create({
                         "partner_id": self.fleet.id, "vehicle_id": self._vehicle("QWE7F21").id, "state": "approved"})):
            with self.assertRaises(AccessError):
                call()
        self.assertFalse(hasattr(order, "customer_decide"), "the customer's answer is not an RPC method")
        order.sudo().line_ids.approval = "approved"
        with self.assertRaises(AccessError):
            order.app_remove_line(order.line_ids.id)

    def test_office_users_can_be_the_mechanic(self):
        # Office implies Mechanic; Odoo 19 keeps implied groups out of group_ids.
        domain = self.env["workshop.order"]._fields["user_id"].domain(self.env["workshop.order"])
        users = self.env["res.users"].search(domain)
        self.assertIn(self.office, users)
        self.assertIn(self.mechanic, users)

    def test_office_registers_customers(self):
        # Customers are contacts: creating them takes Odoo's "Contact Creation" group, which Office brings along.
        customer = self.env["res.partner"].with_user(self.office).create({"name": "Frota Sul", "workshop_customer": True})
        self.assertTrue(customer.workshop_customer)
        with self.assertRaises(AccessError):
            self.env["res.partner"].with_user(self.mechanic).create({"name": "Frota Oeste"})

    def test_orders_read_new_until_numbered(self):
        # The form and its breadcrumb show "New" before saving, never the "/" placeholder.
        self.assertEqual(self.env["workshop.order"].new({}).display_name, "New")
        order = self._order()
        self.assertNotIn(order.name, ("/", "New"))
        self.assertNotIn(order.copy().name, ("/", "New", order.name))

    def test_photos_only_from_odoo_or_cloudinary(self):
        order = self._order()
        Photo = self.env["workshop.order.photo"].with_user(self.mechanic)
        with self.assertRaises(ValidationError):
            Photo.create({"order_id": order.id, "url": "javascript:alert(1)"})
        with self.assertRaises(ValidationError):
            Photo.create({"order_id": order.id, "url": "https://tracker.example.com/pixel.png"})
        Photo.create({"order_id": order.id, "url": "https://res.cloudinary.com/demo/image/upload/oficina/a.jpg"})

    def test_checklist_and_photos(self):
        order = self._order()
        template = self.env.ref("workshop_os.checklist_truck_entry")
        data = order.load_checklist(template.id)
        self.assertEqual(len(data["checklist"]), len(template.item_ids))
        first = order.checklist_line_ids[0]
        order.app_save_checklist({str(first.id): {"result": "fail", "note": "broken"}})
        self.assertEqual(first.result, "fail")
        self.assertGreater(order.checklist_progress, 0)

        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        data = self.env["workshop.order.photo"].with_user(self.mechanic).add_photo(order.id, {"data": pixel, "kind": "entry"})
        self.assertEqual(len(data["photos"]), 1)
        self.assertIn("access_token=", order.photo_ids.url)
        self.assertTrue(order.photo_ids.attachment_id)

    def test_cloudinary_signature(self):
        # Reference example from Cloudinary's upload signature documentation.
        signature = self.env["workshop.order.photo"]._cloudinary_sign(
            {"timestamp": 1315060510, "public_id": "sample_image", "eager": "w_400,h_300,c_pad|w_260,h_200,c_crop"},
            "abcd",
        )
        self.assertEqual(signature, "bfd09f95f331f558cbd1320e67aa8d488770583e")
        ticket = self.env["workshop.order.photo"].upload_ticket()
        self.assertEqual(ticket, {"storage": "database"}, "no Cloudinary settings: photos go to the database")

    def _cloudinary_settings(self, **values):
        return self.env["res.config.settings"].create({
            "workshop_photo_storage": "cloudinary", "workshop_cloudinary_cloud_name": "sv-demo",
            "workshop_cloudinary_api_key": "123456789012345", "workshop_cloudinary_api_secret": "abcd",
            "workshop_cloudinary_folder": "oficina", **values,
        })

    def test_cloudinary_settings_catch_common_mistakes(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._cloudinary_settings(workshop_cloudinary_api_key="Root")
        self._cloudinary_settings(workshop_cloudinary_api_key=" 123456789012345\n", workshop_cloudinary_folder="/oficinas/").execute()
        config = self.env["workshop.order.photo"]._cloudinary_config()
        self.assertEqual((config["api_key"], config["folder"]), ("123456789012345", "oficinas"))

    def test_cloudinary_test_sends_a_photo_and_deletes_it(self):
        calls = []

        def cloudinary(method, url, **kwargs):
            calls.append((url.split("/v1_1/sv-demo/")[1], kwargs))
            return Mock(ok=True, json=Mock(return_value={"public_id": "oficina/connection-test"} if "upload" in url else {}))

        with patch("odoo.addons.workshop_os.models.res_config_settings.requests.request", side_effect=cloudinary):
            result = self._cloudinary_settings().action_workshop_test_cloudinary()
        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual([path for path, _kwargs in calls], ["usage", "image/upload", "image/destroy"])
        upload = calls[1][1]["data"]
        signed = {key: upload[key] for key in ("folder", "public_id", "timestamp")}
        self.assertEqual(upload["folder"], "oficina")
        self.assertEqual(upload["signature"], self.env["workshop.order.photo"]._cloudinary_sign(signed, "abcd"))
        self.assertEqual(calls[2][1]["data"]["public_id"], "oficina/connection-test")

    def test_cloudinary_refusals_say_which_value_is_wrong(self):
        refusal = Mock(ok=False, status_code=401, json=Mock(return_value={"error": {"message": "unknown api_key"}}))
        settings = self._cloudinary_settings()
        with patch("odoo.addons.workshop_os.models.res_config_settings.requests.request", return_value=refusal):
            with self.assertRaisesRegex(UserError, "not the key's name"):
                settings.action_workshop_test_cloudinary()


@tagged("post_install", "-at_install")
class TestCustomerApproval(WorkshopCase):

    def test_token_lookup(self):
        order = self._order()
        Order = self.env["workshop.order"]
        self.assertEqual(Order._get_by_token(order.access_token), order)
        wrong_end = "y" if order.access_token.endswith("x") else "x"  # tokens are random: one in 64 ends with "x"
        self.assertFalse(Order._get_by_token(order.access_token[:-1] + wrong_end))
        self.assertFalse(Order._get_by_token("short"))

    def test_customer_link_comes_with_the_order(self):
        # The form copies the link on the tap itself, without asking the server: it reads it from the order.
        order = self._order().with_user(self.mechanic)
        self.assertEqual(order.public_url, order.get_public_url())
        self.assertTrue(order.public_url.endswith(f"/os/{order.access_token}"))

    def test_partial_approval_with_signature(self):
        order = self._order(services=self.service_a | self.service_b)
        keep = order.line_ids.filtered(lambda l: l.service_id == self.service_a)
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        order._customer_decide(True, "Ana Frota", signature=pixel, line_ids=keep.ids)
        self.assertEqual(order.state, "approved")
        self.assertEqual(keep.approval, "approved")
        self.assertEqual((order.line_ids - keep).approval, "rejected")
        self.assertEqual(order.amount_total, 180, "rejected items leave the total")
        self.assertEqual(order.approved_by, "Ana Frota")
        with self.assertRaises(UserError):
            order._customer_decide(True, "Again")

    def test_rejection(self):
        order = self._order()
        order._customer_decide(False, "Ana")
        self.assertEqual(order.state, "rejected")


@tagged("post_install", "-at_install")
class TestBilling(WorkshopCase):

    def test_monthly_closing(self):
        today = fields.Date.context_today(self.env.user)
        last_month_day = today.replace(day=1) - relativedelta(days=5)
        orders = self.env["workshop.order"]
        for plate in ("AAA1A11", "BBB2B22"):
            order = self._order(self._vehicle(plate), services=self.service_a | self.service_b)
            order.action_approve()
            order.action_done()
            order.date_done = fields.Datetime.to_datetime(last_month_day)
            orders |= order
        this_month = self._order(self._vehicle("CCC3C33"))
        this_month.action_approve()
        this_month.action_done()

        billing = self.env["workshop.billing"].create({"partner_id": self.fleet.id})
        billing.action_load_orders()
        self.assertEqual(billing.order_ids, orders)
        self.assertEqual(billing.amount_total, 600)
        self.assertEqual(billing.order_ids.line_ids._service_rows()[0], ("Headlight", 180.0, 2.0, 360.0))
        self.assertIn("Headlight", billing._service_description())
        billing.action_confirm()
        with self.assertRaises(UserError):
            billing.unlink()
        with self.assertRaises(UserError):
            orders[0].action_cancel()

    def test_invoice_description_fits_the_note(self):
        # Same service at two prices: two lines. Over the limit the orders go, then the smallest services are summed.
        order = self._order(services=self.service_a | self.service_b)
        order.line_ids[:1].copy({"order_id": order.id, "price_unit": 200})
        lines = order.line_ids
        orders_note = "Orders: " + ", ".join(["OS 00001"] * 30)
        full = lines._invoice_description("Services:", orders_note)
        self.assertEqual(full.count("- Headlight:"), 2)
        self.assertIn("Orders:", full)
        short = lines._invoice_description("Services:", orders_note, max_length=90)
        self.assertLessEqual(len(short), 90)
        self.assertNotIn("Orders:", short)
        self.assertIn("- Other services:", short)
        self.assertRegex(short, r"Total: \D*500[.,]00", "the total survives")
        tiny = lines._invoice_description("A heading far too long for the note " * 5, max_length=60)
        self.assertLessEqual(len(tiny), 60, "as a last resort the heading is cut")
        self.assertIn("Total:", tiny)

    def test_parts_are_billed_apart_from_labour(self):
        # A part from the catalogue comes marked; the order, the closing and their reports split labour and parts.
        part = self.env["workshop.service"].create({"name": "H7 bulb", "list_price": 40, "is_part": True})
        order = self._order(services=self.service_a | part)
        self.assertEqual(order.line_ids.mapped("is_part"), [False, True])
        self.assertEqual([line["is_part"] for line in order.app_read()["lines"]], [False, True])
        self.assertEqual((order.amount_services, order.amount_parts, order.amount_total), (180, 40, 220))
        self.assertEqual([row[0] for row in order.line_ids._service_rows()], ["Headlight"])
        self.assertEqual([row[0] for row in order.line_ids._service_rows(parts=True)], ["H7 bulb"])
        text = order.line_ids._invoice_description("Services:")
        self.assertNotIn("H7 bulb", text)
        self.assertRegex(text, r"Total: \D*180[.,]00")
        html, _type = self.env["ir.actions.report"]._render_qweb_html("workshop_os.report_workshop_order", order.ids)
        self.assertIn(b"H7 bulb", html, "the work order still lists the part")

        billing = self.env["workshop.billing"].create({"partner_id": self.fleet.id})
        order.billing_id = billing
        self.assertEqual((billing.amount_services, billing.amount_parts, billing.amount_total), (180, 40, 220))
        html, _type = self.env["ir.actions.report"]._render_qweb_html("workshop_os.report_workshop_billing", billing.ids)
        self.assertIn(b"H7 bulb", html, "the closing report has its own parts table")

    def test_photos_without_a_moment_count_as_arrival(self):
        order = self._order()
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        self.env["workshop.order.photo"].add_photo(order.id, {"data": pixel})
        order.photo_ids.kind = False
        self.assertEqual([(label, len(photos)) for label, photos in order._photo_groups(order.photo_ids)],
                         [("Arrival", 1)], "shown on the customer page and the PDF, not dropped")

    def test_reports_render(self):
        order = self._order()
        html, _type = self.env["ir.actions.report"]._render_qweb_html("workshop_os.report_workshop_order", order.ids)
        self.assertIn(order.name.encode(), html)
        self.assertIn(b"ABC1D23", html)
        billing = self.env["workshop.billing"].create({"partner_id": self.fleet.id})
        html, _type = self.env["ir.actions.report"]._render_qweb_html("workshop_os.report_workshop_billing", billing.ids)
        self.assertIn(b"Fleet Test", html)

    def test_print_asks_about_photos_only_when_there_are_some(self):
        order = self._order()
        self.assertEqual(order.action_print()["type"], "ir.actions.report", "no photos: straight to the PDF")
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        for kind in ("work", "entry"):
            self.env["workshop.order.photo"].add_photo(order.id, {"data": pixel, "kind": kind})
        self.assertEqual([label for label, _photos in order._photo_groups(order.photo_ids)], ["Arrival", "During the job"],
                         "grouped in the order they are taken")
        action = order.action_print()
        self.assertEqual(action["res_model"], "workshop.order.print")
        wizard = self.env["workshop.order.print"].with_context(action["context"]).create({})
        self.assertEqual(wizard.photo_count, 2)
        Report = self.env["ir.actions.report"]
        with_photos, _type = Report._render_qweb_html("workshop_os.report_workshop_order", order.ids)
        wizard.include_photos = False
        action = wizard.action_print()
        self.assertTrue(action["close_on_report_download"])
        without, _type = Report.with_context(action["context"])._render_qweb_html("workshop_os.report_workshop_order", order.ids)
        self.assertIn(b'class="photos"', with_photos)
        self.assertNotIn(b'class="photos"', without)

    def test_dashboard(self):
        self._order(date_promised=fields.Datetime.now() - timedelta(hours=3))
        data = self.env["workshop.order"].dashboard_data()
        self.assertGreaterEqual(data["kpis"]["late"], 1)
        self.assertTrue(data["stages"])

    def test_dashboard_lists_skip_empty_stages(self):
        # Opening "In service" from the dashboard shows that column, not an empty "Office" column in front of it.
        Order, used = self.env["workshop.order"], self.stage_work
        self.assertEqual(Order.with_context(workshop_used_stages_only=True)._read_group_stage_ids(used, []), used)
        self.assertIn(self.stage_office, Order._read_group_stage_ids(used, []), "the order board keeps every column")


@tagged("post_install", "-at_install")
class TestAssets(WorkshopCase):

    def test_styles_compile(self):
        # libsass rejects CSS min()/max() it cannot evaluate; a failing bundle leaves the pages unstyled.
        for name in ("workshop_os.assets_public", "web.assets_backend"):
            bundle = self.env["ir.qweb"]._get_asset_bundle(name, js=False)
            bundle.preprocess_css()
            self.assertFalse(bundle.css_errors, name)

    def test_backend_takes_the_brand_colours(self):
        company = self.env.ref("base.main_company")
        company.write({"workshop_accent_color": "#1D4FA0", "workshop_login_background": "#FFFFFF"})
        theme = self.env["ir.attachment"].search([("url", "=", BACKEND_THEME_URL)])
        scss = theme.raw.decode()
        self.assertIn("$o-brand-primary: #1D4FA0;", scss)
        self.assertIn("$o-navbar-background: #FFFFFF;", scss)
        self.assertIn("$o-navbar-entry-color--hover: #111827;", scss, "dark text on a light top bar")
        bundle = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend", js=False)
        self.assertIn(BACKEND_THEME_URL, [asset.url for asset in bundle.stylesheets])
        bundle.preprocess_css()
        self.assertFalse(bundle.css_errors)

    def test_core_terms_have_portuguese(self):
        # Odoo 19 ships these interface terms untranslated; i18n_extra/pt_BR.po fills the gap as a fallback.
        messages = {m["id"]: m["string"] for m in code_translations.get_web_translations("workshop_os", "pt_BR")["messages"]}
        self.assertEqual(messages["My Preferences"], "Minhas preferências")
        self.assertEqual(messages["Missing required fields"], "Preencha os campos obrigatórios")
        self.assertEqual(messages["Shortcuts"], "Atalhos")

    def test_accent_text_stays_readable(self):
        # A yellow brand paints buttons yellow, but its links and outlines are darkened until they read on white.
        for accent in ("#E8B21E", "#FFFFFF", "#22C55E"):
            self.assertGreaterEqual(_contrast(_readable_on_white(accent), "#ffffff"), 4.5, accent)
        self.assertEqual(_readable_on_white("#1D4FA0"), "#1d4fa0", "a dark brand is used as it is")

    def test_arrow_handlers_have_bound_methods(self):
        # OWL calls `() => openOrders(...)` without `this`; such components must run bindMethods(this) in setup.
        static = Path(__file__).parents[1] / "static" / "src"
        calls = re.compile(r"=>\s*(?!this\.)[A-Za-z_$][\w$]*\s*\(")
        unbound = set()
        for xml in static.rglob("*.xml"):
            for template in etree.parse(str(xml)).iter("t"):
                name = template.get("t-name")
                if name and any(calls.search(value) for element in template.iter()
                                for key, value in element.attrib.items() if key.startswith("t-on-")):
                    unbound.add(name)
        self.assertIn("workshop_os.Dashboard", unbound, "the check itself still finds arrow handlers")
        for js in static.rglob("*.js"):
            for component in re.split(r"\n(?=(?:export )?class )", js.read_text(encoding="utf-8")):
                found = re.search(r'static template = "([^"]+)"', component)
                if found and found.group(1) in unbound:
                    unbound.discard(found.group(1))
                    self.assertTrue("bindMethods(this)" in component,
                                    f"{found.group(1)} has arrow handlers but its component never runs bindMethods(this)")
        self.assertFalse(unbound, "templates with arrow handlers but no component found")

    def test_template_extensions_find_their_place(self):
        # An xpath that matches nothing in Odoo's template breaks every screen using it (tabs anchored on a class
        # Odoo only sets through t-attf-class did that to every form with a notebook).
        odoo_templates = {}
        for xml in Path(file_path("web/static/src")).rglob("*.xml"):
            for template in etree.parse(str(xml)).iterfind(".//t[@t-name]"):
                odoo_templates[template.get("t-name")] = template
        to_xpath = partial(re.sub, r"hasclass\('([^']+)'\)", r"contains(concat(' ', normalize-space(@class), ' '), ' \1 ')")
        checked = 0
        for xml in (Path(__file__).parents[1] / "static" / "src").rglob("*.xml"):
            for extension in etree.parse(str(xml)).iterfind(".//t[@t-inherit-mode='extension']"):
                parent = odoo_templates.get(extension.get("t-inherit"))
                if parent is None:
                    continue
                for xpath in extension.iterfind("xpath"):
                    checked += 1
                    self.assertTrue(deepcopy(parent).xpath(to_xpath(xpath.get("expr"))),
                                    f"{xml.name}: {xpath.get('expr')} matches nothing in {extension.get('t-inherit')}")
        self.assertGreaterEqual(checked, 5, "the notebook and the save/discard buttons are checked")


@tagged("post_install", "-at_install")
class TestBrazilDefaults(WorkshopCase):

    def test_new_companies_become_brazilian(self):
        usd, brl, brazil = self.env.ref("base.USD"), self.env.ref("base.BRL"), self.env.ref("base.br")
        blank = self.env["res.company"].create({"name": "Blank Shop", "currency_id": usd.id})
        usa = self.env["res.company"].create({"name": "US Shop", "currency_id": usd.id,
                                              "country_id": self.env.ref("base.us").id})
        worker = new_test_user(self.env, login="blank_user", company_id=blank.id, company_ids=[blank.id], tz=False)
        self.env["res.company"]._workshop_brazil_defaults()
        self.assertEqual((blank.country_id, blank.currency_id), (brazil, brl))
        self.assertEqual(blank.partner_id.tz, "America/Sao_Paulo")
        self.assertEqual(worker.tz, "America/Sao_Paulo")
        self.assertEqual(usa.currency_id, usd, "a company set elsewhere is left alone")

    def test_login_opens_the_workshop_by_role(self):
        roots = self.env["ir.ui.menu"].with_user(self.office).search([("parent_id", "=", False)])
        self.assertEqual(roots[:1], self.env.ref("workshop_os.workshop_os_menu_root"), "first app, ahead of Discuss")
        Order = self.env["workshop.order"]
        self.assertEqual(Order.with_user(self.office)._workshop_home_action()["tag"], "workshop_os.dashboard")
        self.assertEqual(Order.with_user(self.mechanic)._workshop_home_action()["tag"], "workshop_os.mechanic_app")

    def test_theme_is_a_user_setting(self):
        settings = self.env["res.users.settings"]._find_or_create_for_user(self.mechanic)
        self.assertEqual(settings._res_users_settings_format()["workshop_theme"], "dark", "sent to the browser")
        settings.with_user(self.mechanic).set_res_users_settings({"workshop_theme": "light"})
        self.assertEqual(settings.workshop_theme, "light", "each user switches their own theme")

    def test_guided_tour_opens_once_per_user(self):
        # The browser reads these flags to open each tour on a user's first visit, and sets them when it ends.
        mechanic = self.env["res.users.settings"]._find_or_create_for_user(self.mechanic)
        office = self.env["res.users.settings"]._find_or_create_for_user(self.office)
        sent = mechanic._res_users_settings_format()
        self.assertFalse(sent["workshop_tour_app_done"])
        self.assertFalse(sent["workshop_tour_office_done"])
        mechanic.with_user(self.mechanic).set_res_users_settings({"workshop_tour_app_done": True})
        self.assertTrue(mechanic.workshop_tour_app_done)
        self.assertFalse(office.workshop_tour_app_done, "someone else's tour still opens")
        files = [path for path, *_rest in self.env["ir.asset"]._get_asset_paths("web.assets_backend", {})]
        self.assertTrue(any(path.endswith("/tour/workshop_tour.js") for path in files), "the tour ships with the web client")

    def test_odoobot_stays_quiet(self):
        # Its onboarding chat would open over the screen on the first login.
        self.mechanic._on_webclient_bootstrap()
        self.assertEqual(self.mechanic.odoobot_state, "disabled")

    def test_self_signup_is_closed(self):
        scope = self.env["ir.config_parameter"].sudo().get_param("auth_signup.invitation_scope")
        self.assertEqual(scope, "b2b", "accounts are created by the office, not by visitors")

    def test_starting_data_is_written_in_english(self):
        # English sources, translated by pt_BR.po like any Odoo data; each checklist item has an xml id to carry it.
        self.assertEqual(self.env.ref("workshop_os.stage_office").with_context(lang="en_US").name, "Office")
        template = self.env.ref("workshop_os.checklist_truck_entry")
        self.assertIn(self.env.ref("workshop_os.checklist_truck_entry_item_10"), template.item_ids)
        self.assertEqual(len(template.item_ids), 22)
        company = self.env["res.company"].with_context(lang="en_US").create({"name": "New Shop"})
        self.assertIn("90-day warranty", company.workshop_warranty_text)
