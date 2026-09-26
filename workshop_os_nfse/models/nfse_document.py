from odoo import fields, models


class NfseDocument(models.Model):
    _inherit = "nfse.document"

    workshop_billing_id = fields.Many2one("workshop.billing", string="Monthly closing", index="btree_not_null",
                                          ondelete="set null", copy=False)
    workshop_order_id = fields.Many2one("workshop.order", string="Work order", index="btree_not_null",
                                        ondelete="set null", copy=False)

    def _nfse_after_issue(self):
        super()._nfse_after_issue()
        self.workshop_billing_id.filtered(lambda b: b.state == "confirmed").state = "invoiced"
