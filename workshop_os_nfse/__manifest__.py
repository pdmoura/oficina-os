{
    "name": "Oficina OS – NFS-e for Work Orders and Monthly Closings",
    "version": "19.0.1.3.1",
    "category": "Services",
    "summary": "Issue the NFS-e of a work order or of a fleet's monthly closing with one click: itemised description, "
               "labour only, never invoiced twice. Free with Oficina OS and NFS-e Nacional Brasil.",
    "author": "Pedro Alves",
    "maintainer": "Pedro Alves",
    "website": "https://github.com/pdmoura/oficina-os",
    "live_test_url": "https://oficina-os.onrender.com",
    "license": "OPL-1",
    "depends": ["workshop_os", "l10n_br_nfse_nacional"],
    "data": [
        "security/workshop_os_nfse_groups.xml",
        "views/workshop_billing_views.xml",
        "views/workshop_order_views.xml",
        "views/l10n_br_nfse_nacional_document_views.xml",
        "views/workshop_os_nfse_menus.xml",
    ],
    "images": ["static/description/banner.png", "static/description/main_screenshot.png"],
    "auto_install": True,
    "installable": True,
}
