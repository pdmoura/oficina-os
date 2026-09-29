import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import {
    Component, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, useEffect, useRef, useState,
} from "@odoo/owl";

import {
    bindMethods, displayPlate, elapsedSince, formatBrPhone, isValidBrPhone, isValidPlate, normalizePlate, shareLink,
    shortDate, uploadPhoto,
} from "./utils";

const { DateTime } = luxon;

class Plate extends Component {
    static template = "workshop_os.AppPlate";
    static props = { plate: { type: String, optional: true }, size: { type: String, optional: true } };

    get text() {
        return displayPlate(this.props.plate || "") || "•••••••";
    }
}

/* ---------------------------------------------------------------------------------------------------------------
 * Home: the yard, filtered by stage, searchable by plate.
 * ------------------------------------------------------------------------------------------------------------- */
const STAGE_VIEW_KEY = "workshop_os.stage_view";

export class HomeScreen extends Component {
    static template = "workshop_os.AppHome";
    static components = { Plate };
    static props = { app: Object, theme: { type: String, optional: true } };

    setup() {
        bindMethods(this);
        this.orm = useService("orm");
        this.listRef = useRef("list");
        this.gridLabel = _t("Show stages as a grid");
        this.chipsLabel = _t("Show stages in a row");
        this.state = useState({
            data: null, search: "", stageId: null, loading: true, now: DateTime.now(), stageView: this.savedStageView(),
        });
        onWillStart(() => this.load());
        const tour = useService("workshop_tour");
        // Only after mounting: updating the parent while this screen is still starting would restart it.
        onMounted(() => {
            this.props.app.setMeta(this.state.data);
            tour.maybeStart("app");
        });
        const tick = setInterval(() => {
            this.state.now = DateTime.now();
            if (!document.hidden) {
                this.load(true);
            }
        }, 60000);
        onWillUnmount(() => clearInterval(tick));
    }

