from odoo import fields, models


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
