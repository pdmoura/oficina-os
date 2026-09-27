"""Drop the tables left by the cancel wizard's former names (nfse.cancel, nfse.document.cancel).

Odoo keeps the table of a model that left the code, and its ir.model row is only removed after every migration
step has run, so the test is the registry: a name no model uses any more. These only held transient wizard rows.
"""
from odoo import SUPERUSER_ID, api

FORMER = (("nfse.cancel", "nfse_cancel"), ("nfse.document.cancel", "nfse_document_cancel"))


def migrate(cr, version):
    registry = api.Environment(cr, SUPERUSER_ID, {}).registry
    for model, table in FORMER:
        if model not in registry:
            cr.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
