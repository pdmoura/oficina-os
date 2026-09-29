"""Sample customers, trucks and work orders for trying the system out, and their removal.

Runs in an Odoo shell, as the superuser, in Portuguese (the starting data is translated):

    SAMPLE=create PHOTOS=/tmp/sample-photos odoo shell -c <conf> -d <db> --no-http < sample_data.py
    SAMPLE=check odoo shell -c <conf> -d <db> --no-http < sample_data.py     # what "remove" would delete
    SAMPLE=remove odoo shell -c <conf> -d <db> --no-http < sample_data.py

Every customer, vehicle and order it creates gets an external id under "oficina_exemplo". "remove" deletes those
and what people made on top of them while trying the system out (orders on the sample trucks, closings and unissued
service invoices of the sample customers), photos included, then restarts the order numbering at 1 when no other
order is left. An issued service invoice for a sample customer stops it: fiscal documents are not deleted.
Services are a real starting catalogue: they are only added when missing and "remove" keeps them. The mechanic
assigned to orders is the user whose login is in MECHANIC (default "mecanico"), or the administrator.
"""
import base64
import os
from datetime import timedelta

from odoo import Command, fields

TAG = "oficina_exemplo"
env = env(context=dict(env.context, lang="pt_BR", tz="America/Sao_Paulo", tracking_disable=True))  # noqa: F821

# Starting catalogue: (sector, name, hours, price). Labour only; parts go on their own lines.
SERVICES = [
    ("sector_electric", "Diagnóstico elétrico com scanner", 1.0, 180, True),
    ("sector_electric", "Revisão do alternador", 2.0, 350, True),
    ("sector_electric", "Revisão do motor de partida", 2.0, 380, True),
    ("sector_electric", "Reparo de chicote elétrico", 2.0, 280, False),
    ("sector_electric", "Troca de baterias (par)", 0.5, 90, False),
    ("sector_electric", "Troca de lâmpadas e lanternas", 0.5, 60, False),
    ("sector_electric", "Reparo da iluminação da carreta", 1.5, 220, False),
    ("sector_electric", "Instalação de faróis de LED (par)", 1.0, 160, False),
    ("sector_electric", "Reparo do painel de instrumentos", 2.5, 420, False),
    ("sector_electric", "Instalação de rastreador ou bloqueador", 1.5, 250, False),
    ("sector_injection", "Diagnóstico de injeção eletrônica", 1.0, 250, False),
    ("sector_ac", "Higienização do ar-condicionado", 1.0, 180, True),
    ("sector_ac", "Carga de gás do ar-condicionado (R-134a)", 1.0, 320, True),
    ("sector_ac", "Teste de vazamento com nitrogênio", 1.0, 150, False),
    ("sector_ac", "Troca do filtro secador", 1.5, 240, False),
    ("sector_ac", "Revisão do compressor do ar-condicionado", 3.0, 650, False),
    ("sector_ac", "Troca do condensador", 2.5, 420, False),
    ("sector_ac", "Reparo do climatizador de teto", 2.0, 350, False),
]

CUSTOMERS = {
    "rodovia_sul": {"name": "Rodovia Sul Transportes Ltda", "is_company": True, "email": "frota@rodoviasul.example.com"},
    "cerrado": {"name": "Cerrado Cargas e Logística", "is_company": True, "workshop_auto_approve": True,
                "email": "manutencao@cerradocargas.example.com"},
    "boa_viagem": {"name": "Transportes Boa Viagem Ltda", "is_company": True, "email": "oficina@boaviagem.example.com"},
    "santa_luzia": {"name": "Agropecuária Santa Luzia", "is_company": True, "email": "compras@santaluzia.example.com"},
    "jose_carlos": {"name": "José Carlos Pereira", "is_company": False, "email": "jcpereira@example.com"},
}

