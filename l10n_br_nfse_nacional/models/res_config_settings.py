from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    nfse_mode = fields.Selection(related="company_id.nfse_mode", readonly=False)
    nfse_environment = fields.Selection(related="company_id.nfse_environment", readonly=False)
    nfse_city_ibge = fields.Char(related="company_id.nfse_city_ibge", readonly=False)
    nfse_municipal_registration = fields.Char(related="company_id.nfse_municipal_registration", readonly=False)
    nfse_simples = fields.Selection(related="company_id.nfse_simples", readonly=False)
    nfse_simples_regime = fields.Selection(related="company_id.nfse_simples_regime", readonly=False)
    nfse_special_regime = fields.Selection(related="company_id.nfse_special_regime", readonly=False)
    nfse_service_code = fields.Char(related="company_id.nfse_service_code", readonly=False)
    nfse_municipal_service_code = fields.Char(related="company_id.nfse_municipal_service_code", readonly=False)
    nfse_service_nbs = fields.Char(related="company_id.nfse_service_nbs", readonly=False)
    nfse_iss_rate = fields.Float(related="company_id.nfse_iss_rate", readonly=False)
    nfse_series = fields.Char(related="company_id.nfse_series", readonly=False)
    nfse_simples_total_rate = fields.Float(related="company_id.nfse_simples_total_rate", readonly=False)
    nfse_tax_federal = fields.Float(related="company_id.nfse_tax_federal", readonly=False)
    nfse_tax_state = fields.Float(related="company_id.nfse_tax_state", readonly=False)
    nfse_tax_municipal = fields.Float(related="company_id.nfse_tax_municipal", readonly=False)
    nfse_certificate_id = fields.Many2one(related="company_id.nfse_certificate_id", readonly=False)

    def action_nfse_fill_city(self):
        self.company_id.partner_id.action_nfse_fill_address()
