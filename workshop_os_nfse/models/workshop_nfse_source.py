from odoo import api, models

NFSE_STATES = [("none", "Not issued"), ("draft", "To issue"), ("done", "Issued")]


class NfseSourceMixin(models.AbstractModel):
    """What the monthly closing and the work order share: open or create the note of the record.
    Each model declares its own `nfse_document_ids` (the inverse field differs) and the two computed fields."""
    _name = "workshop.nfse.source"
    _description = "Record that can be invoiced with an NFS-e"

    @api.depends("nfse_document_ids.state")
    def _compute_nfse_state(self):
        for record in self:
            live = record.nfse_document_ids.filtered(lambda d: d.state != "cancel")
            record.nfse_count = len(record.nfse_document_ids)
            record.nfse_state = ("done" if any(d.state == "done" for d in live)
                                 else "draft" if live else "none")

    def _nfse_values(self):
        raise NotImplementedError

    def action_create_nfse(self):
        self.ensure_one()
        live = self.nfse_document_ids.filtered(lambda d: d.state != "cancel")
        document = live[:1] or self.env["l10n_br_nfse_nacional.document"].create(self._nfse_values())
        return document.get_formview_action()

    def action_view_nfse(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("l10n_br_nfse_nacional.l10n_br_nfse_nacional_document_action")
        action["domain"] = [("id", "in", self.nfse_document_ids.ids)]
        return action
