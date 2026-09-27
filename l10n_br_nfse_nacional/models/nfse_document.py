import base64
import io
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from zoneinfo import ZoneInfo

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import plaintext2html

from ..tools import nfse_xml

_logger = logging.getLogger(__name__)

EMISSOR_URLS = {
    "1": "https://www.nfse.gov.br/EmissorNacional",
    "2": "https://www.producaorestrita.nfse.gov.br/EmissorNacional",
}
PUBLIC_URL = "https://www.nfse.gov.br/ConsultaPublica/?tpc=1&chave={key}"
SEFIN_URLS = {
    "1": "https://sefin.nfse.gov.br/SefinNacional",
    "2": "https://sefin.producaorestrita.nfse.gov.br/SefinNacional",
}
BRASILIA = ZoneInfo("America/Sao_Paulo")
APP_VERSION = "OdooWorkshop-1.0"


class NfseDocument(models.Model):
    _name = "nfse.document"
    _description = "Service invoice (NFS-e)"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Issued"), ("error", "Rejected"), ("cancel", "Cancelled")],
        default="draft", required=True, tracking=True, copy=False,
    )
    mode = fields.Selection(
        [("assisted", "Assisted"), ("api", "Direct (API)")], required=True,
        default=lambda self: self.env.company.nfse_mode,
    )
    environment = fields.Selection(
        [("2", "Test (produção restrita)"), ("1", "Production")], required=True,
        default=lambda self: self.env.company.nfse_environment,
    )
    partner_id = fields.Many2one("res.partner", string="Customer", required=True, tracking=True)
    partner_vat = fields.Char(related="partner_id.commercial_partner_id.vat")
    date_competence = fields.Date("Competence", required=True, default=fields.Date.context_today,
                                  help="Date of the service; it defines the tax period and cannot be in the future.")
    description = fields.Text("Service description", required=True)
    amount = fields.Monetary("Service amount", required=True, tracking=True)
    service_code = fields.Char("National service code", size=6, default=lambda self: self.env.company.nfse_service_code)
    municipal_service_code = fields.Char("Municipal service code", size=3,
                                         default=lambda self: self.env.company.nfse_municipal_service_code)
    nbs_code = fields.Char("NBS code", size=9, default=lambda self: self.env.company.nfse_service_nbs)
    iss_rate = fields.Float("ISS rate (%)", digits=(5, 2), default=lambda self: self.env.company.nfse_iss_rate)
    iss_amount = fields.Monetary("ISS (estimate)", compute="_compute_iss_amount")
    iss_withheld = fields.Boolean("ISS withheld by the customer")
    origin = fields.Char("Source")

    dps_series = fields.Char("DPS series", readonly=True, copy=False)
    dps_number = fields.Integer("DPS number", readonly=True, copy=False)
    dps_key = fields.Char("DPS id", readonly=True, copy=False)
    access_key = fields.Char("Access key", size=50, copy=False, tracking=True)
    nfse_number = fields.Char("NFS-e number", readonly=True, copy=False)
    issued_on = fields.Datetime("Issued on", readonly=True, copy=False)
    dps_xml = fields.Binary("DPS (signed XML)", attachment=True, readonly=True, copy=False)
    dps_xml_name = fields.Char(compute="_compute_file_names")
    nfse_xml = fields.Binary("NFS-e (XML)", attachment=True, readonly=True, copy=False)
    nfse_xml_name = fields.Char(compute="_compute_file_names")
    error_message = fields.Text("Error", readonly=True, copy=False)
    issues = fields.Text("Missing before issuing", compute="_compute_issues")

    # The same values as typed on the Emissor Nacional, ready to copy.
    assist_partner_document = fields.Char("Customer CNPJ/CPF", compute="_compute_assist")
    assist_partner_name = fields.Char("Customer name", compute="_compute_assist")
    assist_competence = fields.Char("Competence (dd/mm/yyyy)", compute="_compute_assist")
    assist_service_code = fields.Char("Service code (as typed)", compute="_compute_assist")
    assist_amount = fields.Char("Amount (as typed)", compute="_compute_assist")
    assist_iss_rate = fields.Char("ISS rate (as typed)", compute="_compute_assist")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("nfse_number", "dps_number", "dps_series")
    def _compute_name(self):
        for doc in self:
            if doc.nfse_number:
                doc.name = _("NFS-e %s", doc.nfse_number)
            elif doc.dps_number:
                doc.name = _("DPS %(series)s-%(number)s", series=doc.dps_series, number=doc.dps_number)
            else:
                doc.name = _("Draft NFS-e")

    @api.depends("amount", "iss_rate")
    def _compute_iss_amount(self):
        for doc in self:
            doc.iss_amount = doc.currency_id.round(doc.amount * doc.iss_rate / 100)

    @api.depends("access_key", "nfse_number", "dps_key")
    def _compute_file_names(self):
        for doc in self:
            doc.dps_xml_name = f"{doc.dps_key or 'dps'}.xml"
            doc.nfse_xml_name = f"NFSe-{doc.access_key or doc.nfse_number or doc.id}.xml"

    @api.depends("partner_id", "date_competence", "service_code", "amount", "iss_rate")
    def _compute_assist(self):
        for doc in self:
            partner = doc.partner_id.commercial_partner_id
            doc.assist_partner_document = nfse_xml.clean_document(partner.vat)
            doc.assist_partner_name = partner.name or ""
            doc.assist_competence = doc.date_competence.strftime("%d/%m/%Y") if doc.date_competence else ""
            code = doc.service_code or ""
            doc.assist_service_code = f"{code[:2]}.{code[2:4]}.{code[4:]}" if len(code) == 6 else code
            doc.assist_amount = f"{doc.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            doc.assist_iss_rate = f"{doc.iss_rate:.2f}".replace(".", ",") if doc.iss_rate else ""

    @api.depends("mode", "company_id", "partner_id", "amount", "description", "service_code", "iss_rate",
                 "iss_withheld", "date_competence")
    def _compute_issues(self):
        for doc in self:
            doc.issues = "\n".join(f"• {issue}" for issue in doc._nfse_issues())

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.ondelete(at_uninstall=False)
    def _unlink_except_sent(self):
        if any(doc.state in ("done", "cancel") or doc.dps_key for doc in self):
            raise UserError(_("Notes already sent to the national system cannot be deleted; cancel them instead."))

    # ------------------------------------------------------------------
    # Actions (assisted mode: the note is issued on the Emissor Nacional website; direct mode: sent to SEFIN)
    # ------------------------------------------------------------------
    def action_open_emissor(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": EMISSOR_URLS[self.environment], "target": "new"}

    def action_register_issued(self):
        for doc in self:
            key = nfse_xml.clean_document(doc.access_key)
            if len(key) != 50 or not key.isdigit():
                raise UserError(_("Paste the 50-digit access key of the note issued on the Emissor Nacional."))
            doc.write({"access_key": key, "state": "done", "issued_on": fields.Datetime.now(),
                       "nfse_number": nfse_xml.number_from_access_key(key), "error_message": False})
            doc.message_post(body=_("NFS-e issued on the Emissor Nacional and registered."))
        self._nfse_after_issue()

    def action_view_public(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": PUBLIC_URL.format(key=self.access_key), "target": "new"}

    def action_issue(self):
        for doc in self:
            if doc.state not in ("draft", "error"):
                continue
            issues = doc._nfse_issues()
            if issues:
                raise UserError("\n".join(issues))
            doc._issue_api()
        failed = self.filtered(lambda d: d.state == "error")
        if len(self) == 1 and failed:
            return {"type": "ir.actions.client", "tag": "display_notification", "params": {
                "type": "danger", "sticky": True, "title": _("NFS-e rejected"), "message": failed.error_message,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            }}
        return True

    def action_open_cancel(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "nfse.document.cancel", "view_mode": "form", "target": "new",
            "name": _("Cancel NFS-e"), "context": {"default_document_id": self.id},
        }

    def action_reset_draft(self):
        self.filtered(lambda d: d.state == "error").write({"state": "draft", "error_message": False})

    # ------------------------------------------------------------------
    # Checks before issuing
    # ------------------------------------------------------------------
    def _nfse_issues(self):
        """What the national system would reject, found before anything is sent."""
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id.commercial_partner_id
        issues = []
        if len(nfse_xml.clean_document(company.vat)) != 14:
            issues.append(_("The company's CNPJ (Tax ID) is missing or incomplete."))
        if not nfse_xml.is_ibge_code(company.nfse_city_ibge):
            issues.append(_("The company's city IBGE code must have 7 digits (NFS-e settings)."))
        if company.nfse_simples == "3" and company.nfse_simples_total_rate <= 0:
            issues.append(_("Set the approximate Simples Nacional rate (NFS-e settings)."))
        document = nfse_xml.clean_document(partner.vat)
        if len(document) not in (11, 14):
            issues.append(_("The customer needs a CNPJ or CPF."))
        elif document == nfse_xml.clean_document(company.vat):
            issues.append(_("The customer cannot be the company itself."))
        if len(document) == 14 or self.iss_withheld:
            missing = [label for label, value in (
                (_("CEP"), len(nfse_xml.clean_document(partner.zip)) == 8),
                (_("street"), partner.street),
                (_("district"), partner.nfse_district),
                (_("city IBGE code"), nfse_xml.is_ibge_code(partner.nfse_city_ibge)),
            ) if not value]
            if missing:
                issues.append(_("The customer's address is incomplete: %s.", ", ".join(missing)))
        if not (self.service_code or "").isdigit() or len(self.service_code or "") != 6:
            issues.append(_("The national service code must have 6 digits (e.g. 140101)."))
        if self.amount <= 0:
            issues.append(_("The service amount must be positive."))
        description = nfse_xml.clean_text(self.description, multiline=True)
        if not description:
            issues.append(_("Describe the service."))
        elif len(description) > nfse_xml.MAX_DESCRIPTION:
            issues.append(_("The description is longer than %s characters.", nfse_xml.MAX_DESCRIPTION))
        if self.date_competence and self.date_competence > fields.Date.context_today(self):
            issues.append(_("The competence date cannot be in the future."))
        if nfse_xml.iss_rate_required(company.nfse_simples, company.nfse_simples_regime, self.iss_withheld) \
                and not 1.8 <= self.iss_rate <= 5:
            issues.append(_("With the ISS withheld, the ISS rate must be between 1.8% and 5%."))
        if self.mode == "api":
            certificate = company.sudo().nfse_certificate_id
            if not certificate:
                issues.append(_("Direct emission needs the company's A1 certificate (NFS-e settings)."))
            elif not certificate.is_valid:
                issues.append(_("The A1 certificate is expired or could not be read."))
            elif not certificate.private_key_id:
                issues.append(_("The A1 certificate has no private key; upload the .pfx file with its password."))
        return issues

    # ------------------------------------------------------------------
    # Direct mode: sign the DPS and send it to SEFIN Nacional.
    # ------------------------------------------------------------------
    def _issue_api(self):
        self.ensure_one()
        retry = bool(self.dps_key)  # a previous attempt reached the point of sending
        if not self.dps_number:
            self.write({"dps_series": self.company_id.nfse_series or "1", "dps_number": self._next_dps_number()})
        data = self._nfse_dps_data()
        if retry and self._nfse_recover(data["id"]):
            return
        root = nfse_xml.build_dps(data)
        try:
            nfse_xml.validate(root)
        except nfse_xml.NfseXmlError as error:
            self._nfse_rejected(_("The note does not match the national layout:\n%s", error))
            return
        key_pem, cert_pem = self._nfse_key_and_certificate()
        signed = nfse_xml.sign(root, key_pem, cert_pem)
        self.write({"dps_key": data["id"], "dps_xml": base64.b64encode(signed)})
        status, payload = self._nfse_request("POST", "/nfse", {"dpsXmlGZipB64": nfse_xml.pack(signed)})
        if status in (200, 201) and nfse_xml.get_ci(payload, "nfseXmlGZipB64"):
            self._nfse_store(payload)
            return
        errors = nfse_xml.response_errors(payload)
        # E0014: this DPS already became a note, typically after an answer lost on the way back.
        if "E0014" in errors and self._nfse_recover(data["id"]):
            return
        self._nfse_rejected(errors or _("HTTP %s without details.", status))

    def _nfse_recover(self, dps_id):
        """After a lost answer the DPS may have become a note already (E0014): fetch it instead of resending."""
        status, _payload = self._nfse_request("HEAD", f"/dps/{dps_id}")
        if status != 200:
            return False
        status, payload = self._nfse_request("GET", f"/dps/{dps_id}")
        key = nfse_xml.get_ci(payload, "chaveAcesso")
        if status != 200 or not key:
            return False
        status, payload = self._nfse_request("GET", f"/nfse/{key}")
        if status == 200 and nfse_xml.get_ci(payload, "nfseXmlGZipB64"):
            self._nfse_store(payload)
            return True
        return False

    def _nfse_store(self, payload):
        nfse = nfse_xml.unpack(nfse_xml.get_ci(payload, "nfseXmlGZipB64"))
        info = nfse_xml.parse_nfse(nfse)
        self.write({
            "state": "done",
            "access_key": nfse_xml.get_ci(payload, "chaveAcesso") or info["access_key"],
            "nfse_number": info["number"],
            "issued_on": fields.Datetime.now(),
            "nfse_xml": base64.b64encode(nfse),
            "error_message": False,
        })
        alerts = nfse_xml.format_messages(nfse_xml.get_ci(payload, "alertas"))
        self.message_post(body=plaintext2html(_("NFS-e %s authorised.", self.nfse_number) + (f"\n{alerts}" if alerts else "")))
        self._nfse_after_issue()

    def _nfse_rejected(self, message):
        self.write({"state": "error", "error_message": message})
        self.message_post(body=plaintext2html(_("Rejected:\n%s", message)))

    def _next_dps_number(self):
        """DPS numbers are per company and series, sequential; a rejected number may be sent again."""
        self.ensure_one()
        series = self.company_id.nfse_series or "1"
        code = f"l10n_br_nfse_nacional.dps.{series}"
        Sequence = self.env["ir.sequence"].sudo()
        sequence = Sequence.search([("code", "=", code), ("company_id", "=", self.company_id.id)], limit=1)
        if not sequence:
            sequence = Sequence.create({
                "name": _("DPS series %(series)s (%(company)s)", series=series, company=self.company_id.name),
                "code": code, "company_id": self.company_id.id, "implementation": "no_gap", "padding": 1,
            })
        return int(sequence.next_by_id())

    @api.model
    def _nfse_now(self):
        # A minute in the past: SEFIN rejects a time ahead of its own clock (E0008).
        return (fields.Datetime.now() - timedelta(minutes=1)).replace(tzinfo=ZoneInfo("UTC")).astimezone(BRASILIA)

    def _nfse_dps_data(self):
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id.commercial_partner_id
        provider_document = nfse_xml.clean_document(company.vat)
        customer_document = nfse_xml.clean_document(partner.vat)
        address = None
        if nfse_xml.is_ibge_code(partner.nfse_city_ibge) and partner.street and partner.nfse_district:
            address = {
                "city_ibge": partner.nfse_city_ibge,
                "zip": nfse_xml.clean_document(partner.zip),
                "street": partner.street,
                "number": partner.nfse_street_number,
                "complement": partner.street2,
                "district": partner.nfse_district,
            }
        return {
            "id": nfse_xml.dps_id(company.nfse_city_ibge, provider_document, self.dps_series, self.dps_number),
            "environment": self.environment,
            "issued_at": self._nfse_now(),
            "app_version": APP_VERSION,
            "series": self.dps_series,
            "number": self.dps_number,
            "competence": self.date_competence,
            "city_ibge": company.nfse_city_ibge,
            "provider": {
                "document": provider_document,
                "municipal_registration": nfse_xml.clean_document(company.nfse_municipal_registration),
                "simples": company.nfse_simples or "1",
                "simples_regime": company.nfse_simples_regime,
                "special_regime": company.nfse_special_regime,
                "simples_total_rate": company.nfse_simples_total_rate,
                "tax_federal": company.nfse_tax_federal,
                "tax_state": company.nfse_tax_state,
                "tax_municipal": company.nfse_tax_municipal,
            },
            "customer": {
                "document": customer_document,
                "municipal_registration": nfse_xml.clean_document(partner.nfse_municipal_registration),
                "name": partner.name,
                "address": address,
                "phone": partner.phone,
                "email": partner.email,
            },
            "service": {
                "code": self.service_code,
                "municipal_code": self.municipal_service_code,
                "nbs": nfse_xml.clean_document(self.nbs_code),
                "description": self.description,
                "city_ibge": company.nfse_city_ibge,
            },
            "amount": self.amount,
            "iss_rate": self.iss_rate,
            "iss_withheld": self.iss_withheld,
        }

    def _nfse_key_and_certificate(self):
        certificate = self.company_id.sudo().nfse_certificate_id.with_context(bin_size=False)
        key = certificate.private_key_id.with_context(bin_size=False)
        return base64.b64decode(key.pem_key), base64.b64decode(certificate.pem_certificate)

    @contextmanager
    def _nfse_tls_files(self):
        """requests wants the client certificate and key as files: they exist only during the call."""
        key_pem, cert_pem = self._nfse_key_and_certificate()
        with tempfile.TemporaryDirectory(prefix="nfse-") as folder:
            paths = []
            for name, content in (("cert.pem", cert_pem), ("key.pem", key_pem)):
                path = os.path.join(folder, name)
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600), "wb") as handle:
                    handle.write(content)
                paths.append(path)
            yield tuple(paths)

    def _nfse_request(self, method, path, payload=None):
        self.ensure_one()
        url = SEFIN_URLS[self.environment] + path
        with self._nfse_tls_files() as client_cert:
            try:
                response = requests.request(method, url, json=payload, cert=client_cert, timeout=60,
                                            headers={"Accept": "application/json"})
            except requests.RequestException as error:
                _logger.warning("NFS-e request %s %s failed: %s", method, url, error)
                raise UserError(_("The national NFS-e system did not answer (%s). Try again: the note is checked "
                                  "before being sent a second time.", error)) from error
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}
        return response.status_code, data if isinstance(data, dict) else {"erros": data}

    # ------------------------------------------------------------------
    # DANFSe: the auxiliary PDF, drawn from the authorised XML (NT 008).
    # ------------------------------------------------------------------
    def _danfse_values(self):
        self.ensure_one()
        if not self.nfse_xml:
            raise UserError(_("The DANFSe is printed from the authorised note; notes issued on the Emissor "
                              "Nacional are downloaded there."))
        data = nfse_xml.danfse_data(base64.b64decode(self.with_context(bin_size=False).nfse_xml))
        data["public_url"] = PUBLIC_URL.format(key=data["access_key"])
        data["qr"] = self._qr_data_uri(data["public_url"])
        data["cancelled"] = self.state == "cancel"
        return data

    @api.model
    def _qr_data_uri(self, text):
        import qrcode  # noqa: PLC0415 - only the DANFSe needs it

        image = qrcode.make(text, box_size=6, border=1)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

    # ------------------------------------------------------------------
    # Cancellation and hooks for other modules.
    # ------------------------------------------------------------------
    def _cancel(self, reason_code, reason):
        self.ensure_one()
        if self.state != "done":
            raise UserError(_("Only issued notes can be cancelled."))
        if self.mode == "api":
            event = nfse_xml.build_cancel_event({
                "access_key": self.access_key,
                "environment": self.environment,
                "issued_at": self._nfse_now(),
                "app_version": APP_VERSION,
                "author_document": nfse_xml.clean_document(self.company_id.vat),
                "reason_code": reason_code,
                "reason": reason,
            })
            try:
                nfse_xml.validate(event, "pedRegEvento_v1.01.xsd")
            except nfse_xml.NfseXmlError as error:
                raise UserError(_("The cancellation does not match the national layout:\n%s", error)) from error
            key_pem, cert_pem = self._nfse_key_and_certificate()
            signed = nfse_xml.sign(event, key_pem, cert_pem)
            status, payload = self._nfse_request(
                "POST", f"/nfse/{self.access_key}/eventos", {"pedidoRegistroEventoXmlGZipB64": nfse_xml.pack(signed)})
            if status not in (200, 201):
                message = nfse_xml.response_errors(payload) or _("HTTP %s without details.", status)
                raise UserError(_("The cancellation was refused:\n%s", message))
        self.state = "cancel"
        self.message_post(body=plaintext2html(_("NFS-e cancelled: %s", reason)))

    def _nfse_after_issue(self):
        """Hook for the modules that create notes (e.g. mark a billing as invoiced)."""
