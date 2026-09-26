import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";

import { displayPlate, elapsedSince } from "@workshop_os/app/utils";

/** Office cockpit: what is in the yard, what is late, what is ready and what the month brought in. */
export class WorkshopDashboard extends Component {
    static template = "workshop_os.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null });
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
        });
    }

    openStage(stage) {
        return this.openOrders([["stage_id", "=", stage.id], ["state", "in", ["draft", "approved", "done"]]], stage.name);
    }

    openOrder(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: "workshop.order", res_id: id,
                                      views: [[false, "form"]] });
    }

    openKanban() {
        return this.action.doAction("workshop_os.action_workshop_order");
    }

    openApp() {
        return this.action.doAction("workshop_os.action_mechanic_app");
    }

    get accentStyle() {
        return this.state.data ? `--wo-accent: ${this.state.data.company.accent};` : "";
    }
}

registry.category("actions").add("workshop_os.dashboard", WorkshopDashboard);
