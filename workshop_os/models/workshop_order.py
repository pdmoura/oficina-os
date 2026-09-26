import secrets
from datetime import timedelta
from urllib.parse import quote

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import consteq, format_amount

from .workshop_vehicle import PLATE_RE, format_plate, normalize_plate

OPEN_STATES = ("draft", "approved", "done")


class WorkshopOrder(models.Model):
    _name = "workshop.order"
    _description = "Work Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, date_in desc, id desc"
    _rec_names_search = ["name", "vehicle_id.plate", "partner_id.name", "vehicle_id.fleet_number"]

    name = fields.Char("Number", readonly=True, copy=False, default="/", index=True)
    partner_id = fields.Many2one("res.partner", "Customer", required=True, index=True, tracking=True)
    vehicle_id = fields.Many2one("workshop.vehicle", "Vehicle", required=True, index=True, tracking=True,
                                 domain="['|', ('partner_id', '=', False), ('partner_id', '=', partner_id)]")
    plate = fields.Char(related="vehicle_id.plate_display", string="Plate")
    odometer = fields.Integer("Odometer (km)")
    driver_name = fields.Char("Brought by", help="Driver or employee of the customer who brought the vehicle.")
    stage_id = fields.Many2one("workshop.stage", "Stage", index=True, tracking=True, group_expand="_read_group_stage_ids",
                               default=lambda self: self.env["workshop.stage"].search([], limit=1))
    stage_color = fields.Char(related="stage_id.color")
    location_id = fields.Many2one("workshop.location", "Location", tracking=True)
    sector_id = fields.Many2one("workshop.sector", "Sector")
    user_id = fields.Many2one("res.users", "Mechanic", tracking=True, default=lambda self: self.env.user,
                              domain=lambda self: [("group_ids", "in", self.env.ref("workshop_os.group_workshop_user").id)])
    priority = fields.Selection([("0", "Normal"), ("1", "Urgent")], default="0")
    state = fields.Selection([
        ("draft", "Awaiting approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("done", "Ready"),
        ("delivered", "Delivered"),
        ("cancel", "Cancelled"),
    ], default="draft", required=True, tracking=True, index=True, copy=False)
    date_in = fields.Datetime("Arrived", default=fields.Datetime.now, required=True, index=True)
    date_promised = fields.Datetime("Promised for", tracking=True)
    date_done = fields.Datetime("Ready on", readonly=True, copy=False)
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
    amount_approved = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    hours_total = fields.Float("Labour hours", compute="_compute_amounts", store=True)
    photo_count = fields.Integer(compute="_compute_counts")
    checklist_progress = fields.Integer(compute="_compute_counts", help="Answered checklist items, in %.")

    is_late = fields.Boolean(compute="_compute_is_late", search="_search_is_late")
    stage_since = fields.Datetime(compute="_compute_stage_since")
    warranty_text = fields.Text(default=lambda self: self.env.company.workshop_warranty_text)

    access_token = fields.Char(copy=False, default=lambda self: secrets.token_urlsafe(24), readonly=True)
    approved_by = fields.Char("Approved by", readonly=True, copy=False)
    approved_on = fields.Datetime(readonly=True, copy=False)
    approval_signature = fields.Image(readonly=True, copy=False, max_width=1024, max_height=512)
    billing_id = fields.Many2one("workshop.billing", "Monthly closing", readonly=True, copy=False, index=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("line_ids.subtotal", "line_ids.approval", "line_ids.hours", "line_ids.quantity")
    def _compute_amounts(self):
        for order in self:
            lines = order.line_ids.filtered(lambda l: l.approval != "rejected")
            order.amount_total = sum(lines.mapped("subtotal"))
            order.amount_approved = sum(lines.filtered(lambda l: l.approval == "approved").mapped("subtotal"))
            order.hours_total = sum(l.hours * l.quantity for l in lines)

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
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(_("Unsupported search on late orders."))
        late = [("date_promised", "<", fields.Datetime.now()), ("state", "in", OPEN_STATES)]
        return late if (operator == "=") == value else ["!", "&", *late]

    @api.depends("stage_log_ids.date_start")
    def _compute_stage_since(self):
        for order in self:
            open_log = order.stage_log_ids.filtered(lambda l: not l.date_end)[:1]
            order.stage_since = open_log.date_start or order.date_in

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([], order=stages._order)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("workshop.order") or "/"
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
        stage_changed = "stage_id" in vals
        res = super().write(vals)
        if stage_changed:
            for order in self:
                order._log_stage_change()
        if vals.get("odometer"):
            for order in self.filtered(lambda o: o.odometer > o.vehicle_id.odometer):
                order.vehicle_id.odometer = order.odometer
        return res

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

    @api.constrains("vehicle_id", "partner_id")
    def _check_vehicle_owner(self):
        for order in self:
            owner = order.vehicle_id.partner_id
            if owner and owner.commercial_partner_id != order.partner_id.commercial_partner_id:
                raise ValidationError(_("Vehicle %(plate)s belongs to %(owner)s, not to %(partner)s.",
                                        plate=order.plate, owner=owner.display_name, partner=order.partner_id.display_name))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_approve(self):
        for order in self.filtered(lambda o: o.state in ("draft", "rejected")):
            order.line_ids.filtered(lambda l: l.approval == "pending").approval = "approved"
            order.write({"state": "approved", "approved_by": self.env.user.name, "approved_on": fields.Datetime.now()})
        return True

    def action_reject(self):
        self.filtered(lambda o: o.state == "draft").write({"state": "rejected"})
        return True

    def action_done(self):
        for order in self:
            if order.state not in ("draft", "approved"):
                raise UserError(_("%s cannot be marked ready from its current status.", order.name))
            if not order.line_ids:
                raise UserError(_("Add at least one service to %s before marking it ready.", order.name))
        self.write({"state": "done", "date_done": fields.Datetime.now()})
        return True

    def action_deliver(self):
        for order in self:
            if order.state != "done":
                raise UserError(_("Mark %s as ready before delivering it.", order.name))
        self.write({"state": "delivered", "date_delivered": fields.Datetime.now()})
        return True

    def action_cancel(self):
        if self.filtered("billing_id"):
            raise UserError(_("Orders already included in a monthly closing cannot be cancelled."))
        self.write({"state": "cancel"})
        return True

    def action_reopen(self):
        if self.filtered("billing_id"):
            raise UserError(_("Orders already included in a monthly closing cannot be reopened."))
        self.write({"state": "approved", "date_done": False, "date_delivered": False})
        return True

    # ------------------------------------------------------------------
    # Customer link (approval and tracking)
    # ------------------------------------------------------------------
    def get_public_url(self):
        self.ensure_one()
        return f"{self.get_base_url()}/os/{self.access_token}"

    @api.model
    def _get_by_token(self, token):
        """Order for a public link token, compared in constant time; empty recordset if none."""
        if not token or len(token) < 16:
            return self.browse()
        order = self.sudo().search([("access_token", "=", token)], limit=1)
        return order if order and consteq(order.access_token, token) else self.browse()

    def customer_decide(self, approve, name, signature=None, line_ids=None):
        """Approval or rejection sent from the public page (already token-checked, runs as sudo)."""
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

    def action_copy_public_url(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"type": "info", "sticky": True, "title": _("Customer link"), "message": self.get_public_url()},
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
    # Mechanic app API: one call per screen, because every round trip to the database costs latency
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
            "user": {"name": self.env.user.name, "is_manager": self.env.user.has_group("workshop_os.group_workshop_manager")},
            "company": {
                "name": self.env.company.name,
                "logo": f"/web/image/res.company/{self.env.company.id}/logo/256x256",
                "accent": self.env.company.workshop_accent_color or "#E8B21E",
            },
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
            "company": {"name": self.env.company.name, "accent": self.env.company.workshop_accent_color or "#E8B21E"},
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
    def app_new_form(self):
        """Everything the new-order screen needs, in one call."""
        services = self.env["workshop.service"].search([], limit=60)
        partners = self.env["res.partner"].search([("workshop_customer", "=", True)], limit=50)
        return {
            "stages": [{"id": s.id, "name": s.name, "color": s.color} for s in self.env["workshop.stage"].search([])],
            "locations": [{"id": l.id, "name": l.name} for l in self.env["workshop.location"].search([])],
            "sectors": [{"id": s.id, "name": s.name} for s in self.env["workshop.sector"].search([])],
            "services": [{"id": s.id, "name": s.name, "price": s.list_price, "hours": s.hours, "favorite": s.favorite,
                          "price_fmt": format_amount(self.env, s.list_price, s.currency_id),
                          "sector_id": s.sector_id.id} for s in services],
            "partners": [{"id": p.id, "name": p.display_name} for p in partners],
            "templates": [{"id": t.id, "name": t.name, "kind": t.kind}
                          for t in self.env["workshop.checklist.template"].search([])],
        }

    @api.model
    def app_create(self, values):
        """Create an order from the mechanic app, registering the vehicle on the fly when the plate is new."""
        plate = normalize_plate(values.get("plate"))
        if not PLATE_RE.match(plate):
            raise UserError(_("%s is not a valid plate.", plate or _("Empty plate")))
        Vehicle = self.env["workshop.vehicle"]
        vehicle = Vehicle.search([("plate", "=", plate)], limit=1)
        partner_id = values.get("partner_id") or vehicle.partner_id.id
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
            "lines": [{
                "id": l.id, "name": l.name, "quantity": l.quantity, "price": l.price_unit, "subtotal": l.subtotal,
                "subtotal_fmt": format_amount(self.env, l.subtotal, self.currency_id),
                "hours": l.hours, "approval": l.approval,
            } for l in self.line_ids],
            "state_actions": self._app_state_actions(),
            "photos": [{"id": p.id, "url": p.url, "thumb": p.thumb_url, "caption": p.caption or "", "kind": p.kind}
                       for p in self.photo_ids],
            "checklist": [{"id": c.id, "section": c.section or "", "name": c.name, "result": c.result or "",
                           "note": c.note or ""} for c in self.checklist_line_ids],
            "timeline": [{"stage": log.stage_id.name, "color": log.stage_id.color, "start": fields.Datetime.to_string(log.date_start),
                          "hours": round(log.duration_hours, 2), "user": log.user_id.name}
                         for log in self.stage_log_ids.sorted("date_start")],
            "stages": [{"id": s.id, "name": s.name, "color": s.color} for s in self.env["workshop.stage"].search([])],
            "locations": [{"id": l.id, "name": l.name} for l in self.env["workshop.location"].search([])],
            "templates": [{"id": t.id, "name": t.name} for t in self.env["workshop.checklist.template"].search([])],
        }

    def _app_state_actions(self):
        """Buttons the app shows for the current status, respecting the user's role."""
        self.ensure_one()
        manager = self.env.user.has_group("workshop_os.group_workshop_manager")
        actions = []
        if self.state in ("draft", "rejected") and manager:
            actions.append({"action": "action_approve", "label": _("Approve"), "style": "primary"})
        if self.state in ("draft", "approved"):
            actions.append({"action": "action_done", "label": _("Job ready"), "style": "primary" if self.state == "approved" else "ghost"})
        if self.state == "done":
            actions.append({"action": "action_deliver", "label": _("Delivered"), "style": "primary"})
        return actions

    @api.model
    def app_services(self, search=""):
        domain = [("name", "ilike", search)] if search else []
        return [{"id": s.id, "name": s.name, "price_fmt": format_amount(self.env, s.list_price, s.currency_id),
                 "hours": s.hours, "favorite": s.favorite}
                for s in self.env["workshop.service"].search(domain, limit=40)]

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

    def app_remove_line(self, line_id):
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.id == line_id)
        if line and line.approval == "approved" and not self.env.user.has_group("workshop_os.group_workshop_manager"):
            raise UserError(_("Approved items can only be removed by the office."))
        line.unlink()
        return self.app_read()

    def app_action(self, action):
        self.ensure_one()
        if action not in ("action_done", "action_deliver", "action_approve"):
            raise UserError(_("Unknown action."))
        if action == "action_approve" and not self.env.user.has_group("workshop_os.group_workshop_manager"):
            raise UserError(_("Only the office can approve an order."))
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

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    service_id = fields.Many2one("workshop.service", "Service")
    name = fields.Char("Description", required=True)
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

    @api.model
    def _vals_from_service(self, service):
        return {
            "service_id": service.id,
            "name": service.name,
            "price_unit": service.list_price,
            "hours": service.hours,
            "sector_id": service.sector_id.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.order_id.state == "approved" and line.order_id.partner_id.commercial_partner_id.workshop_auto_approve:
                line.approval = "approved"
            if line.service_id:
                line.service_id.sudo().usage_count += 1
        return lines


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


class WorkshopOrderStageLog(models.Model):
    _name = "workshop.order.stage.log"
    _description = "Work Order Stage History"
    _order = "date_start desc, id desc"

    order_id = fields.Many2one("workshop.order", required=True, ondelete="cascade", index=True)
    stage_id = fields.Many2one("workshop.stage", required=True)
    user_id = fields.Many2one("res.users")
    date_start = fields.Datetime(required=True)
    date_end = fields.Datetime()
    duration_hours = fields.Float(compute="_compute_duration", store=True)
    is_waiting = fields.Boolean(related="stage_id.is_waiting", store=True)

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        now = fields.Datetime.now()
        for log in self:
            end = log.date_end or now
            log.duration_hours = max((end - log.date_start) / timedelta(hours=1), 0.0) if log.date_start else 0.0
