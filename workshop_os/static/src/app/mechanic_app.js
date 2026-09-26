import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";

import { HomeScreen, NewOrderScreen, OrderScreen } from "./screens";

/**
 * Full-screen app for mechanics (client action with target "fullscreen"). Screens live in a small stack so the back
 * button of the app behaves like a phone app, and each screen loads its data in one server call.
 */
export class MechanicApp extends Component {
    static template = "workshop_os.MechanicApp";
    static components = { HomeScreen, NewOrderScreen, OrderScreen };
    static props = ["*"];

    setup() {
        this.action = useService("action");
        const start = [{ screen: "home", key: 1 }];
        const orderId = this.props.action?.context?.active_id;
        if (orderId) {
            start.push({ screen: "order", orderId, key: 2 });
        }
        this.state = useState({ stack: start, meta: null, menu: false });
        this._key = 10;
        this.api = {
            openOrder: (id, replace) => this.push({ screen: "order", orderId: id }, replace),
            newOrder: () => this.push({ screen: "new" }),
            back: () => this.back(),
            home: () => (this.state.stack = [{ screen: "home", key: ++this._key }]),
            setMeta: (data) => {
                const meta = data && { company: data.company, user: data.user };
                if (meta && JSON.stringify(meta) !== JSON.stringify(this.state.meta)) {
                    this.state.meta = meta;
                }
            },
            toggleMenu: () => (this.state.menu = !this.state.menu),
            refresh: () => {
                this.state.menu = false;
                this.api.home();
            },
            openOffice: () => this.action.doAction("workshop_os.action_workshop_order"),
            logout: () => (window.location.href = "/web/session/logout"),
        };
    }

    get current() {
        return this.state.stack[this.state.stack.length - 1];
    }

    push(entry, replace = false) {
        const stack = replace ? this.state.stack.slice(0, -1) : this.state.stack.slice();
        stack.push({ ...entry, key: ++this._key });
        this.state.stack = stack;
        window.scrollTo(0, 0);
    }

    back() {
        if (this.state.stack.length > 1) {
            this.state.stack = this.state.stack.slice(0, -1);
            const home = this.state.stack[this.state.stack.length - 1];
            home.key = ++this._key; // refresh the screen we return to
        }
    }

    get accentStyle() {
        const accent = this.state.meta?.company?.accent;
        return accent ? `--wo-accent: ${accent};` : "";
    }
}

registry.category("actions").add("workshop_os.mechanic_app", MechanicApp);
