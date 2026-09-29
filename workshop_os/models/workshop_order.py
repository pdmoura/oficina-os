import hashlib
import logging
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import quote

import requests

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import consteq, format_amount, formatLang

from .res_config_settings import PARAM
from .workshop_vehicle import PLATE_RE, format_plate, normalize_plate

_logger = logging.getLogger(__name__)

OPEN_STATES = ("draft", "approved", "done")
# Only the office sets these (the customer's own answer comes through the public link, as superuser).
OFFICE_STATES = ("approved", "rejected", "cancel")
OFFICE_FIELDS = {"approved_by", "approved_on", "approval_signature", "billing_id"}


class WorkshopOrder(models.Model):
    _name = "workshop.order"
    _description = "Work Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, date_in desc, id desc"
    _rec_names_search = ["name", "vehicle_id.plate", "partner_id.name", "vehicle_id.fleet_number"]
    _check_company_auto = True

    name = fields.Char("Number", readonly=True, copy=False, index=True, default=lambda self: self.env._("New"))
    partner_id = fields.Many2one("res.partner", "Customer", required=True, index=True, tracking=True)
    vehicle_id = fields.Many2one("workshop.vehicle", "Vehicle", required=True, index=True, tracking=True,
                                 check_company=True,
                                 domain="['|', ('partner_id', '=', False), ('partner_id', '=', partner_id)]")
    plate = fields.Char(related="vehicle_id.plate_display", string="Plate")
    vehicle_desc = fields.Char("Vehicle model", compute="_compute_vehicle_desc")
    odometer = fields.Integer("Odometer (km)")
    driver_name = fields.Char("Brought by", help="Driver or employee of the customer who brought the vehicle.")
    stage_id = fields.Many2one("workshop.stage", "Stage", index=True, tracking=True, group_expand="_read_group_stage_ids",
                               default=lambda self: self.env["workshop.stage"].search([], limit=1))
    stage_color = fields.Char(related="stage_id.color")
    location_id = fields.Many2one("workshop.location", "Location", tracking=True)
    sector_id = fields.Many2one("workshop.sector", "Sector")
    # all_group_ids: group_ids only holds the groups set by hand, so office users (Mechanic implied) would be missing.
    user_id = fields.Many2one("res.users", "Mechanic", tracking=True, default=lambda self: self.env.user,
                              domain=lambda self: [("all_group_ids", "in", self.env.ref("workshop_os.workshop_os_group_user").id),
                                                   ("share", "=", False)])
    priority = fields.Selection([("0", "Normal"), ("1", "Urgent")], default="0")
    state = fields.Selection([
        ("draft", "Awaiting approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("done", "Ready"),
        ("delivered", "Delivered"),
        ("cancel", "Cancelled"),
    ], string="Progress", default="draft", required=True, tracking=True, index=True, copy=False)
    date_in = fields.Datetime("Arrived", default=fields.Datetime.now, required=True, index=True)
    date_promised = fields.Datetime("Promised for", tracking=True)
    date_done = fields.Datetime("Ready on", readonly=True, copy=False)
    state_before_done = fields.Char(readonly=True, copy=False,
                                    help="Status before the order was marked ready, restored if that is undone.")
    date_delivered = fields.Datetime("Delivered on", readonly=True, copy=False)
    complaint = fields.Text("Reported problem")
    diagnosis = fields.Text()
    internal_notes = fields.Text()
    tow = fields.Boolean("Arrived towed")
    rework = fields.Boolean("Rework", help="Return of a previous job (reserviço).")

    line_ids = fields.One2many("workshop.order.line", "order_id", string="Services", copy=True)
    photo_ids = fields.One2many("workshop.order.photo", "order_id", string="Photos")
    checklist_line_ids = fields.One2many("workshop.order.checklist", "order_id", string="Checklist")
    stage_log_ids = fields.One2many("workshop.order.stage.log", "order_id", string="Stage history", readonly=True)

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    amount_total = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_services = fields.Monetary("Labour", compute="_compute_amounts", store=True, currency_field="currency_id",
                                      help="Labour, the part of the order the service invoice (NFS-e) covers.")
    amount_parts = fields.Monetary("Parts", compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_approved = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    hours_total = fields.Float("Labour hours", compute="_compute_amounts", store=True)
    photo_count = fields.Integer(compute="_compute_counts")
    checklist_progress = fields.Integer(compute="_compute_counts", help="Answered checklist items, in %.")

    is_late = fields.Boolean(compute="_compute_is_late", search="_search_is_late")
    stage_since = fields.Datetime(compute="_compute_stage_since")
    warranty_text = fields.Text(default=lambda self: self.env.company.workshop_warranty_text)

    access_token = fields.Char(copy=False, default=lambda self: secrets.token_urlsafe(24), readonly=True)
    public_url = fields.Char("Customer link", compute="_compute_public_url")
    approved_by = fields.Char("Approved by", readonly=True, copy=False)
    approved_on = fields.Datetime(readonly=True, copy=False)
    approval_signature = fields.Image(readonly=True, copy=False, max_width=1024, max_height=512)
    billing_id = fields.Many2one("workshop.billing", "Monthly closing", readonly=True, copy=False, index=True,
                                 check_company=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("line_ids.subtotal", "line_ids.approval", "line_ids.hours", "line_ids.quantity", "line_ids.is_part")
    def _compute_amounts(self):
        for order in self:
            lines = order.line_ids.filtered(lambda l: l.approval != "rejected")
            order.amount_total = sum(lines.mapped("subtotal"))
            order.amount_parts = sum(lines.filtered("is_part").mapped("subtotal"))
            order.amount_services = order.amount_total - order.amount_parts
            order.amount_approved = sum(lines.filtered(lambda l: l.approval == "approved").mapped("subtotal"))
            order.hours_total = sum(l.hours * l.quantity for l in lines)

    @api.depends("vehicle_id.brand", "vehicle_id.model", "vehicle_id.fleet_number")
    def _compute_vehicle_desc(self):
        for order in self:
            vehicle = order.vehicle_id
            desc = " ".join(filter(None, [vehicle.brand, vehicle.model]))
            order.vehicle_desc = f"{desc} · #{vehicle.fleet_number}" if vehicle.fleet_number else desc

    @api.depends("access_token")
    def _compute_public_url(self):
        for order in self:
            order.public_url = order.get_public_url()

    @api.depends("photo_ids", "checklist_line_ids.result")
    def _compute_counts(self):
        for order in self:
            order.photo_count = len(order.photo_ids)
            items = order.checklist_line_ids
            done = len(items.filtered("result"))
            order.checklist_progress = round(100 * done / len(items)) if items else 0

    @api.depends("date_promised", "state")
    def _compute_is_late(self):
        now = fields.Datetime.now()
        for order in self:
            order.is_late = bool(order.date_promised and order.date_promised < now and order.state in OPEN_STATES)

    def _search_is_late(self, operator, value):
        if operator != "in":
            return NotImplemented
        late = Domain("date_promised", "<", fields.Datetime.now()) & Domain("state", "in", OPEN_STATES)
        if True in value and False in value:
            return Domain.TRUE
        return late if True in value else ~late

    @api.depends("stage_log_ids.date_start")
    def _compute_stage_since(self):
        for order in self:
            open_log = order.stage_log_ids.filtered(lambda l: not l.date_end)[:1]
            order.stage_since = open_log.date_start or order.date_in

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        # Boards opened from a dashboard card on a phone show the stages that have orders, not empty columns first.
        if self.env.context.get("workshop_used_stages_only"):
            return stages
        return stages.search([], order=stages._order)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("vehicle_id", "partner_id")
    def _check_vehicle_owner(self):
        for order in self:
            owner = order.vehicle_id.partner_id
            if owner and owner.commercial_partner_id != order.partner_id.commercial_partner_id:
                raise ValidationError(_("Vehicle %(plate)s belongs to %(owner)s, not to %(partner)s.",
                                        plate=order.plate, owner=owner.display_name, partner=order.partner_id.display_name))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("state") in OFFICE_STATES or OFFICE_FIELDS & vals.keys():
                self._check_office()
            if vals.get("name") in (None, False, "", "/", self.env._("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code("workshop.order") or self.env._("New")
            if vals.get("partner_id") and not vals.get("state"):
                partner = self.env["res.partner"].browse(vals["partner_id"])
                if partner.commercial_partner_id.workshop_auto_approve:
                    vals["state"] = "approved"
        orders = super().create(vals_list)
        for order in orders:
            order._log_stage_change()
            if order.odometer and order.odometer > order.vehicle_id.odometer:
                order.vehicle_id.odometer = order.odometer
        return orders

    def write(self, vals):
        if vals.get("state") in OFFICE_STATES or OFFICE_FIELDS & vals.keys():
            self._check_office()
        stage_changed = "stage_id" in vals
        res = super().write(vals)
        if stage_changed:
            for order in self:
                order._log_stage_change()
        if vals.get("odometer"):
            for order in self.filtered(lambda o: o.odometer > o.vehicle_id.odometer):
                order.vehicle_id.odometer = order.odometer
        return res

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_approve(self):
        self._check_office()
        for order in self.filtered(lambda o: o.state in ("draft", "rejected")):
            order.line_ids.filtered(lambda l: l.approval == "pending").approval = "approved"
            order.write({"state": "approved", "approved_by": self.env.user.name, "approved_on": fields.Datetime.now()})
        return True

    def action_reject(self):
        self._check_office()
        self.filtered(lambda o: o.state == "draft").write({"state": "rejected"})
        return True

    def action_done(self):
        for order in self:
            if order.state not in ("draft", "approved"):
                raise UserError(_("%s cannot be marked ready from its current status.", order.name))
            if not order.line_ids:
                raise UserError(_("Add at least one service to %s before marking it ready.", order.name))
        now = fields.Datetime.now()
        for order in self:
            order.write({"state": "done", "date_done": now, "state_before_done": order.state})
        return True

    def action_undo_done(self):
        """Back from "ready" to the job, for a mechanic who marked it by mistake.

        Only until the truck leaves or the order is billed; after that, reopening is the office's (action_reopen).
        """
        for order in self:
            order._check_can_undo_done()
            previous = order.state_before_done or (
                "approved" if order.approved_on or "approved" in order.line_ids.mapped("approval") else "draft")
            # "Approved" is an office status: the mechanic only gets back the one the office or the customer gave.
            order.sudo().write({"state": previous, "date_done": False, "state_before_done": False})
        return True

    def action_deliver(self):
        for order in self:
            if order.state != "done":
                raise UserError(_("Mark %s as ready before delivering it.", order.name))
        self.write({"state": "delivered", "date_delivered": fields.Datetime.now()})
        return True

    def action_cancel(self):
        self._check_office()
        if self.filtered("billing_id"):
            raise UserError(_("Orders already included in a monthly closing cannot be cancelled."))
        self.write({"state": "cancel"})
        return True

    def action_reopen(self):
        self._check_office()
        if self.filtered("billing_id"):
            raise UserError(_("Orders already included in a monthly closing cannot be reopened."))
        self.write({"state": "approved", "date_done": False, "date_delivered": False})
        return True

    def action_print(self):
        """Print button: straight to the PDF, or first a question about the photos when the order has some."""
        self.ensure_one()
        if not self.photo_ids.filtered("show_to_customer"):
            # config=False: the PDF has its own layout, so Odoo's document layout set-up has nothing to ask.
            return self.env.ref("workshop_os.action_report_workshop_order").report_action(self, config=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Print %s", self.name),
            "res_model": "workshop.order.print",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    def action_send_whatsapp(self):
        self.ensure_one()
        phone = "".join(ch for ch in (self.partner_id.phone or "") if ch.isdigit())
        if phone and not phone.startswith("55"):
            phone = "55" + phone
        text = _("Hello! Work order %(name)s for %(plate)s: %(url)s", name=self.name, plate=self.plate,
                 url=self.get_public_url())
        return {"type": "ir.actions.act_url", "target": "new",
                "url": f"https://wa.me/{phone}?text={quote(text)}" if phone else f"https://wa.me/?text={quote(text)}"}

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------
    def _check_can_undo_done(self):
        """Raise when a ready order can no longer go back to the job; the NFS-e module adds its own reason."""
        self.ensure_one()
        if self.state != "done":
            raise UserError(_("Only an order marked ready can go back to the job."))
        if self.billing_id:
            raise UserError(_("%s is already in a monthly closing: ask the office to reopen it.", self.name))

    def _check_office(self, message=None):
        """Approving, refusing, cancelling and reopening belong to the office, whoever calls the method and how."""
        if not self.env.su and not self.env.user.has_group("workshop_os.workshop_os_group_manager"):
            raise AccessError(message or _("Only the office can approve, refuse, cancel or reopen a work order."))

    def _log_stage_change(self):
        self.ensure_one()
        now = fields.Datetime.now()
        open_logs = self.stage_log_ids.filtered(lambda l: not l.date_end)
        if open_logs and open_logs[:1].stage_id == self.stage_id:
            return
        open_logs.write({"date_end": now})
        if self.stage_id:
            self.env["workshop.order.stage.log"].create({
                "order_id": self.id, "stage_id": self.stage_id.id, "date_start": now, "user_id": self.env.user.id,
            })

    def get_public_url(self):
        self.ensure_one()
        return f"{self.get_base_url()}/os/{self.access_token}"

    def _photo_groups(self, photos):
        """[(label, photos)] in the order they are taken (arrival, job, delivery), leaving out empty ones.

        A photo without a moment counts as arrival, the default, so it is never left out of the page or the PDF.
        """
        labels = dict(photos._fields["kind"]._description_selection(self.env))
        groups = [(labels[kind], photos.filtered(lambda p, kind=kind: (p.kind or "entry") == kind)) for kind in labels]
        return [(label, group) for label, group in groups if group]

    @api.model
    def _get_by_token(self, token):
        """Order for a public link token, compared in constant time; empty recordset if none."""
        if not token or len(token) < 16:
            return self.browse()
        order = self.sudo().search([("access_token", "=", token)], limit=1)
        return order if order and consteq(order.access_token, token) else self.browse()

    def _customer_decide(self, approve, name, signature=None, line_ids=None):
        """Approval or rejection sent from the public page (already token-checked, runs as sudo).

        Private: over RPC anyone logged in could otherwise answer in the customer's name.
        """
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("This order was already answered."))
        name = (name or "").strip()[:120]
        if not name:
            raise UserError(_("Please type your name."))
        if approve:
            chosen = self.line_ids.filtered(lambda l: l.id in line_ids) if line_ids is not None else self.line_ids
            chosen.approval = "approved"
            (self.line_ids - chosen).approval = "rejected"
            self.write({
                "state": "approved" if chosen else "rejected",
                "approved_by": name,
                "approved_on": fields.Datetime.now(),
                "approval_signature": signature or False,
            })
            body = _("Approved online by %(name)s: %(count)s of %(total)s items.",
                     name=name, count=len(chosen), total=len(self.line_ids))
        else:
            self.write({"state": "rejected", "approved_by": name, "approved_on": fields.Datetime.now()})
            body = _("Rejected online by %(name)s.", name=name)
        self.message_post(body=body, message_type="notification")
        return True

    @api.model
    def _workshop_home_action(self):
        """Where the Workshop app opens: the office on the yard dashboard, mechanics straight in their app."""
        office = self.env.user.has_group("workshop_os.workshop_os_group_manager")
        xmlid = "workshop_os.workshop_order_action_dashboard" if office else "workshop_os.workshop_order_action_mechanic_app"
        return self.env["ir.actions.actions"]._for_xml_id(xmlid)

    # ------------------------------------------------------------------
    # Mechanic app and dashboard API: one call per screen, because every round trip to the database costs latency
    # ------------------------------------------------------------------
    @api.model
    def app_home(self, search=""):
        stages = self.env["workshop.stage"].search([])
        domain = [("state", "in", OPEN_STATES)]
        if search:
            plate = normalize_plate(search)
            domain += ["|", "|", ("vehicle_id.plate", "ilike", plate or search), ("name", "ilike", search),
                       ("partner_id.name", "ilike", search)]
        orders = self.search(domain, limit=80)
        return {
            "stages": [{"id": s.id, "name": s.name, "color": s.color, "waiting": s.is_waiting} for s in stages],
            "orders": [o._app_card() for o in orders],
            "user": {"name": self.env.user.name, "is_manager": self.env.user.has_group("workshop_os.workshop_os_group_manager")},
            "company": self.env.company._workshop_brand(),
            "counts": {
                "open": len(orders),
                "late": len(orders.filtered("is_late")),
                "waiting": len(orders.filtered(lambda o: o.state == "draft")),
            },
        }

    @api.model
    def dashboard_data(self):
        """Office cockpit: the yard now and the month so far, in one call."""
        now = fields.Datetime.now()
        month_start = fields.Datetime.to_datetime(fields.Date.context_today(self).replace(day=1))
        open_orders = self.search([("state", "in", OPEN_STATES)])
        month_done = self.search([("state", "in", ("done", "delivered")), ("date_done", ">=", month_start)])
        currency = self.env.company.currency_id
        revenue = sum(month_done.mapped("amount_total"))
        durations = [(o.date_done - o.date_in).total_seconds() / 3600 for o in month_done if o.date_done and o.date_in]
        by_customer = {}
        for order in month_done:
            key = order.partner_id.commercial_partner_id
            by_customer[key] = by_customer.get(key, 0.0) + order.amount_total
        top_customers = sorted(by_customer.items(), key=lambda kv: -kv[1])[:6]
        stages = self.env["workshop.stage"].search([])
        return {
            "company": self.env.company._workshop_brand(),
            "kpis": {
                "open": len(open_orders),
                "late": len(open_orders.filtered("is_late")),
                "to_approve": len(open_orders.filtered(lambda o: o.state == "draft")),
                "ready": len(open_orders.filtered(lambda o: o.state == "done")),
                "done_month": len(month_done),
                "revenue_month": format_amount(self.env, revenue, currency),
                "avg_hours": round(sum(durations) / len(durations), 1) if durations else 0,
                "to_bill": format_amount(self.env, sum(self.search([
                    ("state", "in", ("done", "delivered")), ("billing_id", "=", False)]).mapped("amount_total")), currency),
            },
            "stages": [{
                "id": stage.id, "name": stage.name, "color": stage.color,
                "count": len(open_orders.filtered(lambda o, st=stage: o.stage_id == st)),
            } for stage in stages],
            "late": [o._app_card() for o in open_orders.filtered("is_late").sorted("date_promised")[:8]],
            "ready": [o._app_card() for o in open_orders.filtered(lambda o: o.state == "done")[:8]],
            "top_customers": [{"name": partner.name, "amount": format_amount(self.env, amount, currency),
                               "share": round(100 * amount / revenue) if revenue else 0}
                              for partner, amount in top_customers],
            "now": fields.Datetime.to_string(now),
        }

    def _app_card(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "plate": self.plate or "",
            "vehicle": " ".join(filter(None, [self.vehicle_id.brand, self.vehicle_id.model])),
            "fleet_number": self.vehicle_id.fleet_number or "",
            "partner": self.partner_id.commercial_partner_id.display_name or "",
            "stage_id": self.stage_id.id,
            "stage": self.stage_id.name or "",
            "stage_color": self.stage_id.color or "#64748B",
            "location": self.location_id.name or "",
            "mechanic": self.user_id.name or "",
            "state": self.state,
            "state_label": dict(self._fields["state"]._description_selection(self.env)).get(self.state),
            "is_late": self.is_late,
            "promised": fields.Datetime.to_string(self.date_promised) if self.date_promised else False,
            "stage_since": fields.Datetime.to_string(self.stage_since) if self.stage_since else False,
            "amount": self.amount_total,
            "amount_fmt": format_amount(self.env, self.amount_total, self.currency_id),
            "hours": self.hours_total,
            "photo_count": self.photo_count,
        }

    @api.model
    def app_new_form(self, service_ids=None, partner_id=None):
        """Everything the new-order screen needs, in one call. Services and customers are searched as the mechanic
        types (app_services, app_partners); only the ones a saved draft already holds come here, for their names."""
        partner = self.env["res.partner"].browse(partner_id).exists() if partner_id else self.env["res.partner"]
        return {
            "stages": [{"id": s.id, "name": s.name, "color": s.color} for s in self.env["workshop.stage"].search([])],
            "locations": [{"id": l.id, "name": l.name} for l in self.env["workshop.location"].search([])],
            "sectors": [{"id": s.id, "name": s.name} for s in self.env["workshop.sector"].search([])],
            "services": [self._app_service(s) for s in self.env["workshop.service"].browse(service_ids or []).exists()],
            "partner": self._app_partner(partner) if partner else False,
            "templates": [{"id": t.id, "name": t.name, "kind": t.kind}
                          for t in self.env["workshop.checklist.template"].search([])],
        }

    @api.model
    def app_partners(self, search=""):
        """Customers for the app's picker: by name, CNPJ/CPF or phone; with nothing typed, the latest ones first."""
        Partner = self.env["res.partner"]
        domain = [("workshop_customer", "=", True)]
        if search:
            partners = Partner.search(domain + ["|", "|", ("name", "ilike", search), ("vat", "ilike", search),
                                                ("phone", "ilike", search)], limit=30)
        else:
            recent = self.search([], order="date_in desc", limit=100).partner_id.commercial_partner_id
            partners = (recent.filtered("workshop_customer") | Partner.search(domain, limit=30))[:30]
        return [self._app_partner(p) for p in partners]

    @api.model
    def _app_partner(self, partner):
        return {"id": partner.id, "name": partner.display_name, "detail": partner.vat or partner.phone or partner.city or ""}

    @api.model
    def _app_service(self, service):
        return {"id": service.id, "name": service.name, "hours": service.hours, "favorite": service.favorite,
                "is_part": service.is_part, "price_fmt": format_amount(self.env, service.list_price, service.currency_id)}

    @api.model
    def _app_create_partner(self, values):
        """A customer registered by a mechanic at the gate: name, phone and kind; the office completes the rest.

        Mechanics cannot create contacts in Odoo, so the app creates this one for them, with these fields only. A
        customer of the same name is reused rather than doubled.
        """
        name = " ".join((values.get("name") or "").split())[:120]
        if not name:
            raise UserError(_("Type the new customer's name."))
        phone = re.sub(r"\D", "", values.get("phone") or "")
        if len(phone) > 11 and phone.startswith("55"):
            phone = phone[2:]
        if phone and not (re.match(r"[1-9]{2}", phone) and (len(phone) == 10 or (len(phone) == 11 and phone[2] == "9"))):
            raise UserError(_("Type the phone with the DDD, like (61) 99999-0000."))
        Partner = self.env["res.partner"]
        # Compared in Python: "%" or "_" in a name would be wildcards to the database.
        partner = Partner.search([("workshop_customer", "=", True), ("name", "ilike", name)]).filtered(
            lambda p: p.name.casefold() == name.casefold())[:1]
        if not partner:
            partner = Partner.sudo().create({
                "name": name,
                "phone": f"+55 {phone[:2]} {phone[2:-4]}-{phone[-4:]}" if phone else False,
                "is_company": values.get("is_company", True) is not False,
                "workshop_customer": True,
            })
            partner.message_post(body=_("Registered in the mechanic app by %s. Complete the CNPJ/CPF and the address "
                                        "before invoicing.", self.env.user.name))
        return partner.sudo(False)

    @api.model
    def app_create(self, values):
        """Create an order from the mechanic app, registering the vehicle on the fly when the plate is new."""
        plate = normalize_plate(values.get("plate"))
        if not PLATE_RE.match(plate):
            raise UserError(_("%s is not a valid plate.", plate or _("Empty plate")))
        Vehicle = self.env["workshop.vehicle"]
        vehicle = Vehicle.search([("plate", "=", plate)], limit=1)
        partner_id = values.get("partner_id") or vehicle.partner_id.id
        if not partner_id and (values.get("new_partner") or {}).get("name"):
            partner_id = self._app_create_partner(values["new_partner"]).id
        if not partner_id:
            raise UserError(_("Choose the customer for %s.", format_plate(plate)))
        if not vehicle:
            vehicle = Vehicle.create({
                "plate": plate,
                "partner_id": partner_id,
                "brand": values.get("brand") or False,
                "model": values.get("model") or False,
                "fleet_number": values.get("fleet_number") or False,
            })
        elif not vehicle.partner_id:
            vehicle.partner_id = partner_id
        open_order = self.search([("vehicle_id", "=", vehicle.id), ("state", "in", OPEN_STATES)], limit=1)
        if open_order and not values.get("force_new"):
            return {"id": open_order.id, "existing": True}
        services = self.env["workshop.service"].browse(values.get("service_ids") or []).exists()
        order = self.create({
            "partner_id": partner_id,
            "vehicle_id": vehicle.id,
            "odometer": int("".join(ch for ch in str(values.get("odometer") or "") if ch.isdigit()) or 0),
            "driver_name": values.get("driver_name") or False,
            "complaint": values.get("complaint") or False,
            "stage_id": values.get("stage_id") or self.env["workshop.stage"].search([], limit=1).id,
            "location_id": values.get("location_id") or False,
            "sector_id": values.get("sector_id") or False,
            "user_id": self.env.user.id,
            "line_ids": [Command.create(self.env["workshop.order.line"]._vals_from_service(s)) for s in services],
        })
        if values.get("template_id"):
            order.load_checklist(values["template_id"])
        return {"id": order.id, "existing": False}

    def app_read(self):
        self.ensure_one()
        return {
            **self._app_card(),
            "odometer": self.odometer,
            "driver_name": self.driver_name or "",
            "complaint": self.complaint or "",
            "diagnosis": self.diagnosis or "",
            "location_id": self.location_id.id,
            "date_in": fields.Datetime.to_string(self.date_in),
            "public_url": self.get_public_url(),
            "approved_by": self.approved_by or "",
            "partner_id": self.partner_id.id,
            "partner_detail": self._app_partner(self.partner_id)["detail"],
            "brand": self.vehicle_id.brand or "",
            "model": self.vehicle_id.model or "",
            "fleet_number": self.vehicle_id.fleet_number or "",
            "is_open": self.state in OPEN_STATES,
            "can_delete": not self._app_delete_blocker(),
            "plate_editable": self._app_plate_editable(),
            "partner_editable": self._app_partner_editable(),
            "lines": [{
                "id": l.id, "service_id": l.service_id.id, "name": l.name, "quantity": l.quantity,
                "price": l.price_unit, "subtotal": l.subtotal,
                "subtotal_fmt": format_amount(self.env, l.subtotal, self.currency_id),
                "hours": l.hours, "approval": l.approval, "is_part": l.is_part,
            } for l in self.line_ids],
            "state_actions": self._app_state_actions(),
            "photos": [{"id": p.id, "url": p.url, "thumb": p.thumb_url, "caption": p.caption or "", "kind": p.kind}
                       for p in self.photo_ids],
            "checklist": [{"id": c.id, "section": c.section or "", "name": c.name, "result": c.result or "",
                           "note": c.note or ""} for c in self.checklist_line_ids],
            "timeline": [{"stage": log.stage_id.name, "color": log.stage_id.color, "start": fields.Datetime.to_string(log.date_start),
                          "hours": round(log.elapsed_hours, 2), "user": log.user_id.name}
                         for log in self.stage_log_ids.sorted("date_start")],
            "stages": [{"id": s.id, "name": s.name, "color": s.color} for s in self.env["workshop.stage"].search([])],
            "locations": [{"id": l.id, "name": l.name} for l in self.env["workshop.location"].search([])],
            "templates": [{"id": t.id, "name": t.name} for t in self.env["workshop.checklist.template"].search([])],
        }

    def _app_state_actions(self):
        """Buttons the app shows for the current status, respecting the user's role."""
        self.ensure_one()
        manager = self.env.user.has_group("workshop_os.workshop_os_group_manager")
        actions = []
        if self.state in ("draft", "rejected") and manager:
            actions.append({"action": "action_approve", "label": _("Approve"), "style": "primary"})
        if self.state in ("draft", "approved") and self.line_ids:
            actions.append({"action": "action_done", "label": _("Job ready"), "style": "primary" if self.state == "approved" else "ghost"})
        if self.state == "done":
            actions.append({"action": "action_undo_done", "label": _("Reopen"), "style": "ghost"})
            actions.append({"action": "action_deliver", "label": _("Delivered"), "style": "primary"})
        return actions

    @api.model
    def app_services(self, search="", limit=40):
        """Services for the app's pickers: favourites and the most used first (the model's order)."""
        domain = ["|", ("name", "ilike", search), ("code", "ilike", search)] if search else []
        return [self._app_service(s) for s in self.env["workshop.service"].search(domain, limit=min(limit, 200))]

    def app_update(self, values):
        """Small edits from the app: stage, location, odometer, diagnosis."""
        self.ensure_one()
        allowed = {"stage_id", "location_id", "odometer", "diagnosis", "complaint", "driver_name"}
        self.write({k: v for k, v in values.items() if k in allowed})
        return self.app_read()

    def app_add_services(self, service_ids):
        self.ensure_one()
        services = self.env["workshop.service"].browse(service_ids).exists()
        self.write({"line_ids": [Command.create(self.env["workshop.order.line"]._vals_from_service(s)) for s in services]})
        return self.app_read()

    def app_edit(self, values):
        """The app's corrections: the arrival details, the truck, and the customer while nobody approved the order."""
        self.ensure_one()
        if self.state not in OPEN_STATES:
            raise UserError(_("%s is closed: ask the office to change it.", self.name))
        order_values = {key: values[key] or False for key in ("driver_name", "complaint", "diagnosis") if key in values}
        vehicle_values = {key: values[key] or False for key in ("brand", "model", "fleet_number") if key in values}
        if "odometer" in values:
            order_values["odometer"] = int("".join(ch for ch in str(values["odometer"] or "") if ch.isdigit()) or 0)
            if self.vehicle_id.odometer == self.odometer:
                # The truck's reading came from this order: a typo fixed here must not stay on the truck.
                vehicle_values["odometer"] = order_values["odometer"]
        plate = normalize_plate(values.get("plate") or "")
        if plate and plate != self.vehicle_id.plate:
            if not self._app_plate_editable():
                raise UserError(_("This truck has other orders: ask the office to correct its plate."))
            if not PLATE_RE.match(plate):
                raise UserError(_("%s is not a valid plate.", plate))
            if self.env["workshop.vehicle"].search_count([("plate", "=", plate), ("id", "!=", self.vehicle_id.id)]):
                raise UserError(_("%s is already registered to another truck.", format_plate(plate)))
            vehicle_values["plate"] = plate
        partner = self.env["res.partner"]
        if values.get("partner_id") and values["partner_id"] != self.partner_id.id:
            partner = partner.browse(values["partner_id"]).exists()
        elif (values.get("new_partner") or {}).get("name"):
            if not self._app_partner_editable():
                raise UserError(_("Only the office changes the customer now: the truck has earlier orders, or the quote was already answered."))
            partner = self._app_create_partner(values["new_partner"])
        if partner and partner != self.partner_id:
            if not self._app_partner_editable():
                raise UserError(_("Only the office changes the customer now: the truck has earlier orders, or the quote was already answered."))
            # The truck came in with this order alone, so the customer was wrong for both: it moves first, since an
            # order's truck must belong to its customer (_check_vehicle_owner).
            vehicle_values["partner_id"] = partner.id
        if vehicle_values:
            self.vehicle_id.write(vehicle_values)
        if partner and partner != self.partner_id:
            self._app_change_partner(partner)
        if order_values:
            self.write(order_values)
        return self.app_read()

    def _app_change_partner(self, partner):
        """Another customer, whose contract decides again whether the order starts approved, as when it was opened."""
        auto = partner.commercial_partner_id.workshop_auto_approve
        values = {"partner_id": partner.id}
        if auto and self.state == "draft":
            values["state"] = "approved"
            self.line_ids.filtered(lambda l: l.approval == "pending").sudo().approval = "approved"
        elif not auto and self.state == "approved":
            values["state"] = "draft"
            self.line_ids.filtered(lambda l: l.approval == "approved").sudo().approval = "pending"
        # Only reached while nobody approved the order (_app_partner_editable), so no decision is overridden.
        self.sudo().write(values)

    def _app_partner_editable(self):
        """The customer is corrected from the app while nobody answered the quote, on a truck new with this order:
        a known truck brings its own customer, and changing that is the office's."""
        self.ensure_one()
        return (self.state in ("draft", "approved") and not self.approved_by and not self.billing_id
                and self._app_vehicle_is_new())

    def _app_plate_editable(self):
        """A plate is corrected from the app only on a truck that came in with this order alone."""
        self.ensure_one()
        return self.state in OPEN_STATES and self._app_vehicle_is_new()

    def _app_vehicle_is_new(self):
        return self.search_count([("vehicle_id", "=", self.vehicle_id.id)]) == 1

    def _app_delete_blocker(self):
        """Why the app cannot delete this order, or False. It deletes orders opened by mistake: before anyone
        approved, finished or billed them, and a mechanic only the ones they opened."""
        self.ensure_one()
        if self.state not in ("draft", "approved") or self.approved_by or self.billing_id:
            return _("%s was already approved or finished: ask the office to cancel it.", self.name)
        if self.create_uid != self.env.user and not self.env.user.has_group("workshop_os.workshop_os_group_manager"):
            return _("Only whoever opened %s can delete it: ask the office.", self.name)
        return False

    def app_delete(self):
        """Delete an order opened by mistake, with the truck and the customer registered for it alone."""
        self.ensure_one()
        if blocker := self._app_delete_blocker():
            raise UserError(blocker)
        name, user = self.name, self.env.user
        vehicle, partner = self.vehicle_id.sudo(), self.partner_id.commercial_partner_id.sudo()
        # Mechanics cannot delete records in Odoo; the checks above are what allows this one.
        self.sudo().unlink()
        Order = self.env["workshop.order"].sudo()
        if vehicle.create_uid == user and not Order.search_count([("vehicle_id", "=", vehicle.id)]):
            vehicle.unlink()  # a mistyped plate would stay as a truck that never came in
        else:
            vehicle.message_post(body=_("Work order %(name)s deleted by %(user)s.", name=name, user=user.name))
        if (partner.create_uid == user and partner.workshop_customer
                and not Order.search_count([("partner_id", "child_of", partner.id)])
                and not self.env["workshop.vehicle"].sudo().search_count([("partner_id", "child_of", partner.id)])):
            partner.action_archive()  # kept, archived, in case the office wants it back
        return True

    def app_remove_line(self, line_id):
        self.ensure_one()
        self.line_ids.filtered(lambda l: l.id == line_id).unlink()
        return self.app_read()

    def app_action(self, action):
        self.ensure_one()
        if action not in ("action_done", "action_undo_done", "action_deliver", "action_approve"):
            raise UserError(_("Unknown action."))
        getattr(self, action)()
        return self.app_read()

    def load_checklist(self, template_id):
        self.ensure_one()
        template = self.env["workshop.checklist.template"].browse(template_id).exists()
        if template:
            self.write({"checklist_line_ids": [Command.create({
                "template_id": template.id, "section": item.section, "name": item.name, "sequence": item.sequence,
            }) for item in template.item_ids]})
        return self.app_read()

    def app_save_checklist(self, answers):
        """answers: {line_id: {"result": "ok|attention|fail|na", "note": "..."}}"""
        self.ensure_one()
        lines = self.checklist_line_ids
        for line_id, answer in (answers or {}).items():
            line = lines.filtered(lambda l: l.id == int(line_id))
            if line:
                line.write({"result": answer.get("result") or False, "note": answer.get("note") or False})
        return self.app_read()


class WorkshopOrderLine(models.Model):
    _name = "workshop.order.line"
    _description = "Work Order Service"
    _order = "order_id, sequence, id"

    _check_company_auto = True

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    service_id = fields.Many2one("workshop.service", "Service", check_company=True)
    name = fields.Char("Description", required=True)
    is_part = fields.Boolean("Part", help="A part or material rather than labour. Parts are billed as goods and "
                                          "stay out of the service invoice (NFS-e).")
    sector_id = fields.Many2one("workshop.sector", "Sector")
    user_id = fields.Many2one("res.users", "Mechanic", default=lambda self: self.env.user)
    quantity = fields.Float(default=1.0, digits=(10, 2))
    price_unit = fields.Monetary("Unit price", currency_field="currency_id")
    hours = fields.Float("Hours (each)", digits=(6, 2))
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True, currency_field="currency_id")
    approval = fields.Selection([("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                                default="pending", required=True)
    currency_id = fields.Many2one(related="order_id.currency_id")
    company_id = fields.Many2one(related="order_id.company_id", store=True)
    partner_id = fields.Many2one(related="order_id.partner_id", store=True, string="Customer")
    date = fields.Datetime(related="order_id.date_in", store=True)

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.onchange("service_id")
    def _onchange_service_id(self):
        if self.service_id:
            for key, value in self._vals_from_service(self.service_id).items():
                if key != "service_id":
                    self[key] = value

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("approval", "pending") != "pending" for vals in vals_list):
            self.env["workshop.order"]._check_office(_("Only the office can approve or refuse services."))
        lines = super().create(vals_list)
        for line in lines:
            if line.order_id.state == "approved" and line.order_id.partner_id.commercial_partner_id.workshop_auto_approve:
                # The contract approves the fleet's services in advance: the system approves, not the mechanic.
                line.sudo().approval = "approved"
            if line.service_id:
                # Mechanics cannot edit services; the usage counter is bookkeeping, not their edit.
                line.service_id.sudo().usage_count += 1
        return lines

    def write(self, vals):
        if "approval" in vals:
            self.env["workshop.order"]._check_office(_("Only the office can approve or refuse services."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_approved(self):
        if self.filtered(lambda l: l.approval == "approved"):
            self.env["workshop.order"]._check_office(_("Approved items can only be removed by the office."))

    def _service_rows(self, parts=False):
        """[(name, unit price, quantity, amount)] per service and price, refused lines left out, largest first.
        Services only, or parts only with parts=True.

        Shared by the closing report and the service invoice, so both show the same breakdown.
        """
        totals = {}
        for line in self.filtered(lambda l: l.approval != "rejected" and l.is_part == parts):
            row = totals.setdefault((line.name, line.price_unit), [0.0, 0.0])
            row[0] += line.quantity
            row[1] += line.subtotal
        return sorted(((name, price, qty, amount) for (name, price), (qty, amount) in totals.items()),
                      key=lambda row: -row[3])

    def _invoice_description(self, heading, orders_note=None, max_length=None):
        """Text of these services for a service invoice: the heading, one line per service and price
        ("- Revisão do alternador: 3 × R$ 280,00 = R$ 840,00"), the total and the orders. Parts are left out.

        Over max_length the orders go first, then the smallest services are summed into one "Other services"
        line, and as a last resort the heading is cut, so the note always fits and never loses its total.
        """
        currency = self.currency_id[:1] or self.env.company.currency_id

        def money(amount):
            # The note only takes plain spaces: a non-breaking one would be dropped and glue "R$" to the number.
            return format_amount(self.env, amount, currency).replace("\xa0", " ")

        rows = self._service_rows()
        total = sum(row[3] for row in rows)

        def build(kept, others, with_orders, heading=heading):
            lines = [heading]
            for name, price, qty, amount in kept:
                count = f"{qty:g}" if float(qty).is_integer() else formatLang(self.env, qty, digits=2)
                lines.append(f"- {name}: {count} × {money(price)} = {money(amount)}")
            if others:
                lines.append(_("- Other services: %s", money(others)))
            lines.append(_("Total: %s", money(total)))
            if orders_note and with_orders:
                lines.append(orders_note)
            return "\n".join(lines)

        text = build(rows, 0, True)
        if max_length and len(text) > max_length:
            kept, others = list(rows), 0.0
            text = build(kept, others, False)
            while len(text) > max_length and kept:
                others += kept.pop()[3]
                text = build(kept, others, False)
            if len(text) > max_length:
                cut = max(len(heading) - (len(text) - max_length) - 1, 0)
                text = build(kept, others, False, heading=heading[:cut].rstrip() + "…")[:max_length]
        return text

    @api.model
    def _vals_from_service(self, service):
        return {
            "service_id": service.id,
            "name": service.name,
            "is_part": service.is_part,
            "price_unit": service.list_price,
            "hours": service.hours,
            "sector_id": service.sector_id.id,
        }


class WorkshopOrderPhoto(models.Model):
    _name = "workshop.order.photo"
    _description = "Work Order Photo"
    _order = "create_date desc, id desc"

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade", index=True)
    url = fields.Char(required=True)
    thumb_url = fields.Char()
    public_id = fields.Char(help="Cloudinary public id, used to delete the image.")
    attachment_id = fields.Many2one("ir.attachment", help="Set when photos are stored in the database.")
    caption = fields.Char()
    kind = fields.Selection([("entry", "Arrival"), ("work", "During the job"), ("exit", "Delivery")], default="entry")
    show_to_customer = fields.Boolean(default=True)

    @api.constrains("url", "thumb_url", "attachment_id")
    def _check_image_source(self):
        """The app sends these values: only images kept by Odoo or on Cloudinary reach the order and the customer page."""
        for photo in self:
            for address in filter(None, (photo.url, photo.thumb_url)):
                if not address.startswith(("/web/image/", "https://res.cloudinary.com/")):
                    raise ValidationError(_("Photos must be stored in Odoo or on Cloudinary."))
            attachment = photo.attachment_id.sudo()
            if attachment and (attachment.res_model, attachment.res_id) != ("workshop.order", photo.order_id.id):
                raise ValidationError(_("The photo file belongs to another record."))

    def unlink(self):
        config = self._cloudinary_config()
        for photo in self.filtered(lambda p: config and p.public_id and p.public_id.startswith(config["folder"] + "/")):
            params = {"public_id": photo.public_id, "timestamp": int(time.time())}
            try:
                requests.post(
                    f"https://api.cloudinary.com/v1_1/{config['cloud_name']}/image/destroy",
                    data={**params, "api_key": config["api_key"],
                          "signature": self._cloudinary_sign(params, config["api_secret"])},
                    timeout=10,
                )
            except requests.RequestException:
                _logger.warning("Could not delete %s from Cloudinary", photo.public_id)
        self.attachment_id.unlink()
        return super().unlink()

    @api.model
    def _cloudinary_config(self):
        get = self.env["ir.config_parameter"].sudo().get_param
        if get(PARAM + "photo_storage") != "cloudinary":
            return {}
        config = {
            "cloud_name": (get(PARAM + "cloudinary_cloud_name") or "").strip(),
            "api_key": (get(PARAM + "cloudinary_api_key") or "").strip(),
            "api_secret": (get(PARAM + "cloudinary_api_secret") or "").strip(),
            "folder": (get(PARAM + "cloudinary_folder") or "").strip().strip("/") or "oficina",
        }
        return config if all(config.values()) else {}

    @staticmethod
    def _cloudinary_sign(params, secret):
        payload = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] not in (None, ""))
        return hashlib.sha1((payload + secret).encode()).hexdigest()

    @api.model
    def upload_ticket(self):
        """What the app needs to send a photo: a signed Cloudinary upload, or 'database' for direct upload to Odoo.

        The API secret never leaves the server; the browser only gets a short-lived signature.
        """
        config = self._cloudinary_config()
        if not config:
            return {"storage": "database"}
        params = {"folder": config["folder"], "timestamp": int(time.time())}
        return {
            "storage": "cloudinary",
            "url": f"https://api.cloudinary.com/v1_1/{config['cloud_name']}/image/upload",
            "api_key": config["api_key"],
            "signature": self._cloudinary_sign(params, config["api_secret"]),
            **params,
        }

    @api.model
    def add_photo(self, order_id, values):
        """Register a photo taken in the app. values: Cloudinary result (secure_url, public_id) or {data, name}."""
        order = self.env["workshop.order"].browse(order_id)
        order.check_access("write")
        vals = {"order_id": order.id, "kind": values.get("kind") or "entry", "caption": values.get("caption") or False}
        if values.get("secure_url"):
            url = values["secure_url"]
            folder = self._cloudinary_config().get("folder")
            public_id = values.get("public_id") or ""
            # Only ids in the shop's own folder: deleting the photo later destroys that id, signed with the secret.
            vals.update(url=url, public_id=public_id if folder and public_id.startswith(folder + "/") else False,
                        thumb_url=url.replace("/upload/", "/upload/c_fill,w_360,h_360,q_auto,f_auto/"))
        elif values.get("data"):
            attachment = self.env["ir.attachment"].create({
                "name": values.get("name") or f"{order.name}.jpg",
                "datas": values["data"],
                "res_model": "workshop.order",
                "res_id": order.id,
                "mimetype": "image/jpeg",
            })
            attachment.generate_access_token()
            vals.update(attachment_id=attachment.id,
                        url=f"/web/image/{attachment.id}?access_token={attachment.access_token}",
                        thumb_url=f"/web/image/{attachment.id}/360x360?access_token={attachment.access_token}")
        else:
            raise UserError(_("No image received."))
        self.create(vals)
        return order.app_read()


class WorkshopOrderChecklist(models.Model):
    _name = "workshop.order.checklist"
    _description = "Work Order Checklist Answer"
    _order = "order_id, sequence, id"

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade", index=True)
    template_id = fields.Many2one("workshop.checklist.template")
    sequence = fields.Integer(default=10)
    section = fields.Char()
    name = fields.Char(required=True)
    result = fields.Selection([("ok", "OK"), ("attention", "Attention"), ("fail", "Problem"), ("na", "N/A")])
    note = fields.Char()


class WorkshopOrderStageLog(models.Model):
    _name = "workshop.order.stage.log"
    _description = "Work Order Stage History"
    _order = "date_start desc, id desc"

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade", index=True)
    stage_id = fields.Many2one("workshop.stage", required=True)
    user_id = fields.Many2one("res.users")
    date_start = fields.Datetime(required=True)
    date_end = fields.Datetime()
    duration_hours = fields.Float(compute="_compute_duration", store=True,
                                  help="Time spent in the stage, set when the order leaves it (for reports).")
    elapsed_hours = fields.Float("Hours", compute="_compute_elapsed_hours",
                                 help="Time in the stage, counting up to now for the current one.")
    is_waiting = fields.Boolean(related="stage_id.is_waiting", store=True)

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for log in self:
            log.duration_hours = log._hours_until(log.date_end) if log.date_end else 0.0

    def _compute_elapsed_hours(self):
        now = fields.Datetime.now()
        for log in self:
            log.elapsed_hours = log._hours_until(log.date_end or now)

    def _hours_until(self, end):
        self.ensure_one()
        return max((end - self.date_start) / timedelta(hours=1), 0.0) if self.date_start else 0.0
