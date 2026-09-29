from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nBrNfseNacionalDocument(models.Model):
    _inherit = "l10n_br_nfse_nacional.document"

    workshop_billing_id = fields.Many2one(
        "workshop.billing", string="Monthly closing", index="btree_not_null", ondelete="set null", copy=False,
        domain="[('state', 'in', ('confirmed', 'invoiced', 'paid')), ('company_id', '=', company_id)]",
        help="Fills in the customer, the amount and the description from a confirmed monthly closing.")
    workshop_order_id = fields.Many2one(
        "workshop.order", string="Work order", index="btree_not_null", ondelete="set null", copy=False,
        domain="[('state', 'in', ('done', 'delivered')), ('billing_id', '=', False), ('company_id', '=', company_id)]",
        help="Fills in the customer, the amount and the description from a finished work order.")

    @api.onchange("workshop_order_id")
    def _onchange_workshop_order_id(self):
        if self.workshop_order_id:
            self.workshop_billing_id = False
            return self._workshop_fill(self.workshop_order_id)

    @api.onchange("workshop_billing_id")
    def _onchange_workshop_billing_id(self):
        if self.workshop_billing_id:
            self.workshop_order_id = False
            return self._workshop_fill(self.workshop_billing_id)

    def _workshop_fill(self, source):
        """A note started by hand takes its values from the order or closing picked, as if created from it."""
        try:
            values = source._nfse_values()
        except UserError as error:
            source_field = "workshop_order_id" if source._name == "workshop.order" else "workshop_billing_id"
            self[source_field] = False
            return {"warning": {"title": _("Cannot invoice %s", source.display_name), "message": str(error)}}
        for name in ("partner_id", "amount", "description", "date_competence", "origin"):
            self[name] = values[name]

    def _nfse_after_issue(self):
        super()._nfse_after_issue()
        self.workshop_billing_id.filtered(lambda b: b.state == "confirmed").state = "invoiced"
