{
    "name": "Workshop Orders",
    "version": "19.0.1.0.0",
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
    "depends": ["base", "web", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/brazil_defaults.xml",
        "data/ir_sequence.xml",
        "data/workshop_data.xml",
        "data/checklist_data.xml",
        "report/workshop_order_report.xml",
        "report/workshop_billing_report.xml",
        "views/workshop_stage_views.xml",
        "views/workshop_service_views.xml",
        "views/workshop_vehicle_views.xml",
        "views/workshop_order_views.xml",
        "views/workshop_checklist_views.xml",
        "views/workshop_billing_views.xml",
        "views/res_config_settings_views.xml",
        "views/workshop_app_actions.xml",
        "views/menus.xml",
        "views/portal_templates.xml",
        "views/webclient_templates.xml",
    ],
    "demo": [
        "demo/workshop_demo.xml",
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
