from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WorkshopBilling(models.Model):
    """Monthly closing for a fleet customer: the finished orders of the period, the report and the service invoice."""
    _name = "workshop.billing"
    _description = "Monthly Closing"
    _inherit = ["mail.thread"]
    _order = "date_to desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    partner_id = fields.Many2one("res.partner", "Customer", required=True, index=True, tracking=True)
    date_from = fields.Date("From", required=True,
                            default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1))
    date_to = fields.Date("To", required=True,
                          default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(days=1))
    order_ids = fields.One2many("workshop.order", "billing_id", string="Work orders")
    order_count = fields.Integer(compute="_compute_totals", store=True)
    amount_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    state = fields.Selection([
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("invoiced", "Invoiced"),
        ("paid", "Paid"),
    ], string="Status", default="draft", required=True, tracking=True)
    notes = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related="company_id.currency_id")

    @api.depends("partner_id.commercial_partner_id.name", "date_to")
    def _compute_name(self):
        for billing in self:
            period = billing.date_to.strftime("%m/%Y") if billing.date_to else ""
            billing.name = f"{billing.partner_id.commercial_partner_id.name or ''} · {period}".strip(" ·")

    @api.depends("order_ids.amount_total", "order_ids.state")
    def _compute_totals(self):
        for billing in self:
            orders = billing.order_ids.filtered(lambda o: o.state != "cancel")
            billing.order_count = len(orders)
            billing.amount_total = sum(orders.mapped("amount_total"))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        # The orders are released by the database (billing_id is set to null).
        if self.filtered(lambda b: b.state != "draft"):
            raise UserError(_("Only draft closings can be deleted."))

    def action_load_orders(self):
        for billing in self:
            if billing.state != "draft":
                raise UserError(_("Only draft closings can be changed."))
            orders = self.env["workshop.order"].search(billing._candidate_domain())
            orders.billing_id = billing
        return True

    def action_confirm(self):
        for billing in self:
            if not billing.order_ids:
                raise UserError(_("Load the orders of the period before confirming."))
        self.write({"state": "confirmed"})
        return True

    def action_reset(self):
        self.filtered(lambda b: b.state == "confirmed").write({"state": "draft"})
        return True

    def action_mark_paid(self):
        self.write({"state": "paid"})
        return True

    def _candidate_domain(self):
        self.ensure_one()
        return [
            ("partner_id", "child_of", self.partner_id.commercial_partner_id.id),
            ("state", "in", ("done", "delivered")),
            ("billing_id", "=", False),
            ("date_done", ">=", fields.Datetime.to_datetime(self.date_from)),
            ("date_done", "<", fields.Datetime.to_datetime(self.date_to + relativedelta(days=1))),
        ]

    def _service_summary(self):
        """Lines grouped by service for the report: [(name, quantity, amount)], largest amount first."""
        self.ensure_one()
        totals = defaultdict(lambda: [0.0, 0.0])
        for line in self.order_ids.line_ids.filtered(lambda l: l.approval != "rejected"):
            totals[line.name][0] += line.quantity
            totals[line.name][1] += line.subtotal
        return sorted(((name, q, a) for name, (q, a) in totals.items()), key=lambda row: -row[2])

    def _service_description(self, max_length=None):
        """Service description of the month's NFS-e: one line per service and price, the total and the orders."""
        self.ensure_one()
        heading = _("Services on %(count)s work orders, %(start)s to %(end)s:",
                    count=len(self.order_ids), start=self.date_from.strftime("%d/%m/%Y"),
                    end=self.date_to.strftime("%d/%m/%Y"))
        orders = _("Orders: %s", ", ".join(self.order_ids.sorted("name").mapped("name")))
        return self.order_ids.line_ids._invoice_description(heading, orders, max_length=max_length)
