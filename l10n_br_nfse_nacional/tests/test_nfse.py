import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger

from ..models import l10n_br_nfse_nacional_document
from ..models.res_partner import cnpj_is_valid
from ..tools import nfse_xml

N = {"n": nfse_xml.NS}
KEY = "31062002211222333000181000000000004226090000000017"


REQUESTS_GET = "odoo.addons.l10n_br_nfse_nacional.models.res_partner.requests.get"


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload
        self.content = json.dumps(payload).encode() if payload is not None else b""
        self.ok = status < 400

    def json(self):
        return self._payload


def fake_nfse(signed_dps, number="42", key=KEY):
    """The authorised note as SEFIN returns it, reduced to what the module reads."""
    dps = etree.fromstring(signed_dps)
    root = etree.Element(f"{{{nfse_xml.NS}}}NFSe", nsmap={None: nfse_xml.NS}, versao="1.01")
    inf = etree.SubElement(root, f"{{{nfse_xml.NS}}}infNFSe", Id=f"NFS{key}")
    for tag, text in (("xLocEmi", "Belo Horizonte"), ("xLocPrestacao", "Belo Horizonte"), ("nNFSe", number),
                      ("xLocIncid", "Belo Horizonte"), ("xTribNac", "Manutenção e conservação de veículos"),
                      ("dhProc", "2026-09-26T10:31:05-03:00")):
        etree.SubElement(inf, f"{{{nfse_xml.NS}}}{tag}").text = text
    emit = etree.SubElement(inf, f"{{{nfse_xml.NS}}}emit")
    etree.SubElement(emit, f"{{{nfse_xml.NS}}}CNPJ").text = "11222333000181"
    etree.SubElement(emit, f"{{{nfse_xml.NS}}}xNome").text = "OFICINA TESTE LTDA"
    values = etree.SubElement(inf, f"{{{nfse_xml.NS}}}valores")
    for tag, text in (("vBC", "1500.00"), ("pAliqAplic", "2.00"), ("vISSQN", "30.00"), ("vLiq", "1500.00")):
        etree.SubElement(values, f"{{{nfse_xml.NS}}}{tag}").text = text
    inf.append(dps)
    return b'<?xml version="1.0" encoding="UTF-8"?>' + etree.tostring(root, encoding="UTF-8")


