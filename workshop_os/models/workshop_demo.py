"""Demo yard: two fleets, trucks in every stage today and a finished previous month ready to close."""
import random
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models

TRUCKS = [
    ("RTA2B41", "Scania", "R 450", "2021", "101", "demo_partner_fleet_a"),
    ("QWE7F21", "Volvo", "FH 540", "2022", "102", "demo_partner_fleet_a"),
    ("PLM3C88", "Mercedes-Benz", "Actros 2651", "2020", "103", "demo_partner_fleet_a"),
    ("KJH9D12", "DAF", "XF 530", "2023", "104", "demo_partner_fleet_a"),
    ("OTR5E07", "Volkswagen", "Constellation 24.280", "2019", "105", "demo_partner_fleet_a"),
    ("BRA1S40", "Iveco", "S-Way 480", "2022", "N-12", "demo_partner_fleet_b"),
    ("GHI4J55", "Scania", "G 410", "2018", "N-07", "demo_partner_fleet_b"),
    ("MNB6K30", "Volvo", "VM 270", "2020", "N-21", "demo_partner_fleet_b"),
]

COMPLAINTS = [
    "Farol esquerdo sem luz alta.",
    "Painel acendendo luz de bateria.",
    "Lanterna traseira e pisca falhando.",
    "Ar-condicionado não gela.",
    "Vazamento na mangueira do Arla.",
    "Tomada do semirreboque sem sinal de freio.",
    "Caminhão sem partida pela manhã.",
]


class WorkshopOrderDemo(models.Model):
    _inherit = "workshop.order"

    @api.model
    def _load_demo_data(self):
        rng = random.Random(7)
        ref = self.env.ref
        services = self.env["workshop.service"].search([("is_part", "=", False)])
        mechanics = ref("base.user_admin") | ref("workshop_os.demo_user_mechanic")
        vehicles = self.env["workshop.vehicle"]
        for plate, brand, model, year, fleet_no, partner_xmlid in TRUCKS:
            vehicles |= vehicles.create({
                "plate": plate, "brand": brand, "model": model, "year": year, "fleet_number": fleet_no,
                "partner_id": ref(f"workshop_os.{partner_xmlid}").id, "odometer": rng.randint(90, 480) * 1000,
            })

        today = fields.Date.context_today(self)
        stages = self.env["workshop.stage"].search([])
        locations = self.env["workshop.location"].search([])

        # Last month: finished and delivered, so the monthly closing has something to load.
        last_month = today.replace(day=1) - relativedelta(months=1)
        for index in range(14):
            vehicle = vehicles[index % len(vehicles)]
            arrived = datetime.combine(last_month + relativedelta(days=1 + index * 2), time(8 + index % 4, 0))
            order = self._demo_order(vehicle, arrived, services, rng, mechanics)
            order.action_approve()
            order.write({"stage_id": stages[3].id})
            order.action_done()
            order.write({"date_done": arrived + relativedelta(hours=rng.randint(3, 30))})
            order.action_deliver()
            order.write({"date_delivered": order.date_done + relativedelta(hours=2)})

        # Today: the yard, one truck per stage and a couple waiting.
        for index, vehicle in enumerate(vehicles[:7]):
            arrived = fields.Datetime.now() - relativedelta(hours=rng.randint(1, 50))
            order = self._demo_order(vehicle, arrived, services, rng, mechanics)
            order.write({
                "stage_id": stages[index % len(stages)].id,
                "location_id": locations[index % len(locations)].id,
                "date_promised": arrived + relativedelta(hours=rng.choice([6, 20, 30, 48])),
                "priority": "1" if index == 2 else "0",
            })
            if index in (1, 3, 4):
                order.action_approve()
            if index == 0:
                order.load_checklist(ref("workshop_os.checklist_truck_entry").id)
        self.env["workshop.billing"].create({"partner_id": ref("workshop_os.demo_partner_fleet_a").id}).action_load_orders()
        # Orders copy the warranty text when created, here in the install's English: the demo yard is Brazilian.
        if "pt_BR" in dict(self.env["res.lang"].get_installed()):
            self.search([]).write({"warranty_text": self.env.company.with_context(lang="pt_BR").workshop_warranty_text})

    def _demo_order(self, vehicle, arrived, services, rng, mechanics):
        chosen = services.browse(rng.sample(services.ids, k=rng.randint(1, 3)))
        mechanic = rng.choice(mechanics.ids)
        Line = self.env["workshop.order.line"]
        lines = [Command.create(dict(Line._vals_from_service(s), user_id=mechanic)) for s in chosen]
        # A bulb replacement brings its bulb: a part, billed apart from the labour.
        if self.env.ref("workshop_os.demo_service_bulb") in chosen:
            lines.append(Command.create(dict(Line._vals_from_service(self.env.ref("workshop_os.demo_part_bulb")),
                                             user_id=mechanic)))
        order = self.create({
            "partner_id": vehicle.partner_id.id,
            "vehicle_id": vehicle.id,
            "odometer": vehicle.odometer + rng.randint(500, 4000),
            "driver_name": rng.choice(["João", "Marcos", "Adriano", "Célio", "Wesley"]),
            "complaint": rng.choice(COMPLAINTS),
            "user_id": mechanic,
            "line_ids": lines,
        })
        order.write({"date_in": arrived})
        order.stage_log_ids.write({"date_start": arrived})
        return order