    async load(silent = false) {
        if (!silent) {
            this.state.loading = true;
        }
        const data = await this.orm.call("workshop.order", "app_home", [this.state.search]);
        this.state.data = data;
        this.state.loading = false;
        if (silent) {
            this.props.app.setMeta(data);
        }
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.load(true), 300);
    }

    get orders() {
        const orders = this.state.data?.orders || [];
        return this.state.stageId ? orders.filter((o) => o.stage_id === this.state.stageId) : orders;
    }

    stageCount(stageId) {
        return (this.state.data?.orders || []).filter((o) => o.stage_id === stageId).length;
    }

    /** Stages as a sliding row of chips or as a grid of cards; each phone remembers its mechanic's choice. */
    savedStageView() {
        try {
            return window.localStorage.getItem(STAGE_VIEW_KEY) === "grid" ? "grid" : "chips";
        } catch {
            return "chips";
        }
    }

    toggleStageView() {
        this.state.stageView = this.state.stageView === "grid" ? "chips" : "grid";
        try {
            window.localStorage.setItem(STAGE_VIEW_KEY, this.state.stageView);
        } catch {
            // Private browsing or blocked storage: the choice lasts until the app is closed.
        }
    }

    pickStage(stageId) {
        this.state.stageId = this.state.stageId === stageId ? null : stageId;
        if (this.state.stageView === "grid") {
            this.listRef.el?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    /** The symbol made for the current background. */
    get mark() {
        const company = this.state.data?.company;
        if (!company) {
            return { src: false, bare: false };
        }
        const light = this.props.theme === "light";
        return {
            src: light ? company.mark_light : company.mark,
            bare: light ? company.has_mark_light : company.has_mark,
        };
    }

    elapsed(order) {
        return elapsedSince(order.stage_since, this.state.now);
    }

    greeting() {
        const hour = DateTime.now().hour;
        const name = (this.state.data?.user.name || "").split(" ")[0];
        const part = hour < 12 ? _t("Good morning") : hour < 18 ? _t("Good afternoon") : _t("Good evening");
        return `${part}, ${name}`;
    }
}

/* ---------------------------------------------------------------------------------------------------------------
 * Search box that opens a scrollable list under it: tap to pick (several in a row when `multi`) or type to narrow
 * the list. The list comes from the server as the mechanic types, so a catalogue of hundreds stays quick to use.
 * ------------------------------------------------------------------------------------------------------------- */
export class SearchSelect extends Component {
    static template = "workshop_os.AppSearchSelect";
    static props = {
        placeholder: String,
        search: Function, // (query, limit) => Promise of [{ id, name, detail?, price_fmt?, is_part? }]
        selectedIds: Array,
        onPick: Function, // (item) => void
        multi: { type: Boolean, optional: true },
        createLabel: { type: String, optional: true },
        onCreate: { type: Function, optional: true }, // (typed text) => void: a last button creates what was typed
        limit: { type: Number, optional: true },
    };
    static defaultProps = { multi: false, limit: 100 };

    setup() {
        bindMethods(this);
        this.root = useRef("root");
        this.state = useState({ open: false, query: "", items: [], loading: false });
        const outside = (ev) => this.state.open && !this.root.el?.contains(ev.target) && this.close();
        onMounted(() => document.addEventListener("pointerdown", outside, true));
        onWillUnmount(() => {
            document.removeEventListener("pointerdown", outside, true);
            clearTimeout(this.timer);
        });
    }

    async open() {
        if (this.state.open) {
            return;
        }
        this.state.open = true;
        // Bring the box to the top, so the list has room above the phone's keyboard.
        this.root.el?.scrollIntoView({ block: "start", behavior: "smooth" });
        await this.load();
    }

    /** Closing forgets the search, so the list opens whole next time. */
    close() {
        Object.assign(this.state, { open: false, query: "" });
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        this.state.open = true;
        clearTimeout(this.timer);
        this.timer = setTimeout(this.load, 200);
    }

    async load() {
        const query = this.state.query;
        this.state.loading = true;
        const items = await this.props.search(query.trim(), this.props.limit);
        if (query === this.state.query) {
            Object.assign(this.state, { items, loading: false });
        }
    }

    get more() {
        return this.state.items.length >= this.props.limit;
    }

    isSelected(item) {
        return this.props.selectedIds.includes(item.id);
    }

    pick(item) {
        this.props.onPick(item);
        if (!this.props.multi) {
            this.close();
        }
    }

    create() {
        this.props.onCreate(this.state.query.trim());
        this.close();
    }
}

/* ---------------------------------------------------------------------------------------------------------------
 * Customer of an order, when opening it or correcting it: the one picked, a new one being typed in (created with the
 * order), or the search to find one.
 * ------------------------------------------------------------------------------------------------------------- */
export class CustomerField extends Component {
    static template = "workshop_os.AppCustomerField";
    static components = { SearchSelect };
    static props = {
        partner: { optional: true }, // { id, name, detail } or null
        newPartner: { optional: true }, // { name, phone, is_company } or null
        readonly: { type: Boolean, optional: true },
        onPick: Function,
        onNew: Function,
        onChangeNew: Function,
        onClear: Function,
    };

    setup() {
        bindMethods(this);
        this.orm = useService("orm");
        this.box = useRef("newPartner");
        // A new customer is typed in an open box; once the mechanic moves on, it shows as a customer like any other.
        this.state = useState({ expanded: !this.newPartnerComplete(this.props.newPartner), phoneTouched: false });
        onWillUpdateProps((next) => {
            if (next.newPartner && !this.props.newPartner) {
                Object.assign(this.state, { expanded: true, phoneTouched: false });
            }
        });
        const outside = (ev) => {
            if (this.state.expanded && this.props.newPartner && !this.box.el?.contains(ev.target)) {
                this.collapse();
            }
        };
        onMounted(() => {
            document.addEventListener("pointerdown", outside, true);
            document.addEventListener("focusin", outside, true);
        });
        onWillUnmount(() => {
            document.removeEventListener("pointerdown", outside, true);
            document.removeEventListener("focusin", outside, true);
        });
    }

    search(query) {
        return this.orm.call("workshop.order", "app_partners", [query]);
    }

    newPartnerComplete(partner) {
        return Boolean(partner?.name?.trim()) && isValidBrPhone(partner.phone);
    }

    collapse() {
        if (this.newPartnerComplete(this.props.newPartner)) {
            this.state.expanded = false;
        } else {
            this.state.phoneTouched = true; // stays open, showing what is missing
        }
    }

    expand() {
        this.state.expanded = true;
    }

    onPhoneInput(ev) {
        const phone = formatBrPhone(ev.target.value);
        ev.target.value = phone;
        this.props.onChangeNew("phone", phone);
    }

    get phoneError() {
        const partner = this.props.newPartner;
        return this.state.phoneTouched && partner && !isValidBrPhone(partner.phone);
    }
}

/* ---------------------------------------------------------------------------------------------------------------
 * New order: plate first, everything else pre-filled from the vehicle when it is known.
 * ------------------------------------------------------------------------------------------------------------- */
const DRAFT_KEY = "workshop_os.new_order_draft";

export class NewOrderScreen extends Component {
    static template = "workshop_os.AppNewOrder";
    static components = { Plate, SearchSelect, CustomerField };
    static props = { app: Object };

    setup() {
        bindMethods(this);
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.plateInput = useRef("plate");
        const draft = this.loadDraft();
        this.state = useState({
            form: null,
            lookup: null,
            looking: false,
            saving: false,
            step: draft?.plate?.length === 7 ? 2 : 1,
            values: {
                plate: "", partner_id: false, new_partner: null, brand: "", model: "", fleet_number: "", odometer: "",
                driver_name: "", complaint: "", stage_id: false, location_id: false, service_ids: [], template_id: false,
                ...(draft || {}),
            },
            // Names of what is picked: the lists themselves are searched on the server.
            serviceItems: {},
            partner: null,
        });
        onWillStart(async () => {
            const values = this.state.values;
            this.state.form = await this.orm.call("workshop.order", "app_new_form", [values.service_ids, values.partner_id]);
            for (const service of this.state.form.services) {
                this.state.serviceItems[service.id] = service;
            }
            values.service_ids = values.service_ids.filter((id) => id in this.state.serviceItems);
            this.state.partner = this.state.form.partner || null;
            values.partner_id = this.state.partner?.id || false;
            values.stage_id ||= this.state.form.stages[0]?.id || false;
            const entry = this.state.form.templates.find((t) => t.kind === "entry");
            if (!draft && entry) {
                this.state.values.template_id = entry.id;
            }
            if (this.state.values.plate.length === 7) {
                await this.lookup();
            }
        });
        onMounted(() => this.state.step === 1 && this.plateInput.el?.focus());
    }

    loadDraft() {
        try {
            return JSON.parse(window.localStorage.getItem(DRAFT_KEY) || "null");
        } catch {
            return null;
        }
    }

    saveDraft() {
        try {
            window.localStorage.setItem(DRAFT_KEY, JSON.stringify(this.state.values));
        } catch {
            // private mode: the draft simply is not kept
        }
    }

    clearDraft() {
        try {
            window.localStorage.removeItem(DRAFT_KEY);
        } catch {
            // nothing to clear
        }
    }

    get plateValid() {
        return isValidPlate(this.state.values.plate);
    }

    async onPlateInput(ev) {
        const plate = normalizePlate(ev.target.value);
        this.state.values.plate = plate;
        ev.target.value = plate;
        this.state.lookup = null;
        if (plate.length === 7) {
            await this.lookup();
        }
        this.saveDraft();
    }

    async lookup() {
        this.state.looking = true;
        const result = await this.orm.call("workshop.vehicle", "find_by_plate", [this.state.values.plate]);
        this.state.lookup = result;
        this.state.looking = false;
        if (result.partner_id) {
            // A known truck brings its customer; what was picked for another plate no longer applies.
            this.state.partner = null;
            Object.assign(this.state.values, { partner_id: result.partner_id, new_partner: null });
        }
    }

    continueFromPlate() {
        if (this.state.lookup?.open_order_id) {
            this.props.app.openOrder(this.state.lookup.open_order_id, true);
            return;
        }
        this.state.step = 2;
        this.saveDraft();
    }

    set(field, value) {
        this.state.values[field] = value;
        this.saveDraft();
    }

    searchServices(query, limit) {
        return this.orm.call("workshop.order", "app_services", [query, limit]);
    }

    toggleService(item) {
        const ids = this.state.values.service_ids;
        if (ids.includes(item.id)) {
            this.state.values.service_ids = ids.filter((id) => id !== item.id);
        } else {
            this.state.serviceItems[item.id] = item;
            this.state.values.service_ids = [...ids, item.id];
        }
        this.saveDraft();
    }

    get chosenServices() {
        return this.state.values.service_ids.map((id) => this.state.serviceItems[id]).filter(Boolean);
    }

    pickPartner(item) {
        this.state.partner = item;
        Object.assign(this.state.values, { partner_id: item.id, new_partner: null });
        this.saveDraft();
    }

    /** A customer not registered yet: created with the order, and the truck is registered to them. */
    newPartner(name) {
        this.state.partner = null;
        Object.assign(this.state.values, { partner_id: false, new_partner: { name, phone: "", is_company: true } });
        this.saveDraft();
    }

    setNewPartner(field, value) {
        this.state.values.new_partner[field] = value;
        this.saveDraft();
    }

    clearPartner() {
        this.state.partner = null;
        Object.assign(this.state.values, { partner_id: false, new_partner: null });
        this.saveDraft();
    }

    get odometerHint() {
        return this.state.lookup?.odometer ? String(this.state.lookup.odometer) : "0";
    }

    onChecklistToggle(ev) {
        const templates = this.state.form.templates;
        const entry = templates.find((t) => t.kind === "entry") || templates[0];
        this.set("template_id", ev.target.checked && entry ? entry.id : false);
    }

    get canSave() {
        const v = this.state.values;
        const newPartner = v.new_partner && v.new_partner.name?.trim() && isValidBrPhone(v.new_partner.phone);
        const customer = v.partner_id || this.state.lookup?.partner_id || newPartner;
        return this.plateValid && Boolean(customer) && !this.state.saving;
    }

    async save(forceNew = false) {
        this.state.saving = true;
        try {
            const v = this.state.values;
            const result = await this.orm.call("workshop.order", "app_create", [{
                ...v,
                odometer: Number(String(v.odometer).replace(/\D/g, "")) || 0,
                force_new: forceNew,
            }]);
            this.clearDraft();
            if (result.existing) {
                this.notification.add(_t("This vehicle already has an open order; opening it."), { type: "info" });
            }
            this.props.app.openOrder(result.id, true);
        } finally {
            this.state.saving = false;
        }
    }

    cancel() {
        this.clearDraft();
        this.props.app.back();
    }
}

/* ---------------------------------------------------------------------------------------------------------------
 * Order: stage, services, photos, checklist, history and the next step.
 * ------------------------------------------------------------------------------------------------------------- */
export class OrderScreen extends Component {
    static template = "workshop_os.AppOrder";
    static components = { Plate, CustomerField };
    static props = { app: Object, orderId: Number };

    setup() {
        bindMethods(this);
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInput = useRef("file");
        this.confirmDelete = useRef("confirmDelete");
        this.state = useState({
            data: null, tab: "services", uploading: 0, busy: false, picker: false, serviceSearch: "", services: [],
            photoKind: "entry", viewer: null, now: DateTime.now(), edit: null,
        });
        // The confirmation shows at the end of the edit sheet: bring it into view.
        useEffect(
            (asking) => {
                if (asking) {
                    this.confirmDelete.el?.scrollIntoView({ block: "center", behavior: "smooth" });
                }
            },
            () => [this.state.edit?.confirmDelete],
        );
        onWillStart(() => this.load());
        const tick = setInterval(() => (this.state.now = DateTime.now()), 60000);
        onWillUnmount(() => clearInterval(tick));
    }

    async load() {
        this.state.data = await this.orm.call("workshop.order", "app_read", [[this.props.orderId]]);
    }

    async run(method, args = []) {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call("workshop.order", method, [[this.props.orderId], ...args]);
        } finally {
            this.state.busy = false;
        }
    }

    setStage(stageId) {
        if (stageId !== this.state.data.stage_id) {
            return this.run("app_update", [{ stage_id: stageId }]);
        }
    }

    setLocation(locationId) {
        return this.run("app_update", [{ location_id: locationId === this.state.data.location_id ? false : locationId }]);
    }

    async openPicker() {
        this.state.picker = true;
        this.state.services = await this.orm.call("workshop.order", "app_services", [""]);
    }

    async searchServices(ev) {
        this.state.serviceSearch = ev.target.value;
        clearTimeout(this._timer);
        this._timer = setTimeout(async () => {
            this.state.services = await this.orm.call("workshop.order", "app_services", [this.state.serviceSearch]);
        }, 250);
    }

    async addService(serviceId) {
        await this.run("app_add_services", [[serviceId]]);
        this.notification.add(_t("Service added"), { type: "success" });
    }

    removeLine(lineId) {
        return this.run("app_remove_line", [lineId]);
    }

    /** Photos by moment of the job; the moment the order is in is highlighted, as the likely next photo. */
    get photoGroups() {
        const data = this.state.data;
        const photos = data?.photos || [];
        const current = ["done", "delivered"].includes(data?.state) ? "exit" : data?.state === "approved" ? "work" : "entry";
        return [
            { kind: "entry", icon: "fa-truck", title: _t("Arrival"),
              hint: _t("How the truck came in: front, sides, dashboard and any damage.") },
            { kind: "work", icon: "fa-wrench", title: _t("Job"),
              hint: _t("The fault and the repair: the customer sees them on the approval link.") },
            { kind: "exit", icon: "fa-check", title: _t("Delivery"),
              hint: _t("The truck ready to leave.") },
        ].map((group) => ({
            ...group,
            current: group.kind === current,
            // A photo without a moment counts as arrival, the default.
            photos: photos.filter((p) => (p.kind || "entry") === group.kind),
        }));
    }

    takePhoto(kind) {
        this.state.photoKind = kind;
        this.fileInput.el.click();
    }

    async onFiles(ev) {
        const files = Array.from(ev.target.files || []);
        ev.target.value = "";
        for (const file of files) {
            this.state.uploading++;
            try {
                this.state.data = await uploadPhoto(this.orm, this.props.orderId, file, this.state.photoKind);
            } catch (error) {
                this.notification.add(error.message || String(error), { type: "danger", title: _t("Photo not sent") });
            } finally {
                this.state.uploading--;
            }
        }
    }

    async answer(item, result) {
        const next = item.result === result ? "" : result;
        item.result = next;
        await this.orm.call("workshop.order", "app_save_checklist", [[this.props.orderId], { [item.id]: { result: next } }]);
    }

    loadChecklist(templateId) {
        return this.run("load_checklist", [templateId]);
    }

    get addedServiceIds() {
        return new Set((this.state.data?.lines || []).map((line) => line.service_id));
    }

    get checklistSections() {
        const sections = [];
        for (const item of this.state.data?.checklist || []) {
            let section = sections.find((s) => s.name === item.section);
            if (!section) {
                section = { name: item.section, items: [] };
                sections.push(section);
            }
            section.items.push(item);
        }
        return sections;
    }

    get checklistDone() {
        const items = this.state.data?.checklist || [];
        return items.filter((i) => i.result).length;
    }

    async doAction(action) {
        await this.run("app_action", [action]);
        if (action === "action_done") {
            // Tapped by mistake: undo right here, or later with "Reopen" while the truck is still in the yard.
            const close = this.notification.add(_t("Marked as ready."), {
                type: "success",
                buttons: [{
                    name: _t("Undo"),
                    primary: true,
                    onClick: () => {
                        close();
                        this.doAction("action_undo_done");
                    },
                }],
            });
        } else {
            this.notification.add(action === "action_undo_done" ? _t("Back to the job.") : _t("Updated"), { type: "success" });
        }
    }

    /* Corrections: the truck, the customer while nobody approved, the arrival details; and deleting a mistake. */
    openEdit() {
        const d = this.state.data;
        this.state.edit = {
            saving: false,
            confirmDelete: false,
            partner: { id: d.partner_id, name: d.partner, detail: d.partner_detail },
            values: {
                plate: d.plate, brand: d.brand, model: d.model, fleet_number: d.fleet_number,
                odometer: d.odometer ? String(d.odometer) : "", driver_name: d.driver_name, complaint: d.complaint,
                diagnosis: d.diagnosis, partner_id: d.partner_id, new_partner: null,
            },
        };
    }

    closeEdit() {
        this.state.edit = null;
    }

    setEdit(field, value) {
        this.state.edit.values[field] = value;
    }

    editPickPartner(item) {
        this.state.edit.partner = item;
        Object.assign(this.state.edit.values, { partner_id: item.id, new_partner: null });
    }

    editNewPartner(name) {
        this.state.edit.partner = null;
        Object.assign(this.state.edit.values, { partner_id: false, new_partner: { name, phone: "", is_company: true } });
    }

    editChangeNewPartner(field, value) {
        this.state.edit.values.new_partner[field] = value;
    }

    editClearPartner() {
        this.state.edit.partner = null;
        Object.assign(this.state.edit.values, { partner_id: false, new_partner: null });
    }

    get canSaveEdit() {
        const edit = this.state.edit;
        const newPartner = edit?.values.new_partner;
        const valid = newPartner ? newPartner.name?.trim() && isValidBrPhone(newPartner.phone) : edit?.values.partner_id;
        return Boolean(edit && !edit.saving && valid);
    }

    async saveEdit() {
        const edit = this.state.edit;
        edit.saving = true;
        try {
            await this.run("app_edit", [{ ...edit.values }]);
            this.state.edit = null;
            this.notification.add(_t("Order updated."), { type: "success" });
        } finally {
            edit.saving = false;
        }
    }

    async deleteOrder() {
        const name = this.state.data.name;
        await this.orm.call("workshop.order", "app_delete", [[this.props.orderId]]);
        this.notification.add(_t("%s deleted.", name), { type: "success" });
        this.props.app.home();
    }

    share() {
        const d = this.state.data;
        return shareLink(d.public_url, _t("Work order %(name)s, %(plate)s:", { name: d.name, plate: displayPlate(d.plate) }));
    }

    elapsed() {
        return elapsedSince(this.state.data.stage_since, this.state.now);
    }

    date(value) {
        return shortDate(value);
    }

    hours(value) {
        const h = Math.floor(value);
        const m = Math.round((value - h) * 60);
        return h ? `${h}h${m ? String(m).padStart(2, "0") : ""}` : `${m} min`;
    }
}
