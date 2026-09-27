"""The starting checklists now declare each item as its own record, so each one can be translated.

Existing items were created inside their checklist without an xml id: they get theirs here (matched by checklist
and order), so the update finds them instead of adding a second copy.
"""

# checklist xml id -> [item xml id, sequence, original Portuguese name, original Portuguese section]
ITEMS = {
    "checklist_truck_entry": [
        [
            "checklist_truck_entry_item_01",
            1,
            "Painel sem luzes de alerta",
            "Cabine"
        ],
        [
            "checklist_truck_entry_item_02",
            2,
            "Tacógrafo funcionando",
            "Cabine"
        ],
        [
            "checklist_truck_entry_item_03",
            3,
            "Nível de combustível anotado",
            "Cabine"
        ],
        [
            "checklist_truck_entry_item_04",
            4,
            "Pertences do motorista conferidos",
            "Cabine"
        ],
        [
            "checklist_truck_entry_item_10",
            10,
            "Farol baixo (esquerdo e direito)",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_11",
            11,
            "Farol alto",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_12",
            12,
            "Lanternas traseiras",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_13",
            13,
            "Setas e pisca-alerta",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_14",
            14,
            "Luz de freio",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_15",
            15,
            "Luz e alarme de ré",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_16",
            16,
            "Buzina",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_17",
            17,
            "Limpador e esguicho",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_18",
            18,
            "Baterias: fixação e terminais",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_19",
            19,
            "Carga do alternador",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_20",
            20,
            "Tomada elétrica do semirreboque",
            "Elétrica"
        ],
        [
            "checklist_truck_entry_item_30",
            30,
            "Ar condicionado gelando",
            "Ar condicionado"
        ],
        [
            "checklist_truck_entry_item_31",
            31,
            "Ventilação da cabine",
            "Ar condicionado"
        ],
        [
            "checklist_truck_entry_item_40",
            40,
            "Para-brisa sem trincas",
            "Externo"
        ],
        [
            "checklist_truck_entry_item_41",
            41,
            "Retrovisores",
            "Externo"
        ],
        [
            "checklist_truck_entry_item_42",
            42,
            "Avarias na lataria (fotografar)",
            "Externo"
        ],
        [
            "checklist_truck_entry_item_43",
            43,
            "Vazamentos aparentes",
            "Externo"
        ],
        [
            "checklist_truck_entry_item_44",
            44,
            "Arla 32: nível e mangueiras",
            "Externo"
        ]
    ],
    "checklist_truck_exit": [
        [
            "checklist_truck_exit_item_01",
            1,
            "Todos os itens aprovados executados",
            "Serviço"
        ],
        [
            "checklist_truck_exit_item_02",
            2,
            "Peças substituídas separadas para o cliente",
            "Serviço"
        ],
        [
            "checklist_truck_exit_item_10",
            10,
            "Todas as luzes testadas",
            "Teste"
        ],
        [
            "checklist_truck_exit_item_11",
            11,
            "Painel sem alertas",
            "Teste"
        ],
        [
            "checklist_truck_exit_item_12",
            12,
            "Teste de rodagem feito",
            "Teste"
        ],
        [
            "checklist_truck_exit_item_20",
            20,
            "Cabine limpa",
            "Entrega"
        ],
        [
            "checklist_truck_exit_item_21",
            21,
            "Km de saída anotado",
            "Entrega"
        ]
    ]
}


def migrate(cr, version):
    for template, rows in ITEMS.items():
        cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'workshop_os' AND name = %s", (template,))
        found = cr.fetchone()
        if not found:
            continue
        for xmlid, sequence, _name, _section in rows:
            cr.execute("SELECT 1 FROM ir_model_data WHERE module = 'workshop_os' AND name = %s", (xmlid,))
            if cr.fetchone():
                continue
            cr.execute(
                """SELECT item.id FROM workshop_checklist_template_item item
                    WHERE item.template_id = %s AND item.sequence = %s
                      AND NOT EXISTS (SELECT 1 FROM ir_model_data d
                                       WHERE d.model = 'workshop.checklist.template.item' AND d.res_id = item.id)
                    ORDER BY item.id LIMIT 1""",
                (found[0], sequence),
            )
            item = cr.fetchone()
            if item:
                cr.execute(
                    """INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_uid, write_uid,
                                                  create_date, write_date)
                       VALUES ('workshop_os', %s, 'workshop.checklist.template.item', %s, TRUE, 1, 1, now(), now())""",
                    (xmlid, item[0]),
                )
