{
    "name": "NFS-e Nacional Brasil – Nota Fiscal de Serviço Eletrônica (NFSe) | Emissor Nacional",
    "version": "19.0.1.3.0",
    "category": "Accounting/Localizations",
    "summary": "Brazilian service invoices through the national system: assisted mode without a certificate or direct "
               "API emission with an A1 certificate, DANFSe, cancellation, customers filled from the CNPJ and the CEP. "
               "Emissão de NFS-e padrão nacional.",
    "description": """
Issue NFS-e through the Sistema Nacional NFS-e (www.nfse.gov.br).

* Assisted mode: no certificate needed. Every field the Emissor Nacional asks for is ready to copy,
  and the access key of the issued note is recorded back.
* API mode: the DPS is built, validated, signed with the company's ICP-Brasil A1 certificate and sent
  to SEFIN Nacional over mutual TLS; the authorised NFS-e XML is kept on the document.
* The DPS is checked against the official XSD (layout 1.01) before it leaves, with readable messages.
* DANFSe drawn from the authorised XML (NT 008), with the QR code of the public consultation.
* Test environment (produção restrita) and production, cancellation event, recovery of lost answers.
""",
    "author": "Pedro Alves",
    "maintainer": "Pedro Alves",
    "website": "https://github.com/pdmoura/oficina-os",
    "live_test_url": "https://oficina-os.onrender.com",
    "license": "OPL-1",
    "price": 199.0,
    "currency": "EUR",
    # partner_autocomplete: so that _get_view runs after its own and can take its widget off the CNPJ field.
    "depends": ["base", "mail", "certificate", "partner_autocomplete"],
    "external_dependencies": {"python": ["cryptography", "lxml", "qrcode", "requests"]},
    "data": [
        "security/l10n_br_nfse_nacional_groups.xml",
        "security/ir.model.access.csv",
        "security/l10n_br_nfse_nacional_document_security.xml",
        "report/l10n_br_nfse_nacional_document_reports.xml",
        "report/l10n_br_nfse_nacional_document_templates.xml",
        "views/l10n_br_nfse_nacional_document_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "wizard/l10n_br_nfse_nacional_document_cancel_views.xml",
        "views/l10n_br_nfse_nacional_menus.xml",
    ],
    "images": ["static/description/banner.png", "static/description/main_screenshot.png"],
    "installable": True,
    "application": False,
}