@tagged("post_install", "-at_install")
class TestNfse(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.company.write({
            "vat": "11.222.333/0001-81", "zip": "30130-010",
            "nfse_simples": "3", "nfse_simples_regime": "1", "nfse_simples_total_rate": 6.0,
            "nfse_service_code": "140101", "nfse_iss_rate": 2.0, "nfse_series": "1",
        })
        cls.company.partner_id.nfse_city_ibge = "3106200"
        cls.customer = cls.env["res.partner"].create({
            "name": "Cliente “Exemplo” Ltda", "is_company": True, "vat": "11.444.777/0001-61",
            "street": "Avenida Afonso Pena", "nfse_street_number": "1000", "street2": "Sala 101",
            "nfse_district": "Centro", "zip": "30130-010", "nfse_city_ibge": "3106200",
            "email": "financeiro@cliente.example.com", "phone": "(31) 99999-0000",
        })
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OFICINA TESTE:11222333000181")])
        now = datetime.now(UTC)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
                .sign(key, hashes.SHA256()))
        pfx = pkcs12.serialize_key_and_certificates(
            b"a1", key, cert, None, serialization.BestAvailableEncryption(b"secret"))
        cls.certificate = cls.env["certificate.certificate"].create({
            "name": "A1 test", "content": base64.b64encode(pfx), "pkcs12_password": "secret",
            "company_id": cls.company.id,
        })

    def _note(self, **values):
        return self.env["l10n_br_nfse_nacional.document"].create({
            "partner_id": self.customer.id, "amount": 1500, "mode": "api", "environment": "2",
            "description": "Revisão do alternador — troca de escovas\nTeste de carga 😀",
            **values,
        })

    def _dps(self, note):
        note.write({"dps_series": "1", "dps_number": 7})
        return nfse_xml.build_dps(note._nfse_dps_data())

    def test_dps_follows_the_national_layout(self):
        root = self._dps(self._note())
        nfse_xml.validate(root)
        inf = root.find("n:infDPS", N)
        self.assertEqual(inf.get("Id"), "DPS3106200211222333000181" + "00001" + "000000000000007")
        self.assertEqual(root.get("versao"), "1.01")
        self.assertIsNone(inf.find("n:prest/n:xNome", N), "the provider's name comes from the registry (E0121)")
        self.assertIsNone(inf.find("n:prest/n:end", N), "and so does its address (E0128)")
        self.assertEqual(inf.findtext("n:prest/n:regTrib/n:regApTribSN", namespaces=N), "1")
        self.assertIsNone(inf.find(".//n:pAliq", N), "ME/EPP without withholding sends no rate (E0625)")
        self.assertEqual(inf.findtext(".//n:pTotTribSN", namespaces=N), "6.00")
        self.assertEqual(inf.findtext("n:toma/n:end/n:endNac/n:cMun", namespaces=N), "3106200")
        self.assertEqual(inf.findtext("n:toma/n:xNome", namespaces=N), 'Cliente "Exemplo" Ltda')
        self.assertEqual(inf.findtext(".//n:xDescServ", namespaces=N),
                         "Revisão do alternador - troca de escovas\nTeste de carga", "Latin-1 only (E1235)")
        self.assertEqual(inf.findtext(".//n:vServ", namespaces=N), "1500.00")
        self.assertRegex(inf.findtext("n:dhEmi", namespaces=N), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d-03:00$")

    def test_rate_goes_only_with_withholding(self):
        root = self._dps(self._note(iss_withheld=True, iss_rate=2.5))
        nfse_xml.validate(root)
        self.assertEqual(root.findtext(".//n:pAliq", namespaces=N), "2.50")
        self.assertEqual(root.findtext(".//n:tpRetISSQN", namespaces=N), "2")

    def test_regimes_estimate_taxes_their_own_way(self):
        self.company.nfse_simples = "2"
        root = self._dps(self._note())
        nfse_xml.validate(root)
        self.assertEqual(root.findtext(".//n:indTotTrib", namespaces=N), "0")
        self.assertIsNone(root.find(".//n:regApTribSN", N), "only ME/EPP report the Simples regime (E0162)")
        self.company.write({"nfse_simples": "1", "nfse_special_regime": "0", "nfse_tax_federal": 13.45})
        root = self._dps(self._note())
        nfse_xml.validate(root)
        self.assertEqual(root.findtext(".//n:pTotTribFed", namespaces=N), "13.45")

    def test_signature(self):
        self.company.nfse_certificate_id = self.certificate
        note = self._note()
        signed = nfse_xml.sign(self._dps(note), *note._nfse_key_and_certificate())
        self.assertTrue(signed.startswith(b'<?xml version="1.0" encoding="UTF-8"?><DPS xmlns='))
        self.assertTrue(nfse_xml.verify(signed))
        nfse_xml.validate(etree.fromstring(signed))
        self.assertFalse(nfse_xml.verify(signed.replace(b"<vServ>1500.00", b"<vServ>1.00")))

    def test_problems_are_listed_before_sending(self):
        self.company.nfse_certificate_id = self.certificate
        note = self._note()
        self.assertFalse(note.issues)
        self.customer.write({"nfse_district": False, "vat": False})
        note.invalidate_recordset(["issues"])
        self.assertIn("CNPJ or CPF", note.issues)
        self.company.nfse_certificate_id = False
        with self.assertRaises(UserError):
            note.action_issue()

    def _route(self, answers, calls):
        def request(method, url, json=None, **kwargs):
            calls.append((method, url, json))
            for (m, fragment), answer in answers.items():
                if m == method and fragment in url:
                    return answer(json) if callable(answer) else answer
            return FakeResponse(404, {})
        return patch.object(l10n_br_nfse_nacional_document.requests, "request", side_effect=request)

    def test_issue_through_the_api(self):
        self.company.nfse_certificate_id = self.certificate
        note = self._note()
        calls = []
        success = lambda payload: FakeResponse(201, {  # noqa: E731
            "tipoAmbiente": 2, "chaveAcesso": KEY, "idDps": "x",
            "nfseXmlGZipB64": nfse_xml.pack(fake_nfse(nfse_xml.unpack(payload["dpsXmlGZipB64"]))),
        })
        with self._route({("POST", "/SefinNacional/nfse"): success}, calls):
            note.action_issue()
        self.assertEqual(note.state, "done")
        self.assertEqual((note.nfse_number, note.access_key), ("42", KEY))
        self.assertEqual(calls[0][1], "https://sefin.producaorestrita.nfse.gov.br/SefinNacional/nfse")
        sent = nfse_xml.unpack(calls[0][2]["dpsXmlGZipB64"])
        self.assertTrue(nfse_xml.verify(sent))

        html, _type = self.env["ir.actions.report"]._render_qweb_html("l10n_br_nfse_nacional.report_danfse", note.ids)
        self.assertIn(KEY.encode(), html)
        self.assertIn("NFS-e SEM VALIDADE JURÍDICA".encode(), html)
        self.assertIn(b"R$ 1.500,00", html)
        self.assertIn("Tributos aproximados (Simples Nacional): 6,00%".encode(), html)

        with self._route({("POST", f"/nfse/{KEY}/eventos"): FakeResponse(201, {"eventoXmlGZipB64": "x"})}, calls):
            note._cancel("1", "Valor do serviço informado errado")
        self.assertEqual(note.state, "cancel")
        event = etree.fromstring(nfse_xml.unpack(calls[-1][2]["pedidoRegistroEventoXmlGZipB64"]))
        self.assertEqual(event.find("n:infPedReg", N).get("Id"), f"PRE{KEY}101101")
        nfse_xml.validate(event, "pedRegEvento_v1.01.xsd")

    def test_rejection_is_readable(self):
        self.company.nfse_certificate_id = self.certificate
        note = self._note()
        refusal = FakeResponse(400, {"Erros": [{"Codigo": "E0310", "Descricao": "Código de tributação inexistente."}]})
        with self._route({("POST", "/SefinNacional/nfse"): refusal}, []):
            action = note.action_issue()
        self.assertEqual(note.state, "error")
        self.assertEqual(note.error_message, "E0310 - Código de tributação inexistente.")
        self.assertEqual(action["params"]["type"], "danger")
        note.action_reset_draft()
        self.assertEqual(note.state, "draft")

    def test_lost_answer_is_recovered_instead_of_duplicated(self):
        self.company.nfse_certificate_id = self.certificate
        note = self._note()
        sent = {}

        def duplicate(payload):
            sent["dps"] = nfse_xml.unpack(payload["dpsXmlGZipB64"])
            return FakeResponse(400, {"erros": [{"codigo": "E0014", "descricao": "DPS já utilizada"}]})

        answers = {
            ("POST", "/SefinNacional/nfse"): duplicate,
            ("HEAD", "/dps/"): FakeResponse(200),
            ("GET", "/dps/"): FakeResponse(200, {"chaveAcesso": KEY}),
            ("GET", f"/nfse/{KEY}"): lambda _p: FakeResponse(200, {"nfseXmlGZipB64": nfse_xml.pack(fake_nfse(sent["dps"]))}),
        }
        with self._route(answers, []):
            note.action_issue()
        self.assertEqual(note.state, "done")
        self.assertEqual(note.nfse_number, "42")

    def test_assisted_mode(self):
        note = self._note(mode="assisted")
        self.assertEqual(note.assist_partner_document, "11444777000161")
        self.assertEqual(note.assist_amount, "1.500,00")
        self.assertEqual(note.assist_service_code, "14.01.01")
        note.access_key = "123"
        with self.assertRaises(UserError):
            note.action_register_issued()
        note.access_key = KEY
        note.action_register_issued()
        self.assertEqual((note.state, note.nfse_number), ("done", "42"))
        with self.assertRaises(UserError):
            note.unlink()

    def test_company_filled_from_its_cnpj(self):
        # Typing the CNPJ brings the register's record; the new CEP then brings the names with their accents.
        record = {"razao_social": "TRANSPORTES DA SERRA LTDA", "descricao_tipo_de_logradouro": "RUA",
                  "logradouro": "DAS FLORES", "numero": "120", "complemento": "GALPAO 2", "bairro": "SETOR SUL",
                  "cep": "70040010", "municipio": "BRASILIA", "uf": "DF", "codigo_municipio_ibge": 5300108,
                  "ddd_telefone_1": "6134939002", "email": "FROTA@SERRA.COM.BR", "descricao_situacao_cadastral": "ATIVA"}
        cep = {"cep": "70040-010", "logradouro": "SBS Quadra 1", "bairro": "Asa Sul", "localidade": "Brasília",
               "uf": "DF", "ibge": "5300108"}

        def answer(url, timeout):
            return FakeResponse(200, cep if "viacep" in url else record)

        with patch(REQUESTS_GET, side_effect=answer):
            form = Form(self.env["res.partner"])
            form.vat = "11.444.777/0001-61"
            partner = form.save()
        self.assertEqual((partner.name, partner.is_company), ("Transportes da Serra Ltda", True))
        self.assertEqual((partner.street, partner.nfse_street_number, partner.street2), ("SBS Quadra 1", "120", "Galpao 2"))
        self.assertEqual((partner.nfse_district, partner.city, partner.state_id.code, partner.nfse_city_ibge),
                         ("Asa Sul", "Brasília", "DF", "5300108"))
        self.assertEqual((partner.zip, partner.email), ("70040-010", "frota@serra.com.br"))
        self.assertIn("3493-9002", partner.phone)

        # A name typed first stays, and everything stays editable after the fill.
        with patch(REQUESTS_GET, side_effect=answer):
            form = Form(self.env["res.partner"])
            form.name = "Serra"
            form.vat = "11444777000161"
            form.nfse_street_number = "122"
        self.assertEqual((form.name, form.nfse_street_number), ("Serra", "122"))

        # An inactive company is filled with a warning; an unknown CNPJ or a service down only warns.
        with patch(REQUESTS_GET, side_effect=lambda url, timeout: FakeResponse(
                200, cep if "viacep" in url else dict(record, descricao_situacao_cadastral="BAIXADA"))), \
                mute_logger("odoo.tests.form.onchange"):
            form = Form(self.env["res.partner"])
            form.vat = "11444777000161"
        self.assertEqual(form.name, "Transportes da Serra Ltda")
        with patch(REQUESTS_GET, return_value=FakeResponse(404, {"message": "not found"})), \
                mute_logger("odoo.tests.form.onchange"):
            form = Form(self.env["res.partner"])
            form.vat = "11444777000161"
        self.assertFalse(form.name)

        # The CNPJ field is this lookup's: Odoo's paid autocomplete keeps the name only.
        arch = etree.fromstring(self.env["res.partner"].get_view(view_type="form")["arch"])
        self.assertFalse(arch.xpath("//field[@name='vat'][@widget='field_partner_autocomplete']"))
        self.assertTrue(arch.xpath("//field[@name='name'][@widget='field_partner_autocomplete']"))

        # Only valid CNPJs are looked up, numeric or alphanumeric (July 2026 format).
        self.assertTrue(cnpj_is_valid("12ABC34501DE35"))
        self.assertFalse(cnpj_is_valid("11444777000162"))
        self.assertFalse(cnpj_is_valid("00000000000000"))
        with patch(REQUESTS_GET) as get:
            Form(self.env["res.partner"]).vat = "11444777000162"
        get.assert_not_called()

    def test_address_from_cep(self):
        partner = self.env["res.partner"].create({"name": "Frota Nova", "zip": "70040010"})
        answer = FakeResponse(200, {"cep": "70040-010", "logradouro": "SBS Quadra 1", "bairro": "Asa Sul",
                                    "localidade": "Brasília", "uf": "DF", "ibge": "5300108"})
        with patch(REQUESTS_GET, return_value=answer):
            partner.action_nfse_fill_address()
        self.assertEqual((partner.nfse_city_ibge, partner.nfse_district, partner.city), ("5300108", "Asa Sul", "Brasília"))
        self.assertEqual(partner.state_id.code, "DF")
        self.assertEqual(partner.zip, "70040-010")
