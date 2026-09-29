{
    "name": "Workshop Orders",
    "version": "19.0.1.5.1",
    "category": "Services/Workshop",
    "summary": "Work orders for fleet workshops: plate-first mobile app for mechanics, kanban, checklists, photos, "
               "customer approval by link and monthly billing per fleet",
    "description": """
Workshop Orders
===============
Built for workshops that maintain fleets (trucks, vans, buses): the mechanic opens and runs orders from a phone,
the office controls the yard, approvals and the monthly closing per customer.

* Plate-first mobile app (full screen, installable) for mechanics
* Stages, locations (bays) and sectors, with time spent in each stage
* Service catalog with prices and labour hours, per-line approval
* Entry and exit checklists, photos stored on Cloudinary
* Customer approval by link, with optional signature
* Work order and monthly PDF reports with the company logo
* Monthly closing per fleet customer, ready for NFS-e
""",
    "author": "Pedro Alves",
    "website": "https://github.com/pdmoura/oficina-os",
    "license": "OPL-1",
    "depends": ["base", "web", "mail", "mail_bot", "auth_signup"],
    "data": [
        "security/workshop_os_groups.xml",
        "security/ir.model.access.csv",
        "security/workshop_order_security.xml",
        "security/workshop_vehicle_security.xml",
        "security/workshop_billing_security.xml",
        "security/workshop_service_security.xml",
        "data/res_company_data.xml",
        "data/ir_asset_data.xml",
        "data/ir_sequence_data.xml",
        "data/workshop_stage_data.xml",
        "data/workshop_location_data.xml",
        "data/workshop_sector_data.xml",
        "data/workshop_checklist_template_data.xml",
        "report/workshop_order_reports.xml",
        "report/workshop_order_templates.xml",
        "report/workshop_billing_reports.xml",
        "report/workshop_billing_templates.xml",
        "views/workshop_stage_views.xml",
        "views/workshop_location_views.xml",
        "views/workshop_sector_views.xml",
        "views/workshop_service_views.xml",
        "views/workshop_vehicle_views.xml",
        "views/res_partner_views.xml",
        "views/workshop_order_views.xml",
        "views/workshop_checklist_template_views.xml",
        "views/workshop_billing_views.xml",
        "views/res_config_settings_views.xml",
        "views/workshop_os_menus.xml",
        "views/workshop_order_templates.xml",
        "views/webclient_templates.xml",
        "wizard/workshop_order_print_views.xml",
    ],
    "demo": [
        "demo/workshop_order_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "workshop_os/static/src/scss/tokens.scss",
            "workshop_os/static/src/app/**/*",
            "workshop_os/static/src/backend/**/*",
        ],
        "workshop_os.assets_public": [
            "workshop_os/static/src/scss/tokens.scss",
            "workshop_os/static/src/public/**/*",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
}
