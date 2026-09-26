import json

from odoo import Command
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

    def test_manifest_opens_the_mechanic_app(self):
        manifest = self.url_open("/web/manifest.webmanifest").json()
        self.assertEqual(manifest["start_url"], "/odoo/action-workshop_os.action_mechanic_app")
