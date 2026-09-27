"""Starting data and default texts are now written in English and translated to Portuguese.

Records created by earlier versions still hold the Portuguese text as their source: where it is untouched, the
English text becomes the source and the Portuguese one its translation. Anything the workshop edited stays as is.
"""

# "table|xml id|field" -> [English, Portuguese]
DATA = {
    "workshop_stage|stage_office|name": [
        "Office",
        "Escritório"
    ],
    "workshop_stage|stage_office|description": [
        "Waiting for a quote or approval",
        "Aguardando orçamento ou aprovação"
    ],
    "workshop_stage|stage_parts|name": [
        "Waiting for parts",
        "Aguardando peças"
    ],
    "workshop_stage|stage_queue|name": [
        "Queued",
        "Na fila"
    ],
    "workshop_stage|stage_queue|description": [
        "Approved, waiting for a mechanic",
        "Aprovado, esperando mecânico"
    ],
    "workshop_stage|stage_working|name": [
        "In progress",
        "Em serviço"
    ],
    "workshop_stage|stage_stopped|name": [
        "On hold",
        "Serviço parado"
    ],
    "workshop_stage|stage_test|name": [
        "Testing / check",
        "Teste / conferência"
    ],
    "workshop_location|location_bay_1|name": [
        "Bay 1",
        "Box 1"
    ],
    "workshop_location|location_bay_2|name": [
        "Bay 2",
        "Box 2"
    ],
    "workshop_location|location_bay_3|name": [
        "Bay 3",
        "Box 3"
    ],
    "workshop_location|location_yard|name": [
        "Yard",
        "Pátio"
    ],
    "workshop_location|location_road|name": [
        "Road test",
        "Em teste na rua"
    ],
    "workshop_location|location_customer|name": [
        "At the customer's",
        "No cliente"
    ],
    "workshop_sector|sector_electric|name": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_sector|sector_ac|name": [
        "Air conditioning",
        "Ar condicionado"
    ],
    "workshop_sector|sector_injection|name": [
        "Electronic fuel injection",
        "Injeção eletrônica"
    ],
    "workshop_sector|sector_diesel|name": [
        "Diesel",
        "Diesel"
    ],
    "workshop_sector|sector_steering|name": [
        "Power steering",
        "Direção hidráulica"
    ],
    "workshop_sector|sector_third|name": [
        "Third-party services",
        "Serviços de terceiros"
    ],
    "workshop_sector|sector_misc|name": [
        "Other",
        "Diversos"
    ],
    "workshop_checklist_template|checklist_truck_entry|name": [
        "Truck arrival",
        "Entrada do caminhão"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_01|name": [
        "Dashboard with no warning lights",
        "Painel sem luzes de alerta"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_01|section": [
        "Cab",
        "Cabine"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_02|name": [
        "Tachograph working",
        "Tacógrafo funcionando"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_02|section": [
        "Cab",
        "Cabine"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_03|name": [
        "Fuel level noted",
        "Nível de combustível anotado"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_03|section": [
        "Cab",
        "Cabine"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_04|name": [
        "Driver's belongings checked",
        "Pertences do motorista conferidos"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_04|section": [
        "Cab",
        "Cabine"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_10|name": [
        "Low beams (left and right)",
        "Farol baixo (esquerdo e direito)"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_10|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_11|name": [
        "High beams",
        "Farol alto"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_11|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_12|name": [
        "Tail lights",
        "Lanternas traseiras"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_12|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_13|name": [
        "Turn signals and hazard lights",
        "Setas e pisca-alerta"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_13|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_14|name": [
        "Brake lights",
        "Luz de freio"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_14|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_15|name": [
        "Reversing light and alarm",
        "Luz e alarme de ré"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_15|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_16|name": [
        "Horn",
        "Buzina"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_16|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_17|name": [
        "Wipers and washers",
        "Limpador e esguicho"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_17|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_18|name": [
        "Batteries: mounting and terminals",
        "Baterias: fixação e terminais"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_18|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_19|name": [
        "Alternator charging",
        "Carga do alternador"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_19|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_20|name": [
        "Trailer electrical socket",
        "Tomada elétrica do semirreboque"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_20|section": [
        "Electrical",
        "Elétrica"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_30|name": [
        "Air conditioning cooling",
        "Ar condicionado gelando"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_30|section": [
        "Air conditioning",
        "Ar condicionado"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_31|name": [
        "Cab ventilation",
        "Ventilação da cabine"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_31|section": [
        "Air conditioning",
        "Ar condicionado"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_40|name": [
        "Windscreen without cracks",
        "Para-brisa sem trincas"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_40|section": [
        "Exterior",
        "Externo"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_41|name": [
        "Mirrors",
        "Retrovisores"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_41|section": [
        "Exterior",
        "Externo"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_42|name": [
        "Body damage (take photos)",
        "Avarias na lataria (fotografar)"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_42|section": [
        "Exterior",
        "Externo"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_43|name": [
        "Visible leaks",
        "Vazamentos aparentes"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_43|section": [
        "Exterior",
        "Externo"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_44|name": [
        "AdBlue (Arla 32): level and hoses",
        "Arla 32: nível e mangueiras"
    ],
    "workshop_checklist_template_item|checklist_truck_entry_item_44|section": [
        "Exterior",
        "Externo"
    ],
    "workshop_checklist_template|checklist_truck_exit|name": [
        "Truck delivery",
        "Saída do caminhão"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_01|name": [
        "All approved items done",
        "Todos os itens aprovados executados"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_01|section": [
        "Service",
        "Serviço"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_02|name": [
        "Replaced parts set aside for the customer",
        "Peças substituídas separadas para o cliente"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_02|section": [
        "Service",
        "Serviço"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_10|name": [
        "All lights tested",
        "Todas as luzes testadas"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_10|section": [
        "Test",
        "Teste"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_11|name": [
        "Dashboard without warnings",
        "Painel sem alertas"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_11|section": [
        "Test",
        "Teste"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_12|name": [
        "Road test done",
        "Teste de rodagem feito"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_12|section": [
        "Test",
        "Teste"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_20|name": [
        "Cab clean",
        "Cabine limpa"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_20|section": [
        "Delivery",
        "Entrega"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_21|name": [
        "Odometer at delivery noted",
        "Km de saída anotado"
    ],
    "workshop_checklist_template_item|checklist_truck_exit_item_21|section": [
        "Delivery",
        "Entrega"
    ]
}

