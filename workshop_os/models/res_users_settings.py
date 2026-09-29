from odoo import fields, models


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    workshop_theme = fields.Selection(
        [("dark", "Dark"), ("light", "Light")], string="Workshop theme", default="dark",
        help="Theme of the mechanic app and the yard dashboard, chosen by each user.")
    # Each guided tour opens by itself the first time; finishing or skipping it marks it seen.
    workshop_tour_office_done = fields.Boolean("Office tour seen")
    workshop_tour_app_done = fields.Boolean("Mechanic app tour seen")
