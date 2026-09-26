from odoo import fields, models

RESULTS = [("ok", "OK"), ("attention", "Attention"), ("fail", "Problem"), ("na", "N/A")]


class WorkshopChecklistTemplate(models.Model):
    _name = "workshop.checklist.template"
    _description = "Checklist Template"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection([("entry", "Arrival"), ("exit", "Delivery"), ("inspection", "Inspection")],
                            default="entry", required=True)
    vehicle_type = fields.Selection([("truck", "Truck"), ("light", "Light vehicle"), ("bus", "Bus"), ("any", "Any")],
                                    default="truck")
    item_ids = fields.One2many("workshop.checklist.template.item", "template_id", string="Items", copy=True)
    item_count = fields.Integer(compute="_compute_item_count")
    active = fields.Boolean(default=True)

    def _compute_item_count(self):
        for template in self:
            template.item_count = len(template.item_ids)


class WorkshopChecklistTemplateItem(models.Model):
    _name = "workshop.checklist.template.item"
    _description = "Checklist Template Item"
    _order = "sequence, id"

    template_id = fields.Many2one("workshop.checklist.template", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    section = fields.Char(translate=True)
    name = fields.Char(required=True, translate=True)


class WorkshopOrderChecklist(models.Model):
    _name = "workshop.order.checklist"
    _description = "Work Order Checklist Answer"
    _order = "order_id, sequence, id"

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade", index=True)
    template_id = fields.Many2one("workshop.checklist.template")
    sequence = fields.Integer(default=10)
    section = fields.Char()
    name = fields.Char(required=True)
    result = fields.Selection(RESULTS)
    note = fields.Char()
