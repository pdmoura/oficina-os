from odoo import fields, models


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