# Company texts that used to default to Portuguese.
COMPANY_TEXTS = {
    "workshop_warranty_text": [
        "Services under a 90-day warranty, as set by the Brazilian Consumer Protection Code.",
        "Serviços com garantia de 90 dias, conforme o Código de Defesa do Consumidor.",
    ],
    "workshop_terms_text": [
        "By approving, I authorise the listed services and their payment as agreed.",
        "Ao aprovar, autorizo a execução dos serviços listados e o pagamento conforme combinado.",
    ],
}


def _retranslate(cr, table, field, english, portuguese, record_id=None):
    where = "AND id = %s" if record_id else ""
    cr.execute(
        f"""UPDATE "{table}"
               SET "{field}" = "{field}" || jsonb_build_object('en_US', %s::text,
                                                               'pt_BR', coalesce("{field}"->>'pt_BR', %s::text))
             WHERE "{field}"->>'en_US' = %s {where}""",
        (english, portuguese, portuguese, *([record_id] if record_id else [])),
    )


def migrate(cr, version):
    for key, (english, portuguese) in DATA.items():
        table, xmlid, field = key.split("|")
        cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'workshop_os' AND name = %s", (xmlid,))
        found = cr.fetchone()
        if found:
            _retranslate(cr, table, field, english, portuguese, found[0])
    for field, (english, portuguese) in COMPANY_TEXTS.items():
        _retranslate(cr, "res_company", field, english, portuguese)
