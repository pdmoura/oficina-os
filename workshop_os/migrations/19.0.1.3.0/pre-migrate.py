"""XML ids renamed to the Odoo naming guidelines.

Renaming the ir.model.data rows keeps the very same records: users keep their groups, favourites and home
action, and noupdate records (record rules) are not created a second time.

The app actions also keep their old id as an alias: installed phone apps and bookmarks open them
by that id.
"""

RENAMES = {
    "group_workshop_user": "workshop_os_group_user",
    "group_workshop_manager": "workshop_os_group_manager",
    "workshop_order_company_rule": "workshop_order_rule_company",
    "workshop_vehicle_company_rule": "workshop_vehicle_rule_company",
    "workshop_billing_company_rule": "workshop_billing_rule_company",
    "action_workshop_order_line_analysis": "workshop_order_line_action_analysis",
    "action_workshop_order": "workshop_order_action",
    "action_workshop_stage": "workshop_stage_action",
    "action_workshop_location": "workshop_location_action",
    "action_workshop_sector": "workshop_sector_action",
    "action_workshop_service": "workshop_service_action",
    "action_workshop_vehicle": "workshop_vehicle_action",
    "action_workshop_customers": "res_partner_action_workshop_customer",
    "action_workshop_checklist_template": "workshop_checklist_template_action",
    "action_workshop_billing": "workshop_billing_action",
    "action_workshop_settings": "res_config_settings_action",
    "action_mechanic_app": "workshop_order_action_mechanic_app",
    "action_workshop_dashboard": "workshop_order_action_dashboard",
    "action_workshop_home": "workshop_order_action_home",
    "menu_workshop_root": "workshop_os_menu_root",
    "menu_workshop_dashboard": "workshop_order_menu_dashboard",
    "menu_workshop_orders": "workshop_order_menu",
    "menu_workshop_app": "workshop_order_menu_mechanic_app",
    "menu_workshop_customers": "workshop_os_menu_customers",
    "menu_workshop_vehicles": "workshop_vehicle_menu",
    "menu_workshop_partners": "res_partner_menu_workshop_customer",
    "menu_workshop_billing_root": "workshop_os_menu_billing",
    "menu_workshop_billing": "workshop_billing_menu",
    "menu_workshop_analysis": "workshop_order_line_menu_analysis",
    "menu_workshop_config": "workshop_os_menu_config",
    "menu_workshop_settings": "res_config_settings_menu",
    "menu_workshop_services": "workshop_service_menu",
    "menu_workshop_checklists": "workshop_checklist_template_menu",
    "menu_workshop_stages": "workshop_stage_menu",
    "menu_workshop_locations": "workshop_location_menu",
    "menu_workshop_sectors": "workshop_sector_menu",
    "res_config_settings_view_form_workshop": "res_config_settings_view_form",
    "res_partner_view_form_workshop": "view_partner_form",
    "webclient_bootstrap_app_icon": "webclient_bootstrap",
    "login_layout_brand": "login_layout",
    "layout_tab_brand": "layout",
}
# Opened from outside Odoo by their old id.
ALIASES = ["action_mechanic_app", "action_workshop_dashboard"]


def migrate(cr, version):
    for old, new in RENAMES.items():
        cr.execute(
            """UPDATE ir_model_data SET name = %s
                WHERE module = %s AND name = %s
                  AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s)""",
            (new, "workshop_os", old, "workshop_os", new),
        )
    for old in ALIASES:
        cr.execute(
            """INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_uid, write_uid, create_date, write_date)
               SELECT module, %s, model, res_id, TRUE, 1, 1, now(), now()
                 FROM ir_model_data WHERE module = %s AND name = %s
               ON CONFLICT DO NOTHING""",
            (old, "workshop_os", RENAMES[old]),
        )