# key: (customer, plate, brand, model, year, colour, fleet number, odometer)
VEHICLES = {
    "r450": ("rodovia_sul", "QRS4E21", "Scania", "R 450", "2021", "Branco", "RS-012", 412300),
    "fh540": ("rodovia_sul", "RTK2B37", "Volvo", "FH 540", "2022", "Prata", "RS-027", 286900),
    "r500": ("rodovia_sul", "QTE6B14", "Scania", "R 500", "2020", "Azul", "RS-031", 530100),
    "actros": ("cerrado", "SHB7C55", "Mercedes-Benz", "Actros 2651", "2023", "Azul", "CC-104", 158200),
    "constellation": ("cerrado", "PQW3F19", "Volkswagen", "Constellation 24.280", "2019", "Branco", "CC-088", 498700),
    "axor": ("cerrado", "NXR4D27", "Mercedes-Benz", "Axor 2544", "2015", "Branco", "CC-061", 902400),
    "daf": ("boa_viagem", "RVA8D62", "DAF", "XF 530", "2022", "Vermelho", False, 301500),
    "iveco": ("boa_viagem", "SGT1J88", "Iveco", "S-Way 540", "2023", "Branco", False, 121800),
    "atego": ("santa_luzia", "OKD5A41", "Mercedes-Benz", "Atego 2430", "2018", "Branco", False, 389000),
    "cargo": ("santa_luzia", "OKV2G56", "Ford", "Cargo 2429", "2017", "Branco", False, 455600),
    "g420": ("jose_carlos", "NWP9H03", "Scania", "G 420", "2014", "Laranja", False, 1104500),
}

# Checklist answers for orders being worked on: item position -> (result, note).
CHECKLIST_NOTES = {2: ("attention", "Tanque com 1/4"), 8: ("fail", "Lanterna esquerda queimada")}


def hours(n):
    return timedelta(hours=n)


def days(n):
    return timedelta(days=n)


def ref(xmlid):
    return env.ref(f"workshop_os.{xmlid}")


def tag(records, key):
    for record in records:
        env["ir.model.data"].create({
            "module": TAG, "name": f"{record._table}_{key}", "model": record._name, "res_id": record.id, "noupdate": True,
        })
    return records


def tagged(model):
    ids = env["ir.model.data"].search([("module", "=", TAG), ("model", "=", model)]).mapped("res_id")
    return env[model].browse(ids).exists()


