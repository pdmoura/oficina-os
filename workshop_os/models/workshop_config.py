from odoo import api, fields, models


class WorkshopStage(models.Model):
    """Where the work stands (situação): office, waiting for parts, in progress... Drives the kanban columns."""
    _name = "workshop.stage"
    _description = "Work Order Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    description = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Char(default="#64748B", help="Hex colour used on the kanban column and the mechanic app.")
    fold = fields.Boolean(help="Folded in the kanban view.")
    is_waiting = fields.Boolean(
        "Waiting stage",
        help="Time in this stage does not count as work time (waiting for parts, for approval...).",
    )
    active = fields.Boolean(default=True)
    order_count = fields.Integer(compute="_compute_order_count")

    def _compute_order_count(self):
        counts = dict(self.env["workshop.order"]._read_group(
            [("stage_id", "in", self.ids), ("state", "not in", ("delivered", "cancel"))],
            ["stage_id"], ["__count"],
        ))
        for stage in self:
            stage.order_count = counts.get(stage, 0)


class WorkshopLocation(models.Model):
    """Physical place of the vehicle in the yard: bay, lift, parking, road test."""
    _name = "workshop.location"
    _description = "Workshop Location"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class WorkshopSector(models.Model):
    """Specialty (setor): electrical, air conditioning, diesel, bodywork..."""
    _name = "workshop.sector"
    _description = "Workshop Sector"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class WorkshopService(models.Model):
    _name = "workshop.service"
    _description = "Workshop Service"
    _order = "favorite desc, usage_count desc, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, index="trigram")
    code = fields.Char()
    sector_id = fields.Many2one("workshop.sector", string="Sector")
    list_price = fields.Monetary("Price", currency_field="currency_id")
    cost = fields.Monetary(currency_field="currency_id", help="Parts or third-party cost, for margin reports.")
    hours = fields.Float("Labour hours", digits=(6, 2), help="Estimated time, in hours (1.5 = 1h30).")
    favorite = fields.Boolean(help="Shown as a one-tap button in the mechanic app.")
    usage_count = fields.Integer(readonly=True, help="How many order lines used this service.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
