from odoo import _, fields, models
from odoo.exceptions import UserError

from .workshop_nfse_source import NFSE_STATES


class WorkshopOrder(models.Model):
    _name = "workshop.order"
    _inherit = ["workshop.order", "workshop.nfse.source"]

    nfse_document_ids = fields.One2many("l10n_br_nfse_nacional.document", "workshop_order_id", string="Service invoices")
    nfse_count = fields.Integer(compute="_compute_nfse_state")
    nfse_state = fields.Selection(NFSE_STATES, string="NFS-e", compute="_compute_nfse_state")

    def _nfse_values(self):
        if self.state not in ("done", "delivered"):
            raise UserError(_("Only finished work orders can be invoiced."))
        if self.billing_id:
            raise UserError(_("This order is billed in the monthly closing %s.", self.billing_id.name))
        lines = self.line_ids.filtered(lambda l: l.approval != "rejected")
        vehicle = " ".join(filter(None, [self.vehicle_id.brand, self.vehicle_id.model]))
        head = _("Services on work order %(order)s, plate %(plate)s", order=self.name, plate=self.plate)
        if vehicle:
            head = f"{head} ({vehicle})"
        body = [f"- {line.name}" for line in lines]
        return {
            "company_id": self.company_id.id,
            "partner_id": self.partner_id.commercial_partner_id.id,
            "amount": self.amount_total,
            "description": "\n".join([head + ":"] + body),
            "date_competence": fields.Date.context_today(self, self.date_done) if self.date_done else fields.Date.context_today(self),
            "origin": self.name,
            "workshop_order_id": self.id,
        }
