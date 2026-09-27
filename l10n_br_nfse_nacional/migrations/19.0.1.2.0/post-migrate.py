"""Drop the tables left by the cancel wizard's former names (nfse.cancel, nfse.document.cancel).

Odoo keeps the table of a model that left the code; these only ever held transient wizard rows.
"""

FORMER = (("nfse.cancel", "nfse_cancel"), ("nfse.document.cancel", "nfse_document_cancel"))


def migrate(cr, version):
    for model, table in FORMER:
        cr.execute("SELECT 1 FROM ir_model WHERE model = %s", (model,))
        if not cr.fetchone():
            cr.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
