from odoo import fields, models


class WorkshopSector(models.Model):
    """Specialty (setor): electrical, air conditioning, diesel, bodywork..."""
    _name = "workshop.sector"
    _description = "Workshop Sector"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
