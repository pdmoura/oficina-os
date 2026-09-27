from odoo import _, fields, models
from odoo.exceptions import UserError


class NfseDocumentCancel(models.TransientModel):
    _name = "nfse.document.cancel"
    _description = "Cancel an NFS-e"

    document_id = fields.Many2one("nfse.document", required=True, ondelete="cascade")
    mode = fields.Selection(related="document_id.mode")
    reason_code = fields.Selection(
        [("1", "Issuing error"), ("2", "Service not provided"), ("9", "Other")],
        string="Reason", required=True, default="1",
    )
    reason = fields.Text("Explanation", required=True, help="At least 15 characters, as the national system requires.")

    def action_confirm(self):
        self.ensure_one()
        if len((self.reason or "").strip()) < 15:
            raise UserError(_("Explain the cancellation in at least 15 characters."))
        self.document_id._cancel(self.reason_code, self.reason.strip())
        return {"type": "ir.actions.act_window_close"}
