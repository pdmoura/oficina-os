import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";

import {
    bindMethods, brandStyle, displayPlate, elapsedSince, saveWorkshopTheme, workshopTheme,
} from "@workshop_os/app/utils";

/** Office cockpit: what is in the yard, what is late, what is ready and what the month brought in. */
export class WorkshopDashboard extends Component {
    static template = "workshop_os.Dashboard";
    static props = ["*"];

    setup() {
        bindMethods(this);
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, theme: workshopTheme() });
        this.lightLabel = _t("Light theme");
        this.darkLabel = _t("Dark theme");
        onWillStart(() => this.load());
        const timer = setInterval(() => !document.hidden && this.load(), 60000);
        onWillUnmount(() => clearInterval(timer));
    }

    async load() {
        this.state.data = await this.orm.call("workshop.order", "dashboard_data", []);
    }

    plate(value) {
        return displayPlate(value);
    }

    elapsed(value) {
        return elapsedSince(value);
    }

    openOrders(domain, name) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: "workshop.order",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain,
            context: { workshop_used_stages_only: true },
        });
    }

    /** The KPI cards open the matching orders, titled like the card so the breadcrumb reads in the user's language. */
    openKpi(kind) {
        const kpis = {
            open: [_t("In the yard"), [["state", "in", ["draft", "approved", "done"]]]],
            late: [_t("Late"), [["is_late", "=", true]]],
            to_approve: [_t("Awaiting approval"), [["state", "=", "draft"]]],
            ready: [_t("Ready for pickup"), [["state", "=", "done"]]],
        };
        const [name, domain] = kpis[kind];
        return this.openOrders(domain, name);
    }

    openStage(stage) {
        return this.openOrders([["stage_id", "=", stage.id], ["state", "in", ["draft", "approved", "done"]]], stage.name);
    }

    openOrder(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "workshop.order", res_id: id,
                                      views: [[false, "form"]] });
    }

    openKanban() {
        return this.action.doAction("workshop_os.workshop_order_action");
    }

    openApp() {
        return this.action.doAction("workshop_os.workshop_order_action_mechanic_app");
    }

    toggleTheme() {
        this.state.theme = this.state.theme === "light" ? "dark" : "light";
        return saveWorkshopTheme(this.state.theme);
    }

    get accentStyle() {
        return brandStyle(this.state.data?.company, this.state.theme);
    }

    /** The full logo made for the current background, when the company has one. */
    get logo() {
        const company = this.state.data?.company;
        if (!company) {
            return false;
        }
        return this.state.theme === "light"
            ? company.has_logo_light && company.logo_light
            : company.has_logo_dark && company.logo_dark;
    }
}

registry.category("actions").add("workshop_os.dashboard", WorkshopDashboard);
