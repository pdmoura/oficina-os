from odoo import _, fields, models
from odoo.exceptions import UserError

from .workshop_nfse_source import NFSE_STATES


class WorkshopBilling(models.Model):
    _name = "workshop.billing"
    _inherit = ["workshop.billing", "workshop.nfse.source"]

    nfse_document_ids = fields.One2many("l10n_br_nfse_nacional.document", "workshop_billing_id", string="Service invoices")
    nfse_count = fields.Integer(compute="_compute_nfse_state")
    nfse_state = fields.Selection(NFSE_STATES, string="NFS-e", compute="_compute_nfse_state")

    def _nfse_values(self):
        if self.state not in ("confirmed", "invoiced", "paid"):
            raise UserError(_("Confirm the monthly closing before issuing its NFS-e."))
        return {
            "company_id": self.company_id.id,
            "partner_id": self.partner_id.commercial_partner_id.id,
            "amount": self.amount_total,
            "description": self._service_description(),
            "date_competence": self.date_to,
            "origin": self.name,
            "workshop_billing_id": self.id,
        }
