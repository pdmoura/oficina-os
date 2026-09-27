from odoo import fields, models


class WorkshopLocation(models.Model):
    """Physical place of the vehicle in the yard: bay, lift, parking, road test."""
    _name = "workshop.location"
    _description = "Workshop Location"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