def create():
    if tagged("workshop.order"):
        print("Sample data is already there; run SAMPLE=remove first.")
        return
    now = fields.Datetime.now()
    admin = env.ref("base.user_admin")
    mechanic = env["res.users"].search([("login", "=", os.environ.get("MECHANIC", "mecanico"))], limit=1) or admin
    Service = env["workshop.service"]
    services = {}
    for sector, name, labour, price, favorite in SERVICES:
        service = Service.search([("name", "=", name)], limit=1) or Service.create({
            "name": name, "sector_id": ref(sector).id, "hours": labour, "list_price": price, "favorite": favorite,
        })
        services[name] = service

    partners = {key: tag(env["res.partner"].create({**values, "workshop_customer": True, "lang": "pt_BR"}), key)
                for key, values in CUSTOMERS.items()}
    vehicles = {}
    for key, (customer, plate, brand, model, year, colour, fleet, km) in VEHICLES.items():
        vehicles[key] = tag(env["workshop.vehicle"].create({
            "partner_id": partners[customer].id, "plate": plate, "brand": brand, "model": model, "year": year,
            "color": colour, "fleet_number": fleet, "odometer": km, "fuel": "diesel",
        }), key)

    photos_dir = os.environ.get("PHOTOS", "")

    def photo(order, filename, kind, caption):
        path = os.path.join(photos_dir, filename)
        if photos_dir and os.path.exists(path):
            with open(path, "rb") as image:
                data = base64.b64encode(image.read()).decode()
            env["workshop.order.photo"].add_photo(order.id, {"data": data, "kind": kind, "caption": caption,
                                                             "name": filename})

    def order(key, vehicle, stage, complaint, lines, arrived, *, since=None, state="approved", user=None, promised=None,
              location=None, diagnosis=None, notes=None, driver=None, priority="0", approver=None, done=None,
              delivered=None, photos=(), checklist=0):
        vehicle = vehicles[vehicle]
        user = user or admin
        line_values = []
        for line in lines:
            if isinstance(line, tuple):  # a part: (description, price)
                line_values.append(Command.create({"name": line[0], "price_unit": line[1], "is_part": True,
                                                   "user_id": user.id, "sector_id": ref("sector_misc").id}))
            else:
                values = env["workshop.order.line"]._vals_from_service(services[line])
                line_values.append(Command.create({**values, "user_id": user.id}))
        record = env["workshop.order"].create({
            "partner_id": vehicle.partner_id.id, "vehicle_id": vehicle.id, "stage_id": ref(stage).id,
            "user_id": user.id,
            "location_id": location and ref(location).id, "date_in": now - arrived,
            "date_promised": promised and now + promised, "complaint": complaint, "diagnosis": diagnosis,
            "internal_notes": notes, "driver_name": driver, "priority": priority,
            "odometer": vehicle.odometer + 380, "line_ids": line_values,
        })
        tag(record, key)
        # The stage history as if the truck had gone through the office first.
        log = record.stage_log_ids
        since = now - (since or arrived)
        if stage != "stage_office":
            env["workshop.order.stage.log"].create({
                "order_id": record.id, "stage_id": ref("stage_office").id, "user_id": admin.id,
                "date_start": now - arrived, "date_end": since,
            })
        log.write({"date_start": since, "user_id": user.id})
        if state != "draft" and record.state == "draft":
            record.action_approve()
        if state != "draft":
            record.write({"approved_by": approver or record.partner_id.name,
                          "approved_on": now - arrived + timedelta(minutes=40)})
        if done is not None:
            record.write({"state": "done", "date_done": now - done})
        if delivered is not None:
            log.write({"date_end": now - delivered})
            record.write({"state": "delivered", "date_delivered": now - delivered})
        if checklist:
            record.load_checklist(ref("checklist_truck_entry").id)
            for position, item in enumerate(record.checklist_line_ids[:checklist], start=1):
                result, note = CHECKLIST_NOTES.get(position, ("ok", False))
                item.write({"result": result, "note": note})
        for filename, kind, caption in photos:
            photo(record, filename, kind, caption)
        return record

    order("o01", "r450", "stage_office", "Luz da bateria acesa no painel e caminhão com dificuldade para pegar de manhã.",
          ["Diagnóstico elétrico com scanner", "Revisão do alternador"], hours(2), state="draft",
          promised=days(1), location="location_yard", driver="Valdir",
          photos=[("chegada-cavalo-branco.jpg", "entry", "Chegada no pátio"),
                  ("painel-luzes.jpg", "entry", "Luz da bateria acesa")])
    order("o02", "g420", "stage_office", "Ar-condicionado não gela e faz barulho ao ligar.",
          ["Teste de vazamento com nitrogênio", "Carga de gás do ar-condicionado (R-134a)"], hours(20), state="draft",
          promised=-hours(4), location="location_yard", driver="José Carlos")
    order("o03", "actros", "stage_parts", "Compressor do ar-condicionado fazendo barulho e desarmando.",
          ["Revisão do compressor do ar-condicionado", ("Embreagem eletromagnética do compressor", 890)],
          days(2), since=hours(30), user=mechanic, promised=days(2), location="location_yard",
          diagnosis="Embreagem eletromagnética com folga e rolamento com ruído. Peça pedida ao fornecedor.",
          approver="Contrato de frota", checklist=12,
          photos=[("compressor-ar.jpg", "work", "Compressor com ruído na embreagem")])
    order("o04", "daf", "stage_queue", "Lanternas da carreta não acendem e o pisca da direita está falhando.",
          ["Reparo da iluminação da carreta", "Troca de lâmpadas e lanternas"], hours(6), since=hours(5),
          user=admin, promised=hours(20), location="location_yard", driver="Rogério", approver="Márcia (Boa Viagem)",
          photos=[("lanterna-quebrada.jpg", "entry", "Lanterna traseira da carreta quebrada")])
    order("o05", "atego", "stage_queue", "Instalar faróis de LED e revisar as baterias: o caminhão viaja amanhã cedo.",
          ["Instalação de faróis de LED (par)", "Troca de baterias (par)", ("Bateria 150 Ah (par)", 2480)],
          hours(4), since=hours(3), priority="1", promised=hours(6), location="location_yard",
          approver="Sr. Antônio (Santa Luzia)")
    order("o06", "fh540", "stage_working", "Painel apaga com o caminhão em movimento e volta sozinho.",
          ["Reparo do painel de instrumentos", "Reparo de chicote elétrico"], days(1), since=hours(3), user=mechanic,
          promised=hours(8), location="location_bay_1", driver="Edson", approver="Carlos (Rodovia Sul)",
          diagnosis="Mau contato no conector do painel e fios ressecados no chicote atrás da cabine.", checklist=19,
          photos=[("box-cavalo-prata.jpg", "entry", "Chegada no box 1"),
                  ("chicote.jpg", "work", "Chicote atrás da cabine")])
    order("o07", "constellation", "stage_working", "Preventiva do contrato: higienização e carga de gás.",
          ["Higienização do ar-condicionado", "Carga de gás do ar-condicionado (R-134a)"], hours(3), since=hours(1),
          user=mechanic, promised=hours(5), location="location_bay_2", approver="Contrato de frota", checklist=8)
    order("o08", "iveco", "stage_stopped", "Motor de partida falhando: às vezes só estala e não gira.",
          ["Revisão do motor de partida"], days(3), since=days(2), user=admin, promised=-days(1),
          location="location_bay_3", approver="Márcia (Boa Viagem)",
          diagnosis="Induzido do motor de partida em curto.",
          notes="Parado: cliente vai decidir entre reparar o induzido ou trocar o motor de partida.",
          photos=[("bancada-motor-partida.jpg", "work", "Motor de partida desmontado na bancada")])
    order("o09", "cargo", "stage_test", "Revisar toda a iluminação para a vistoria.",
          ["Troca de lâmpadas e lanternas", "Diagnóstico elétrico com scanner"], days(1), since=timedelta(minutes=40),
          user=mechanic, promised=hours(3), location="location_road", approver="Sr. Antônio (Santa Luzia)",
          checklist=19)
    order("o10", "r500", "stage_test", "Ar-condicionado com cheiro ruim.", ["Higienização do ar-condicionado"],
          days(2), since=hours(26), user=mechanic, location="location_yard", approver="Carlos (Rodovia Sul)",
          done=hours(2), photos=[("saida-cavalo-azul.jpg", "exit", "Pronto para retirada")])
    order("o11", "axor", "stage_test", "Ar-condicionado fraco.",
          ["Carga de gás do ar-condicionado (R-134a)", "Troca do filtro secador", ("Filtro secador", 310)],
          days(5), since=days(4), user=admin, approver="Contrato de frota", done=days(4), delivered=days(3))
    order("o12", "g420", "stage_test", "Alternador não carrega.", ["Revisão do alternador"], days(22),
          since=days(21), user=admin, approver="José Carlos Pereira", done=days(21), delivered=days(20))
    print("Created:", len(partners), "customers,", len(vehicles), "vehicles,", len(tagged("workshop.order")),
          "orders; mechanic:", mechanic.name)


