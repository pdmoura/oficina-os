from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        document = live[:1] or self.env["nfse.document"].create(self._nfse_values())
        return document.get_formview_action()

    def action_view_nfse(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("l10n_br_nfse_nacional.action_nfse_document")
        action["domain"] = [("id", "in", self.nfse_document_ids.ids)]
        return action


NFSE_STATES = [("none", "Not issued"), ("draft", "To issue"), ("done", "Issued")]


class WorkshopBilling(models.Model):
    _name = "workshop.billing"
    _inherit = ["workshop.billing", "workshop.nfse.source"]

    nfse_document_ids = fields.One2many("nfse.document", "workshop_billing_id", string="Service invoices")
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


class WorkshopOrder(models.Model):
    _name = "workshop.order"
    _inherit = ["workshop.order", "workshop.nfse.source"]

    nfse_document_ids = fields.One2many("nfse.document", "workshop_order_id", string="Service invoices")
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
