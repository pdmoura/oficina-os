"""The NFS-e model is now l10n_br_nfse_nacional.document: the xml ids of this module that carry its name follow.

The model itself, its table and this module's fields on it are renamed by l10n_br_nfse_nacional, updated first.
"""

RENAMES = {
    "nfse_document_view_form": "l10n_br_nfse_nacional_document_view_form",
    "nfse_document_menu_workshop": "l10n_br_nfse_nacional_document_menu_workshop",
}


def migrate(cr, version):
    for old, new in RENAMES.items():
        cr.execute(
            """UPDATE ir_model_data SET name = %s
                WHERE module = 'workshop_os_nfse' AND name = %s
                  AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE module = 'workshop_os_nfse' AND name = %s)""",
            (new, old, new),
        )
