from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

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
        with self.assertRaises(Exception), self.cr.savepoint():
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
        order = self._order(self._vehicle("OTR5E07", self.contract_fleet))
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
        with self.assertRaises(UserError):
            order.with_user(self.mechanic).app_action("action_approve")
        order.with_user(self.office).app_action("action_approve")
        self.assertEqual(order.state, "approved")
        with self.assertRaises(AccessError):
            self.env["workshop.billing"].with_user(self.mechanic).search([])

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


@tagged("post_install", "-at_install")
class TestCustomerApproval(WorkshopCase):

    def test_token_lookup(self):
        order = self._order()
        Order = self.env["workshop.order"]
        self.assertEqual(Order._get_by_token(order.access_token), order)
        self.assertFalse(Order._get_by_token(order.access_token[:-1] + "x"))
        self.assertFalse(Order._get_by_token("short"))

    def test_partial_approval_with_signature(self):
        order = self._order(services=self.service_a | self.service_b)
        keep = order.line_ids.filtered(lambda l: l.service_id == self.service_a)
        pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        order.customer_decide(True, "Ana Frota", signature=pixel, line_ids=keep.ids)
        self.assertEqual(order.state, "approved")
        self.assertEqual(keep.approval, "approved")
        self.assertEqual((order.line_ids - keep).approval, "rejected")
        self.assertEqual(order.amount_total, 180, "rejected items leave the total")
        self.assertEqual(order.approved_by, "Ana Frota")
        with self.assertRaises(UserError):
            order.customer_decide(True, "Again")

    def test_rejection(self):
        order = self._order()
        order.customer_decide(False, "Ana")
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
        self.assertEqual(billing.service_summary()[0], ("Headlight", 2.0, 360.0))
        self.assertIn("Headlight", billing.service_description())
        billing.action_confirm()
        with self.assertRaises(UserError):
            billing.unlink()
        with self.assertRaises(UserError):
            orders[0].action_cancel()

    def test_reports_render(self):
        order = self._order()
        html, _type = self.env["ir.actions.report"]._render_qweb_html("workshop_os.report_workshop_order", order.ids)
        self.assertIn(order.name.encode(), html)
        self.assertIn(b"ABC1D23", html)
        billing = self.env["workshop.billing"].create({"partner_id": self.fleet.id})
        html, _type = self.env["ir.actions.report"]._render_qweb_html("workshop_os.report_workshop_billing", billing.ids)
        self.assertIn(b"Fleet Test", html)

    def test_dashboard(self):
        self._order(date_promised=fields.Datetime.now() - timedelta(hours=3))
        data = self.env["workshop.order"].dashboard_data()
        self.assertGreaterEqual(data["kpis"]["late"], 1)
        self.assertTrue(data["stages"])
