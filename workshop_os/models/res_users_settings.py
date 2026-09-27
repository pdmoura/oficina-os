from odoo import fields, models


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    workshop_theme = fields.Selection(
        [("dark", "Dark"), ("light", "Light")], string="Workshop theme", default="dark",
        help="Theme of the mechanic app and the yard dashboard, chosen by each user.")
