from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.workshop_os.tests.common import WorkshopCase

# city, environment, document type, CNPJ, note number, year+month, random number, check digit
ACCESS_KEY = "5300108" "2" "2" "12345678000195" "0000000000001" "2609" "000000001" "7"


@tagged("post_install", "-at_install")
class TestWorkshopNfse(WorkshopCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({"vat": "12.345.678/0001-95", "nfse_mode": "assisted", "nfse_city_ibge": "5300108",
                               "nfse_iss_rate": 2.0})
        cls.fleet.vat = "11.222.333/0001-81"

    def _done_order(self, plate, when=None):
        order = self._order(self._vehicle(plate), services=self.service_a | self.service_b)
        order.action_approve()
        order.action_done()
        if when:
            order.date_done = when
        return order

    def _closing(self):
        last_month = fields.Date.context_today(self.env.user).replace(day=1) - relativedelta(days=3)
        orders = self._done_order("AAA1A11", last_month) | self._done_order("BBB2B22", last_month)
        billing = self.env["workshop.billing"].create({"partner_id": self.fleet.id})
        billing.action_load_orders()
        return billing, orders

    def test_monthly_closing_becomes_one_note(self):
        billing, _orders = self._closing()
        with self.assertRaises(UserError):
            billing.action_create_nfse()
        billing.action_confirm()
        action = billing.with_user(self.office).action_create_nfse()
        note = self.env["l10n_br_nfse_nacional.document"].browse(action["res_id"])
        self.assertEqual(note.partner_id, self.fleet)
        self.assertEqual(note.amount, 600)
        self.assertEqual(note.date_competence, billing.date_to)
        self.assertIn("Headlight", note.description)
        self.assertEqual(note.iss_rate, 2.0)
        self.assertEqual(billing.action_create_nfse()["res_id"], note.id, "one live note per closing")
        self.assertEqual(billing.nfse_state, "draft")

        note.access_key = ACCESS_KEY
        note.with_user(self.office).action_register_issued()
        self.assertEqual(note.state, "done")
        self.assertEqual(billing.state, "invoiced")
        self.assertEqual(billing.nfse_state, "done")

    def test_single_order_note(self):
        order = self._done_order("CCC3C33")
        note = self.env["l10n_br_nfse_nacional.document"].browse(order.action_create_nfse()["res_id"])
        self.assertEqual(note.amount, 300)
        self.assertIn(order.name, note.description)
        self.assertIn("Battery", note.description)

        billed, _orders = self._closing()
        with self.assertRaises(UserError):
            billed.order_ids[0].action_create_nfse()
        draft = self._order(self._vehicle("DDD4D44"))
        with self.assertRaises(UserError):
            draft.action_create_nfse()

    def test_mechanic_has_no_access_to_notes(self):
        self.assertFalse(self.mechanic.has_group("l10n_br_nfse_nacional.l10n_br_nfse_nacional_group_user"))
        self.assertTrue(self.office.has_group("l10n_br_nfse_nacional.l10n_br_nfse_nacional_group_user"))
