"""Orders copy the company's warranty text when they are created. Orders made during an install, like the demo
yard, were created in English and kept it: where Portuguese is installed they take the company's Portuguese text."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "pt_BR" not in dict(env["res.lang"].get_installed()):
        return
    english = env["res.company"].with_context(lang="en_US")._workshop_default_warranty_text()
    for company in env["res.company"].search([]):
        text = company.with_context(lang="pt_BR").workshop_warranty_text
        if text and text != english:
            env["workshop.order"].search(
                [("company_id", "=", company.id), ("warranty_text", "=", english)]).write({"warranty_text": text})
