{
    "name": "Workshop Orders: NFS-e",
    "version": "19.0.1.3.1",
    "category": "Services",
    "summary": "Issue the NFS-e of a monthly closing or a work order",
    "author": "Pedro Alves",
    "website": "https://github.com/pdmoura",
    "license": "OPL-1",
    "depends": ["workshop_os", "l10n_br_nfse_nacional"],
    "data": [
        "security/workshop_os_nfse_groups.xml",
        "views/workshop_billing_views.xml",
        "views/workshop_order_views.xml",
        "views/l10n_br_nfse_nacional_document_views.xml",
        "views/workshop_os_nfse_menus.xml",
    ],
    "auto_install": True,
    "installable": True,
}
