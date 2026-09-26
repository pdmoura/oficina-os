from odoo import Command
from odoo.tests import TransactionCase, new_test_user


class WorkshopCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.fleet = cls.env["res.partner"].create({"name": "Fleet Test", "is_company": True, "workshop_customer": True})
        cls.contract_fleet = cls.env["res.partner"].create({
            "name": "Contract Fleet", "is_company": True, "workshop_customer": True, "workshop_auto_approve": True,
        })
        cls.service_a = cls.env["workshop.service"].create({"name": "Headlight", "list_price": 180, "hours": 1.0})
        cls.service_b = cls.env["workshop.service"].create({"name": "Battery", "list_price": 120, "hours": 0.5})
        cls.stage_office, cls.stage_work = cls.env["workshop.stage"].create([
            {"name": "Office test", "sequence": -2, "is_waiting": True},
            {"name": "Working test", "sequence": -1},
        ])
        cls.mechanic = new_test_user(cls.env, login="mech_test", groups="workshop_os.group_workshop_user")
        cls.office = new_test_user(cls.env, login="office_test", groups="workshop_os.group_workshop_manager")

    def _vehicle(self, plate="ABC1D23", partner=None):
        return self.env["workshop.vehicle"].create({"plate": plate, "partner_id": (partner or self.fleet).id,
                                                    "brand": "Scania", "model": "R 450"})

    def _order(self, vehicle=None, services=None, **values):
        vehicle = vehicle or self._vehicle()
        return self.env["workshop.order"].create({
            "partner_id": vehicle.partner_id.id,
            "vehicle_id": vehicle.id,
            "stage_id": self.stage_office.id,
            "line_ids": [Command.create(self.env["workshop.order.line"]._vals_from_service(s))
                         for s in (services or self.service_a)],
            **values,
        })
