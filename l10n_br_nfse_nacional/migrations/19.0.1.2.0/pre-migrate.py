"""nfse.document becomes l10n_br_nfse_nacional.document (model names carry the module prefix).

The table, its metadata and every place that stores the model's name are renamed in place, so the notes keep
their ids, chatter, followers, activities and XML files. The cancel wizard is transient: the registry creates
the new one and drops the old at the end of the update.
"""

OLD_MODEL, NEW_MODEL = "nfse.document", "l10n_br_nfse_nacional.document"
OLD_TABLE, NEW_TABLE = "nfse_document", "l10n_br_nfse_nacional_document"

# (table, column) holding a model name, in core and in apps that may be installed next to this one.
MODEL_NAME_COLUMNS = [
    ("ir_model_data", "model"),
    ("ir_model_fields", "relation"),
    ("ir_attachment", "res_model"),
    ("mail_message", "model"),
    ("mail_followers", "res_model"),
    ("mail_activity", "res_model"),
    ("mail_activity_type", "res_model"),
    ("mail_message_subtype", "res_model"),
    ("mail_template", "model"),
    ("ir_act_window", "res_model"),
    ("ir_act_report_xml", "model"),
    ("ir_act_server", "model_name"),
    ("ir_ui_view", "model"),
    ("ir_filters", "model_id"),
    ("ir_embedded_actions", "parent_res_model"),
    ("ir_exports", "resource"),
    ("mail_activity_plan", "res_model"),
    ("mail_compose_message", "model"),
    ("mail_scheduled_message", "model"),
    ("sms_template", "model"),
    ("rating_rating", "res_model"),
]
XMLID_RENAMES = {
    "nfse_document_view_form": "l10n_br_nfse_nacional_document_view_form",
    "nfse_document_view_list": "l10n_br_nfse_nacional_document_view_list",
    "nfse_document_view_search": "l10n_br_nfse_nacional_document_view_search",
    "nfse_document_action": "l10n_br_nfse_nacional_document_action",
    "nfse_document_menu": "l10n_br_nfse_nacional_document_menu",
    "nfse_document_rule_company": "l10n_br_nfse_nacional_document_rule_company",
    "access_nfse_document_user": "access_l10n_br_nfse_nacional_document_user",
}


def _column_exists(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s", (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    cr.execute("SELECT id FROM ir_model WHERE model = %s", (OLD_MODEL,))
    row = cr.fetchone()
    if not row:
        return
    model_id = row[0]

    # The table, its id sequence, and the constraints and indexes named after it.
    cr.execute(f'ALTER TABLE "{OLD_TABLE}" RENAME TO "{NEW_TABLE}"')
    cr.execute(f'ALTER SEQUENCE IF EXISTS "{OLD_TABLE}_id_seq" RENAME TO "{NEW_TABLE}_id_seq"')
    cr.execute("SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass AND conname LIKE %s",
               (NEW_TABLE, OLD_TABLE + "%"))
    for (constraint,) in cr.fetchall():  # a unique or primary key constraint renames its index with it
        cr.execute(f'ALTER TABLE "{NEW_TABLE}" RENAME CONSTRAINT "{constraint}" TO "{NEW_TABLE + constraint[len(OLD_TABLE):]}"')
    cr.execute("SELECT indexname FROM pg_indexes WHERE tablename = %s AND indexname LIKE %s", (NEW_TABLE, OLD_TABLE + "%"))
    for (index,) in cr.fetchall():
        cr.execute(f'ALTER INDEX "{index}" RENAME TO "{NEW_TABLE + index[len(OLD_TABLE):]}"')
    cr.execute("UPDATE ir_model_constraint SET name = %s || substr(name, %s) WHERE model = %s AND name LIKE %s",
               (NEW_TABLE, len(OLD_TABLE) + 1, model_id, OLD_TABLE + "%"))

    # Metadata: the model, its fields (from any module) and their xml ids.
    cr.execute("UPDATE ir_model SET model = %s WHERE model = %s", (NEW_MODEL, OLD_MODEL))
    cr.execute("UPDATE ir_model_fields SET model = %s WHERE model = %s", (NEW_MODEL, OLD_MODEL))
    cr.execute("UPDATE ir_model_data SET name = %s WHERE model = 'ir.model' AND name = %s",
               (f"model_{NEW_TABLE}", f"model_{OLD_TABLE}"))
    for prefix in ("field_", "selection__"):  # field_nfse_document__state, selection__nfse_document__state__draft
        old, new = f"{prefix}{OLD_TABLE}__", f"{prefix}{NEW_TABLE}__"
        cr.execute("UPDATE ir_model_data SET name = %s || substr(name, %s) WHERE starts_with(name, %s)",
                   (new, len(old) + 1, old))

    # Everything that points at the model by its name.
    for table, column in MODEL_NAME_COLUMNS:
        if _column_exists(cr, table, column):
            cr.execute(f'UPDATE "{table}" SET "{column}" = %s WHERE "{column}" = %s', (NEW_MODEL, OLD_MODEL))

    # XML ids derived from the model name.
    for old, new in XMLID_RENAMES.items():
        cr.execute(
            """UPDATE ir_model_data SET name = %s
                WHERE module = 'l10n_br_nfse_nacional' AND name = %s
                  AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE module = 'l10n_br_nfse_nacional' AND name = %s)""",
            (new, old, new),
        )
