from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    workshop_customer = fields.Boolean("Workshop customer", help="Shown in the customer list of the mechanic app.")
    workshop_auto_approve = fields.Boolean(
        "Pre-approved orders",
        help="Fleet under contract: new orders and services start approved, no per-order approval needed.",
    )
    workshop_vehicle_ids = fields.One2many("workshop.vehicle", "partner_id", string="Vehicles")
    workshop_vehicle_count = fields.Integer(compute="_compute_workshop_counts")
    workshop_order_count = fields.Integer(compute="_compute_workshop_counts")

    def _compute_workshop_counts(self):
        Vehicle = self.env["workshop.vehicle"]
        Order = self.env["workshop.order"]
        for partner in self:
            commercial = partner.commercial_partner_id
            partner.workshop_vehicle_count = Vehicle.search_count([("partner_id", "child_of", commercial.id)])
            partner.workshop_order_count = Order.search_count([("partner_id", "child_of", commercial.id)])

    def action_workshop_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("workshop_os.workshop_order_action")
        action["domain"] = [("partner_id", "child_of", self.commercial_partner_id.id)]
        action["context"] = {"default_partner_id": self.id}
        return action

    def action_workshop_vehicles(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("workshop_os.workshop_vehicle_action")
        action["domain"] = [("partner_id", "child_of", self.commercial_partner_id.id)]
        action["context"] = {"default_partner_id": self.id}
        return action
