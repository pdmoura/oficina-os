import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";

import {
    bindMethods, displayPlate, elapsedSince, isValidPlate, normalizePlate, shareLink, shortDate, uploadPhoto,
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
export class HomeScreen extends Component {
    static template = "workshop_os.AppHome";
    static components = { Plate };
    static props = { app: Object };

    setup() {
        bindMethods(this);
        this.orm = useService("orm");
        this.state = useState({ data: null, search: "", stageId: null, loading: true, now: DateTime.now() });
        onWillStart(() => this.load());
        // Only after mounting: updating the parent while this screen is still starting would restart it.
        onMounted(() => this.props.app.setMeta(this.state.data));
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
 * New order: plate first, everything else pre-filled from the vehicle when it is known.
 * ------------------------------------------------------------------------------------------------------------- */
const DRAFT_KEY = "workshop_os.new_order_draft";

export class NewOrderScreen extends Component {
    static template = "workshop_os.AppNewOrder";
    static components = { Plate };
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
                plate: "", partner_id: false, brand: "", model: "", fleet_number: "", odometer: "", driver_name: "",
                complaint: "", stage_id: false, location_id: false, service_ids: [], template_id: false,
                ...(draft || {}),
            },
            serviceSearch: "",
        });
        onWillStart(async () => {
            this.state.form = await this.orm.call("workshop.order", "app_new_form", []);
            this.state.values.stage_id ||= this.state.form.stages[0]?.id || false;
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
        if (result.found) {
            Object.assign(this.state.values, {
                partner_id: result.partner_id || this.state.values.partner_id,
                odometer: this.state.values.odometer || "",
            });
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

    toggleService(id) {
        const ids = this.state.values.service_ids;
        this.state.values.service_ids = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
        this.saveDraft();
    }

    get services() {
        const search = this.state.serviceSearch.trim().toLowerCase();
        const all = this.state.form?.services || [];
        const list = search ? all.filter((s) => s.name.toLowerCase().includes(search)) : all.filter((s) => s.favorite);
        const chosen = all.filter((s) => this.state.values.service_ids.includes(s.id) && !list.includes(s));
        return [...chosen, ...list].slice(0, 30);
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
        return this.plateValid && (v.partner_id || this.state.lookup?.partner_id) && !this.state.saving;
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
    static components = { Plate };
    static props = { app: Object, orderId: Number };

    setup() {
        bindMethods(this);
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInput = useRef("file");
        this.state = useState({
            data: null, tab: "services", uploading: 0, busy: false, picker: false, serviceSearch: "", services: [],
            photoKind: "entry", viewer: null, now: DateTime.now(),
        });
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
        this.notification.add(_t("Updated"), { type: "success" });
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
