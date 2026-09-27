"""XML ids renamed to the Odoo naming guidelines.

Renaming the ir.model.data rows keeps the very same records: users keep their groups, favourites and home
action, and noupdate records (record rules) are not created a second time.
"""

RENAMES = {
    "workshop_billing_view_form_nfse": "workshop_billing_view_form",
    "workshop_billing_view_list_nfse": "workshop_billing_view_list",
    "workshop_order_view_form_nfse": "workshop_order_view_form",
    "nfse_document_view_form_workshop": "nfse_document_view_form",
    "menu_workshop_nfse": "nfse_document_menu_workshop",
}


def migrate(cr, version):
    for old, new in RENAMES.items():
        cr.execute(
            """UPDATE ir_model_data SET name = %s
                WHERE module = %s AND name = %s
                  AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s)""",
            (new, "workshop_os_nfse", old, "workshop_os_nfse", new),
        )
