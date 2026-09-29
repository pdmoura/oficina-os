import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools.nfse_xml import clean_document

_logger = logging.getLogger(__name__)
VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
# Public copies of the Receita Federal company register, free and without a key: BrasilAPI, then Minha Receita
# when the first does not answer. Only the CNPJ is sent.
CNPJ_URLS = ("https://brasilapi.com.br/api/cnpj/v1/{cnpj}", "https://minhareceita.org/{cnpj}")
TIMEOUT = 8
LOWER_WORDS = {"a", "as", "o", "os", "e", "de", "da", "das", "do", "dos", "em", "na", "nas", "no", "nos"}
UPPER_WORDS = {"ME", "EPP", "EIRELI", "S/A", "S.A.", "SA", "II", "III", "IV", "BR"}
# Filled from the CNPJ only when still empty: what the office may have typed differently on purpose.
KEEP_WHEN_SET = ("name", "phone", "email")


def cnpj_is_valid(cnpj):
    """Check digits of a CNPJ, numeric or alphanumeric (from July 2026 the first 12 characters may be letters)."""
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj or "") or len(set(cnpj)) == 1:
        return False
    for size in (12, 13):
        weights = list(range(size - 7, 1, -1)) + list(range(9, 1, -1))
        remainder = sum((ord(char) - 48) * weight for char, weight in zip(cnpj, weights)) % 11
        if int(cnpj[size]) != (0 if remainder < 2 else 11 - remainder):
            return False
    return True


def title_case(text):
    """The register's capitals as people write them: "TRANSPORTES DA SERRA LTDA" -> "Transportes da Serra Ltda"."""
    words = []
    for index, word in enumerate((text or "").split()):
        if word in UPPER_WORDS:
            words.append(word)
        elif index and word.lower() in LOWER_WORDS:
            words.append(word.lower())
        else:
            words.append(word.capitalize())
    return " ".join(words)