def sample_records():
    """The sample records and everything people made on top of them while trying the system out: orders on the
    sample trucks or customers, monthly closings and service invoices of the sample customers."""
    partners = tagged("res.partner")
    vehicles = tagged("workshop.vehicle")
    orders = tagged("workshop.order") | env["workshop.order"].with_context(active_test=False).search(
        ["|", ("vehicle_id", "in", vehicles.ids), ("partner_id", "child_of", partners.ids)])
    billings = env["workshop.billing"].search([("partner_id", "child_of", partners.ids)]) | orders.billing_id
    notes = env["l10n_br_nfse_nacional.document"] if "l10n_br_nfse_nacional.document" in env else None
    if notes is not None:
        notes = notes.search(["|", ("partner_id", "child_of", partners.ids), ("workshop_order_id", "in", orders.ids)])
    return partners, vehicles, orders, billings, notes


def check():
    partners, vehicles, orders, billings, notes = sample_records()
    extra = orders - tagged("workshop.order")
    print(f"Would remove {len(partners)} customers, {len(vehicles)} vehicles, {len(orders)} orders "
          f"({len(extra)} made on the samples: {', '.join(extra.mapped('name')) or '-'}), "
          f"{len(billings)} monthly closings, {len(notes or [])} unissued service invoices.")
    issued = notes and notes.filtered(lambda n: n.state not in ("draft", "error"))
    if issued:
        print("Blocked by issued service invoices, which cannot be deleted:", ", ".join(issued.mapped("display_name")))
    return not issued


def remove():
    if not check():
        raise SystemExit("Nothing removed.")
    partners, vehicles, orders, billings, notes = sample_records()
    if notes:
        notes.unlink()
    orders.write({"billing_id": False})
    billings.write({"state": "draft"})  # a confirmed closing refuses to be deleted
    billings.unlink()
    orders.photo_ids.unlink()  # also deletes the photo files
    orders.unlink()
    vehicles.unlink()
    partners.unlink()
    env["ir.model.data"].search([("module", "=", TAG)]).unlink()
    if not env["workshop.order"].with_context(active_test=False).search_count([]):
        env["ir.sequence"].search([("code", "=", "workshop.order")]).number_next = 1
    print("Removed.")


{"create": create, "check": check, "remove": remove}[os.environ.get("SAMPLE", "create")]()
env.cr.commit()
