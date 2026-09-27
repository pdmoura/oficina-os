from odoo import fields, models

SIMPLES_OPTIONS = [
    ("1", "Not opted in"),
    ("2", "MEI"),
    ("3", "ME/EPP"),
]
SIMPLES_REGIME = [
    ("1", "Federal and municipal taxes paid through the Simples Nacional"),
    ("2", "Federal taxes through the Simples, ISSQN apart"),
    ("3", "Federal and municipal taxes apart from the Simples"),
]
SPECIAL_REGIME = [
    ("0", "None"),
    ("1", "Cooperative act"),
    ("2", "Estimate"),
    ("3", "Municipal microenterprise"),
    ("4", "Notary or registrar"),
    ("5", "Self-employed professional"),
    ("6", "Society of professionals"),
]



class ResCompany(models.Model):
    _inherit = "res.company"

    nfse_mode = fields.Selection(
        [("assisted", "Assisted (Emissor Nacional website)"), ("api", "Direct (API with A1 certificate)")],
        string="NFS-e emission", default="assisted", required=True,
        help="Assisted: the app prepares every field and you issue the note on www.nfse.gov.br. "
             "Direct: the note is signed with the company's certificate and sent straight to the national system.",
    )
    nfse_environment = fields.Selection(
        [("2", "Test (produção restrita)"), ("1", "Production")],
        string="NFS-e environment", default="2", required=True,
    )
    nfse_city_ibge = fields.Char(related="partner_id.nfse_city_ibge", readonly=False)
    nfse_municipal_registration = fields.Char(
        "Municipal registration (IM)",
        help="Fill only if the city registered it in the national taxpayer registry (CNC); "
             "otherwise the note is rejected (E0120).")
    nfse_simples = fields.Selection(SIMPLES_OPTIONS, string="Simples Nacional", default="3")
    nfse_simples_regime = fields.Selection(SIMPLES_REGIME, string="Simples Nacional regime", default="1")
    nfse_special_regime = fields.Selection(SPECIAL_REGIME, string="Special tax regime", default="0")
    nfse_service_code = fields.Char(
        "National service code", size=6, default="140101",
        help="cTribNac: 6 digits from the national list (LC 116). 14.01.01 covers repair and maintenance of vehicles.",
    )
    nfse_municipal_service_code = fields.Char("Municipal service code", size=3)
    nfse_service_nbs = fields.Char("NBS code", size=9)
    nfse_iss_rate = fields.Float("ISS rate (%)", digits=(5, 2),
                                 help="Printed on the note only when the customer withholds the ISS; "
                                      "otherwise the national system applies the city's rate.")
    nfse_simples_total_rate = fields.Float(
        "Approximate Simples Nacional rate (%)", digits=(5, 2),
        help="Approximate share of taxes in the price for ME/EPP (Law 12.741): usually the effective "
             "rate of the Simples Nacional bracket.")
    nfse_tax_federal = fields.Float("Approximate federal taxes (%)", digits=(5, 2))
    nfse_tax_state = fields.Float("Approximate state taxes (%)", digits=(5, 2))
    nfse_tax_municipal = fields.Float("Approximate municipal taxes (%)", digits=(5, 2))
    nfse_series = fields.Char("DPS series", size=5, default="1")
    nfse_certificate_id = fields.Many2one(
        "certificate.certificate", string="A1 certificate",
        domain="[('company_id', 'in', [id, False])]",
        help="ICP-Brasil e-CNPJ certificate (.pfx) used to sign the DPS and authenticate on the national API.",
    )