def format_phone(digits):
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return digits


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
        data = self.env["l10n_br_nfse_nacional.document"]._read_group(
            [("partner_id", "child_of", self.commercial_partner_id.ids)], ["partner_id"], ["__count"])
        counts = {}
        for partner, count in data:
            counts[partner.commercial_partner_id.id] = counts.get(partner.commercial_partner_id.id, 0) + count
        for partner in self:
            partner.nfse_document_count = counts.get(partner.commercial_partner_id.id, 0)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            # The CNPJ fills the company from the Receita Federal (_onchange_vat_fill_from_cnpj). Odoo's paid
            # autocomplete stays on the name, and leaves this field, where its suggestions held back the typed CNPJ.
            for node in arch.xpath("//field[@name='vat'][@widget='field_partner_autocomplete']"):
                del node.attrib["widget"]
        return arch, view

    # ------------------------------------------------------------------
    # Filled from the CNPJ and the CEP, then editable like any typed value
    # ------------------------------------------------------------------
    @api.onchange("vat")
    def _onchange_vat_fill_from_cnpj(self):
        """A CNPJ brings the company's record: the registered address, and the name, phone and e-mail when still
        empty. The new CEP then brings the names with their accents (_onchange_zip_fill_address)."""
        cnpj = clean_document(self.vat)
        if not cnpj_is_valid(cnpj) or cnpj == clean_document(self._origin.vat):
            return None
        try:
            data = self._nfse_cnpj_record(cnpj)
        except UserError as error:
            return {"warning": {"title": _("CNPJ lookup"), "message": str(error)}}
        for field, value in self._nfse_values_from_cnpj(data).items():
            if field not in KEEP_WHEN_SET or not self[field]:
                self[field] = value
        return self._nfse_cnpj_status_warning(data)

    @api.onchange("zip")
    def _onchange_zip_fill_address(self):
        """A new CEP brings its street, district, city, state and IBGE code; the number and complement stay."""
        cep = re.sub(r"\D", "", self.zip or "")
        if len(cep) != 8 or cep == re.sub(r"\D", "", self._origin.zip or ""):
            return None
        try:
            values = self._nfse_address_from_cep(cep)
        except UserError as error:
            return {"warning": {"title": _("CEP lookup"), "message": str(error)}}
        for field, value in values.items():
            self[field] = value
        return None

    def action_nfse_fill_from_cnpj(self):
        """Button: the whole record again from the Receita Federal, over what was typed (the name stays)."""
        for partner in self:
            cnpj = clean_document(partner.vat)
            if not cnpj_is_valid(cnpj):
                raise UserError(_("Type a valid CNPJ first."))
            values = partner._nfse_values_from_cnpj(partner._nfse_cnpj_record(cnpj))
            if partner.name:
                values.pop("name")
            cep = re.sub(r"\D", "", values.get("zip") or "")
            if len(cep) == 8:
                try:
                    values.update(partner._nfse_address_from_cep(cep))
                except UserError:
                    _logger.info("CEP lookup failed for %s; keeping the register's spelling.", cep)
            partner.write(values)
        return True

    def action_nfse_fill_address(self):
        """Street, district, city, state and IBGE code from the CEP (ViaCEP, public; only the CEP is sent)."""
        for partner in self:
            cep = re.sub(r"\D", "", partner.zip or "")
            if len(cep) != 8:
                raise UserError(_("Type the 8-digit CEP first."))
            values = partner._nfse_address_from_cep(cep)
            # The button only completes: a street or district typed by hand stays.
            if partner.street:
                values.pop("street", None)
            if partner.nfse_district:
                values.pop("nfse_district", None)
            partner.write(values)
        return True

    @api.model
    def _nfse_cnpj_record(self, cnpj):
        """The company's entry in the Receita Federal register, from its public copies."""
        for url in CNPJ_URLS:
            try:
                response = requests.get(url.format(cnpj=cnpj), timeout=TIMEOUT)
            except requests.RequestException as error:
                _logger.info("CNPJ lookup failed at %s: %s", url, error)
                continue
            if response.status_code == 404:
                raise UserError(_("CNPJ %s is not in the Receita Federal register.", cnpj))
            try:
                data = response.json() if response.ok else None
            except ValueError:
                data = None
            if data and data.get("razao_social"):
                return data
        raise UserError(_("The CNPJ services did not answer. Fill the data by hand, or try again in a minute."))

    @api.model
    def _nfse_values_from_cnpj(self, data):
        cep = re.sub(r"\D", "", str(data.get("cep") or ""))
        number = (data.get("numero") or "").strip()
        street_type, street = data.get("descricao_tipo_de_logradouro") or "", data.get("logradouro") or ""
        if street_type and not street.startswith(street_type):
            street = f"{street_type} {street}"
        state = self.env["res.country.state"].search(
            [("country_id", "=", self.env.ref("base.br").id), ("code", "=", data.get("uf"))], limit=1)
        return {
            "name": title_case(data.get("razao_social")),
            "is_company": True,
            "street": title_case(street) or False,
            "nfse_street_number": False if number.upper() in ("", "SN", "S/N") else number,
            "street2": title_case(data.get("complemento")) or False,
            "nfse_district": title_case(data.get("bairro")) or False,
            "zip": f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else False,
            "city": title_case(data.get("municipio")) or False,
            "state_id": state.id or False,
            "country_id": self.env.ref("base.br").id,
            "nfse_city_ibge": str(data.get("codigo_municipio_ibge") or "") or False,
            "phone": format_phone(re.sub(r"\D", "", data.get("ddd_telefone_1") or "")) or False,
            "email": (data.get("email") or "").strip().lower() or False,
        }

    @api.model
    def _nfse_cnpj_status_warning(self, data):
        status = data.get("descricao_situacao_cadastral") or ""
        if status and status.upper() != "ATIVA":
            return {"warning": {"title": _("CNPJ lookup"),
                                "message": _("At the Receita Federal this company is registered as %s.", status)}}
        return None

    @api.model
    def _nfse_address_from_cep(self, cep):
        """Values from ViaCEP for an 8-digit CEP; the street and district only when the CEP has them."""
        try:
            response = requests.get(VIACEP_URL.format(cep=cep), timeout=TIMEOUT)
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
            "country_id": brazil.id,
        }
        for field, value in (("city", data.get("localidade")), ("state_id", state.id),
                             ("nfse_city_ibge", data.get("ibge")), ("street", data.get("logradouro")),
                             ("nfse_district", data.get("bairro"))):
            if value:
                values[field] = value
        return values

    def action_view_nfse_documents(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("l10n_br_nfse_nacional.l10n_br_nfse_nacional_document_action")
        action["domain"] = [("partner_id", "child_of", self.commercial_partner_id.id)]
        action["context"] = {"default_partner_id": self.commercial_partner_id.id}
        return action
