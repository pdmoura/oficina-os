from odoo import api, fields, models


class WorkshopOrderPrint(models.TransientModel):
    _name = "workshop.order.print"
    _description = "Print Work Order"

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade")
    photo_count = fields.Integer(compute="_compute_photo_count")
    include_photos = fields.Boolean("Include photos", default=True)

    @api.depends("order_id")
    def _compute_photo_count(self):
        for wizard in self:
            wizard.photo_count = len(wizard.order_id.photo_ids.filtered("show_to_customer"))

    def action_print(self):
        report = self.env.ref("workshop_os.action_report_workshop_order")
        action = report.with_context(workshop_without_photos=not self.include_photos).report_action(
            self.order_id, config=False)
        return {**action, "close_on_report_download": True}
