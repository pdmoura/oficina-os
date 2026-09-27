"""XML ids renamed to the Odoo naming guidelines.

Renaming the ir.model.data rows keeps the very same records: users keep their groups, favourites and home
action, and noupdate records (record rules) are not created a second time.
"""

RENAMES = {
    "group_nfse_user": "l10n_br_nfse_nacional_group_user",
    "nfse_document_company_rule": "nfse_document_rule_company",
    "action_nfse_document": "nfse_document_action",
    "action_nfse_settings": "res_config_settings_action",
    "menu_nfse_root": "l10n_br_nfse_nacional_menu_root",
    "menu_nfse_documents": "nfse_document_menu",
    "menu_nfse_settings": "res_config_settings_menu",
    "res_config_settings_view_form_nfse": "res_config_settings_view_form",
    "res_partner_view_form_nfse": "view_partner_form",
}


def migrate(cr, version):
    for old, new in RENAMES.items():
        cr.execute(
            """UPDATE ir_model_data SET name = %s
                WHERE module = %s AND name = %s
                  AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s)""",
            (new, "l10n_br_nfse_nacional", old, "l10n_br_nfse_nacional", new),
        )
