from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

SOURCE_FIELDS = ("workshop_order_id", "workshop_billing_id")


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

    @api.constrains("workshop_order_id", "workshop_billing_id", "state")
    def _check_workshop_single_note(self):
        """One live note per work order and per closing, however the note was made: no service invoiced twice."""
        for note in self.filtered(lambda n: n.state != "cancel"):
            for source in (note.workshop_order_id, note.workshop_billing_id):
                other = source.nfse_document_ids.filtered(lambda d: d.state != "cancel" and d != note)[:1]
                if other:
                    raise ValidationError(_("%(source)s already has the NFS-e %(note)s; cancel it before making another.",
                                            source=source.display_name, note=other.display_name))

    @api.onchange("workshop_order_id")
    def _onchange_workshop_order_id(self):
        if self.workshop_order_id:
            return self._workshop_fill("workshop_order_id")

    @api.onchange("workshop_billing_id")
    def _onchange_workshop_billing_id(self):
        if self.workshop_billing_id:
            return self._workshop_fill("workshop_billing_id")

    def _workshop_fill(self, field):
        """A note started by hand takes its values from the order or closing picked, as if created from it.

        A source that cannot be invoiced (not finished, already on another note...) is refused with a warning and the
        note keeps what it had, including its previous source, so content and link never part ways.
        """
        source = self[field]
        live = source.nfse_document_ids.filtered(lambda d: d.state != "cancel" and d != self._origin)[:1]
        try:
            if live:
                raise UserError(_("It already has the NFS-e %s.", live.display_name))
            values = source._nfse_values()
        except UserError as error:
            self[field] = False
            return {"warning": {"title": _("Cannot invoice %s", source.display_name), "message": str(error)}}
        for other in SOURCE_FIELDS:
            if other != field:
                self[other] = False
        for name in ("partner_id", "amount", "description", "date_competence", "origin"):
            self[name] = values[name]

    def _nfse_after_issue(self):
        super()._nfse_after_issue()
        self.workshop_billing_id.filtered(lambda b: b.state == "confirmed").state = "invoiced"
