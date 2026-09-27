import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Old Brazilian plates (ABC1234) and Mercosur plates (ABC1D23).
PLATE_RE = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")


def normalize_plate(value):
    """'abc-1d23 ' -> 'ABC1D23'. Accepts what people type and what OCR returns."""
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def format_plate(value):
    """Display form: ABC-1234 for old plates, ABC1D23 for Mercosur plates."""
    plate = normalize_plate(value)
    if len(plate) == 7 and plate[4].isdigit():
        return f"{plate[:3]}-{plate[3:]}"
    return plate


class WorkshopVehicle(models.Model):
    _name = "workshop.vehicle"
    _description = "Vehicle"
    _inherit = ["mail.thread"]
    _order = "plate"
    _rec_names_search = ["plate", "fleet_number", "model", "brand"]

    name = fields.Char(compute="_compute_name", store=True)
    plate = fields.Char(required=True, index=True, tracking=True)
    plate_display = fields.Char("Formatted plate", compute="_compute_plate_display")
    fleet_number = fields.Char("Fleet number", help="The customer's own number for this vehicle (prefixo, frota).")
    partner_id = fields.Many2one("res.partner", "Customer", index=True, tracking=True)
    brand = fields.Char()
    model = fields.Char()
    year = fields.Char()
    color = fields.Char()
    fuel = fields.Selection([
        ("diesel", "Diesel"),
        ("flex", "Flex"),
        ("gasoline", "Gasoline"),
        ("ethanol", "Ethanol"),
        ("electric", "Electric"),
        ("other", "Other"),
    ], default="diesel")
    chassis = fields.Char("VIN / chassis")
    odometer = fields.Integer("Last odometer (km)", tracking=True)
    notes = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    order_ids = fields.One2many("workshop.order", "vehicle_id", string="Work orders")
    order_count = fields.Integer(compute="_compute_order_stats")
    open_order_id = fields.Many2one("workshop.order", compute="_compute_order_stats",
                                    help="Order currently open for this vehicle, if any.")
    last_visit = fields.Datetime(compute="_compute_order_stats")

    _plate_company_uniq = models.Constraint(
        "UNIQUE(plate, company_id)",
        "This plate is already registered.",
    )

    @api.depends("plate", "brand", "model")
    def _compute_name(self):
        for vehicle in self:
            label = " ".join(filter(None, [vehicle.brand, vehicle.model]))
            plate = format_plate(vehicle.plate)
            vehicle.name = f"{plate} · {label}" if label else plate

    @api.depends("plate")
    def _compute_plate_display(self):
        for vehicle in self:
            vehicle.plate_display = format_plate(vehicle.plate)

    def _compute_order_stats(self):
        Order = self.env["workshop.order"]
        counts = dict(Order._read_group([("vehicle_id", "in", self.ids)], ["vehicle_id"], ["__count"]))
        open_orders = Order.search([("vehicle_id", "in", self.ids), ("state", "in", ("draft", "approved", "done"))],
                                   order="date_in desc")
        last = dict(Order._read_group([("vehicle_id", "in", self.ids)], ["vehicle_id"], ["date_in:max"]))
        for vehicle in self:
            vehicle.order_count = counts.get(vehicle, 0)
            vehicle.open_order_id = open_orders.filtered(lambda o: o.vehicle_id == vehicle)[:1]
            vehicle.last_visit = last.get(vehicle)

    @api.constrains("plate")
    def _check_plate(self):
        for vehicle in self:
            if not PLATE_RE.match(vehicle.plate or ""):
                raise ValidationError(_("%s is not a valid plate. Use ABC1234 or ABC1D23.", vehicle.plate))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "plate" in vals:
                vals["plate"] = normalize_plate(vals["plate"])
        return super().create(vals_list)

    def write(self, vals):
        if "plate" in vals:
            vals["plate"] = normalize_plate(vals["plate"])
        return super().write(vals)

    def action_view_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("workshop_os.action_workshop_order")
        action["domain"] = [("vehicle_id", "=", self.id)]
        action["context"] = {"default_vehicle_id": self.id, "default_partner_id": self.partner_id.id}
        return action

    @api.model
    def find_by_plate(self, plate):
        """Used by the mechanic app: the vehicle and its open order for a typed or scanned plate."""
        plate = normalize_plate(plate)
        vehicle = self.search([("plate", "=", plate)], limit=1)
        if not vehicle:
            return {"plate": plate, "found": False, "valid": bool(PLATE_RE.match(plate))}
        open_order = self.env["workshop.order"].search(
            [("vehicle_id", "=", vehicle.id), ("state", "in", ("draft", "approved", "done"))], limit=1)
        return {
            "plate": plate,
            "found": True,
            "valid": True,
            "id": vehicle.id,
            "display": vehicle.plate_display,
            "description": " ".join(filter(None, [vehicle.brand, vehicle.model, vehicle.year])),
            "fleet_number": vehicle.fleet_number or "",
            "partner_id": vehicle.partner_id.id,
            "partner_name": vehicle.partner_id.display_name or "",
            "odometer": vehicle.odometer,
            "open_order_id": open_order.id,
            "open_order_name": open_order.name or "",
            "order_count": vehicle.order_count,
        }
