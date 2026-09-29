{
    # The Odoo Apps listing is found by these words: the brand first, then what buyers search for.
    "name": "Oficina OS – Truck & Fleet Workshop | Vehicle Repair Orders | Mechanic App",
    "version": "19.0.1.10.0",
    "category": "Services/Workshop",
    "summary": "Work orders for truck and fleet workshops: plate-first mechanic mobile app, customer approval by link "
               "with signature, photos, checklists, labour and parts, monthly billing per fleet. English and Brazilian "
               "Portuguese.",
    "description": """
Oficina OS
==========
Built for workshops that maintain fleets (trucks, vans, buses): the mechanic opens and runs orders from a phone,
the office controls the yard, approvals and the monthly closing per customer.

* Plate-first mobile app (full screen, installable) for mechanics
* Stages, locations (bays) and sectors, with time spent in each stage
* Service and parts catalogue with prices and labour hours, per-line approval
* Arrival and delivery checklists, photos by moment, in the database or on Cloudinary
* Customer approval by link, with signature
* Work order and monthly PDF reports with the company's brand
* Monthly closing per fleet customer, ready for NFS-e
""",
    "author": "Pedro Alves",
    "maintainer": "Pedro Alves",
    "website": "https://github.com/pdmoura/oficina-os",
    "live_test_url": "https://oficina-os.onrender.com",
    "license": "OPL-1",
    "price": 199.0,
    "currency": "EUR",
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
            "workshop_os/static/src/tour/**/*",
        ],
        "workshop_os.assets_public": [
            "workshop_os/static/src/scss/tokens.scss",
            "workshop_os/static/src/public/**/*",
        ],
    },
    "images": ["static/description/banner.png", "static/description/main_screenshot.png"],
    "installable": True,
    "application": True,
}
