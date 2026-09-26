import logging
import re

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"


class ResPartner(models.Model):
    _inherit = "res.partner"

    nfse_city_ibge = fields.Char(
        "City IBGE code", size=7,
        help="7-digit IBGE code of the city. Filled from the CEP; required on notes to companies (E0235).",
    )
    nfse_district = fields.Char("District (bairro)")
    nfse_street_number = fields.Char("Street number", help="Leave empty for addresses without a number (S/N).")
    nfse_municipal_registration = fields.Char("Municipal registration (IM)")
    nfse_document_count = fields.Integer(compute="_compute_nfse_document_count")

    def _compute_nfse_document_count(self):
        data = self.env["nfse.document"]._read_group(
            [("partner_id", "child_of", self.commercial_partner_id.ids)], ["partner_id"], ["__count"])
        counts = {}
        for partner, count in data:
            counts[partner.commercial_partner_id.id] = counts.get(partner.commercial_partner_id.id, 0) + count
        for partner in self:
            partner.nfse_document_count = counts.get(partner.commercial_partner_id.id, 0)

    def action_view_nfse_documents(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("l10n_br_nfse_nacional.action_nfse_document")
        action["domain"] = [("partner_id", "child_of", self.commercial_partner_id.id)]
        action["context"] = {"default_partner_id": self.commercial_partner_id.id}
        return action

    def action_nfse_fill_address(self):
        """Street, district, city, state and IBGE code from the CEP (ViaCEP, public; only the CEP is sent)."""
        for partner in self:
            cep = re.sub(r"\D", "", partner.zip or "")
            if len(cep) != 8:
                raise UserError(_("Type the 8-digit CEP first."))
            try:
                response = requests.get(VIACEP_URL.format(cep=cep), timeout=8)
                data = response.json() if response.ok else {}
            except (requests.RequestException, ValueError) as error:
                _logger.info("CEP lookup failed for %s: %s", cep, error)
                raise UserError(_("The CEP service did not answer; fill the address by hand.")) from error
            if not data or data.get("erro"):
                raise UserError(_("CEP %s was not found.", cep))
            brazil = self.env.ref("base.br")
            state = self.env["res.country.state"].search([("country_id", "=", brazil.id), ("code", "=", data.get("uf"))], limit=1)
            values = {
                "zip": f"{cep[:5]}-{cep[5:]}",
                "city": data.get("localidade") or partner.city,
                "country_id": brazil.id,
                "state_id": state.id or partner.state_id.id,
                "nfse_city_ibge": data.get("ibge") or partner.nfse_city_ibge,
            }
            if data.get("logradouro") and not partner.street:
                values["street"] = data["logradouro"]
            if data.get("bairro") and not partner.nfse_district:
                values["nfse_district"] = data["bairro"]
            partner.write(values)
        return True
