import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, reactive, useEffect, useRef, useState } from "@odoo/owl";

/**
 * Guided tour of the main screens: a card per step that points at the part of the screen it talks about.
 *
 * Two tracks: "office" (dashboard, order board, an order, the mechanic app, customers, monthly closing, settings)
 * and "app" (the mechanic app). Each opens by itself the first time a user reaches the dashboard or the app, and
 * again from the user menu or the app menu. On a computer the card sits next to what it points at; on a phone it is
 * a sheet at the bottom, or at the top when what it points at would be hidden under it.
 *
 * A step is { title, body, page, target, open, when, optional }: `target` is the selector to point at (none: the
 * card is centred), `page` the screen it belongs to (a client action tag, a model, or "model#form"), `open` brings
 * that screen when another one is showing or the target is missing, `when` leaves the step out (no order yet, no
 * settings rights), `optional` skips it when the target never shows up.
 */

const SMALL = 768;
const WAIT_MS = 5000;

const sleep = (ms) => new Promise((resolve) => browser.setTimeout(resolve, ms));

/** First element of a comma-separated selector list that is on screen. */
function findTarget(selector) {
    if (!selector) {
        return null;
    }
    for (const part of selector.split(",")) {
        for (const el of document.querySelectorAll(part.trim())) {
            const rect = el.getBoundingClientRect();
            if (rect.width && rect.height) {
                return el;
            }
        }
    }
    return null;
}

/** The screen showing now, in the terms of a step's `page`. */
function currentPage(action) {
    const controller = action.currentController;
    const current = controller?.action;
    if (!current) {
        return null;
    }
    if (current.type === "ir.actions.client") {
        return current.tag;
    }
    const form = controller.view?.type === "form" && current.res_model !== "res.config.settings";
    return form ? `${current.res_model}#form` : current.res_model;
}

async function waitFor(selector, ms = WAIT_MS) {
    const end = Date.now() + ms;
    while (Date.now() < end) {
        const el = findTarget(selector);
        if (el) {
            return el;
        }
        await sleep(100);
    }
    return null;
}

function officeSteps({ action, orm }) {
    let orderId = null;
    const open = (xmlid) => () => action.doAction(xmlid, { clearBreadcrumbs: true });
    return [
        {
            page: "workshop_os.dashboard",
            screen: ".o_workshop_dashboard",
            open: open("workshop_os.workshop_order_action_dashboard"),
            title: _t("Welcome to %s", session.workshop_app_name || "Oficina"),
            body: _t("A short tour of the office's day: the dashboard, the orders, the mechanic app, customers, the monthly closing and the settings. It takes about two minutes."),
        },
        {
            target: ".o_workshop_dash_kpis",
            page: "workshop_os.dashboard",
            open: open("workshop_os.workshop_order_action_dashboard"),
            title: _t("The day at a glance"),
            body: _t("Trucks in the shop, late orders, quotes waiting for approval, trucks ready for pickup and what the month brought in. Each card opens its orders."),
        },
        {
            target: ".o_workshop_dash_stages",
            page: "workshop_os.dashboard",
            open: open("workshop_os.workshop_order_action_dashboard"),
            title: _t("Where every truck is"),
            body: _t("One card per stage of the shop, with how many trucks are in it. Tap a stage to see them."),
        },
        {
            target: ".o_workshop_dash_grid",
            page: "workshop_os.dashboard",
            open: open("workshop_os.workshop_order_action_dashboard"),
            title: _t("What needs attention"),
            body: _t("Late orders, trucks ready for pickup and the month's customers, each one a tap away."),
        },
        {
            target: ".o_workshop_dash_head__actions",
            page: "workshop_os.dashboard",
            open: open("workshop_os.workshop_order_action_dashboard"),
            title: _t("Theme, app and board"),
            body: _t("Switch between the light and the dark theme, open the mechanic app, or see every order on the board."),
        },
        {
            target: ".o_kanban_renderer",
            page: "workshop.order",
            open: open("workshop_os.workshop_order_action"),
            title: _t("The order board"),
            body: _t("Every open order by stage. Drag a card to another stage or open it for the details. On a phone, swipe between the stages."),
        },
        {
            when: async () => {
                [orderId] = await orm.search("workshop.order", [["state", "in", ["draft", "approved", "done"]]], {
                    limit: 1,
                    order: "id desc",
                });
                return Boolean(orderId);
            },
            target: ".o_form_view .o_form_statusbar",
            page: "workshop.order#form",
            open: () => action.doAction(
                { type: "ir.actions.act_window", res_model: "workshop.order", res_id: orderId, views: [[false, "form"]] },
                { clearBreadcrumbs: true },
            ),
            title: _t("An order's buttons"),
            body: _t("Approve or reject the quote, send it on WhatsApp, copy the customer link (they approve on the phone, with a signature) and print. On the right, the order's progress."),
        },
        {
            when: async () => Boolean(orderId),
            target: ".o_form_view .o_notebook_headers",
            optional: true,
            title: _t("An order's sections"),
            body: _t("Services and prices, problem and diagnosis, checklist, photos by moment (arrival, job, delivery), stage history and approval. On a phone, pick the section in this list."),
        },
        {
            target: ".o_workshop_app_top",
            page: "workshop_os.mechanic_app",
            open: open("workshop_os.workshop_order_action_mechanic_app"),
            title: _t("The mechanic app"),
            body: _t("What the mechanics use on their phones: receive a truck from the plate, move it through the stages, add services, photos and the checklist. You can use it too."),
        },
        {
            target: ".o_control_panel_main_buttons",
            page: "res.partner",
            open: open("workshop_os.res_partner_action_workshop_customer"),
            title: _t("Customers and trucks"),
            body: _t("Register the fleets and their trucks here. A fleet on contract can have its quotes approved automatically."),
        },
        {
            target: ".o_control_panel_main_buttons",
            page: "workshop.billing",
            open: open("workshop_os.workshop_billing_action"),
            title: _t("Monthly closing"),
            body: _t("At the end of the month, one closing per fleet: load the finished orders, confirm, print the report and issue the NFS-e with one click."),
        },
        {
            when: () => user.hasGroup("base.group_system"),
            target: ".app_settings_block[data-key='workshop_os'] h2, .app_settings_block[data-key='workshop_os']",
            screen: ".o_setting_container, .o_settings_container, .app_settings_block",
            page: "res.config.settings",
            open: open("workshop_os.res_config_settings_action"),
            title: _t("Your shop's settings"),
            body: _t("Logos and colours, warranty and approval texts, where the photos are kept and the NFS-e. Services, stages, bays and users are in the Configuration menu."),
        },
        {
            screen: ".o_workshop_dashboard",
            target: ".o_user_menu, .o_mobile_menu_toggle",
            page: "workshop_os.dashboard",
            open: open("workshop_os.workshop_order_action_dashboard"),
            title: _t("All set"),
            body: _t("Open this tour again whenever you like from your user menu, at the top right."),
        },
    ];
}

function appSteps({ action }) {
    const home = ".o_workshop_app_top";
    const openApp = () => action.doAction("workshop_os.workshop_order_action_mechanic_app", { clearBreadcrumbs: true });
    const toHome = async () => {
        const back = findTarget(".o_workshop_app_bar .o_workshop_app_icon_btn");
        return back ? back.click() : openApp();
    };
    const toOrder = async () => {
        if (!findTarget(home)) {
            await openApp();
            await waitFor(".o_workshop_app_card");
        }
        findTarget(".o_workshop_app_card")?.click();
    };
    return [
        {
            screen: home,
            open: openApp,
            title: _t("Welcome to the app"),
            body: _t("Everything the yard needs, on the phone. Tip: add it to the home screen to open it like any other app."),
        },
        { target: ".o_workshop_app_top ~ .o_workshop_app_search", open: toHome, title: _t("Find a truck"),
          body: _t("Type part of the plate, the order number or the customer.") },
        { target: ".o_workshop_app_kpis", open: toHome, title: _t("Your numbers"),
          body: _t("Open orders, late ones and quotes waiting for the customer.") },
        { target: ".o_workshop_app_section_head", open: toHome, title: _t("Stages"),
          body: _t("Filter the trucks by stage. The button on the right switches between a row and a grid.") },
        { target: ".o_workshop_app_card", open: toHome, optional: true, title: _t("A truck in the yard"),
          body: _t("Plate, vehicle, stage, time in the stage and bay. Tap it to open the order.") },
        { target: ".o_workshop_app_fab", open: toHome, title: _t("Receive a truck"),
          body: _t("Start here when a truck arrives: type the plate, and a known truck brings its customer and odometer.") },
        { target: ".o_workshop_app_tabs", open: toOrder, optional: true, title: _t("Inside an order"),
          body: _t("Change the stage and the bay with one tap. Below: services, photos by moment, the checklist and the history. The pencil at the top corrects the order, or deletes one opened by mistake.") },
        { target: ".o_workshop_app_footer--actions", open: toOrder, optional: true, title: _t("The next step"),
          body: _t("When the job is done, mark it here; the office sees it right away. Marked it by mistake? Reopen it here too.") },
        { target: ".o_workshop_app_top .o_workshop_app_icon_btn", open: toHome, title: _t("The menu"),
          body: _t("Light or dark theme, refresh, the office view and this tour. Sign out here too.") },
        { screen: home, open: toHome, title: _t("All set"),
          body: _t("Open this tour again from the menu whenever you like.") },
    ];
}

const TRACKS = { office: officeSteps, app: appSteps };

export const workshopTourService = {
    dependencies: ["action", "orm"],
    start(env, services) {
        const state = reactive({ active: false, track: null, steps: [], index: 0, target: null, busy: false });
        let run = 0; // a newer navigation cancels the one in progress

        async function show(index, direction) {
            const token = ++run;
            state.busy = true;
            while (index >= 0 && index < state.steps.length) {
                const step = state.steps[index];
                if (step.when && !(await step.when())) {
                    index += direction;
                    continue;
                }
                const screen = step.screen || step.target;
                const elsewhere = step.page && currentPage(services.action) !== step.page;
                if (step.open && (elsewhere || (screen && !findTarget(screen)))) {
                    await step.open();
                }
                const target = step.target ? await waitFor(step.target) : null;
                if (screen && step.screen) {
                    await waitFor(step.screen);
                }
                if (token !== run) {
                    return;
                }
                if (step.target && !target && step.optional) {
                    index += direction;
                    continue;
                }
                target?.scrollIntoView({ block: "center", inline: "nearest" });
                Object.assign(state, { index, target, busy: false });
                return;
            }
            finish();
        }

        function finish() {
            if (state.track) {
                user.setUserSettings(`workshop_tour_${state.track}_done`, true);
            }
            Object.assign(state, { active: false, track: null, steps: [], target: null, busy: false });
        }

        return {
            state,
            async start(track) {
                if (!track) {
                    const office = await user.hasGroup("workshop_os.workshop_os_group_manager");
                    track = office ? "office" : "app";
                }
                Object.assign(state, { active: true, track, steps: TRACKS[track](services), index: 0, target: null });
                return show(0, 1);
            },
            /** The first visit to the dashboard or the app opens its tour, once per user. */
            async maybeStart(track) {
                if (state.active || user.settings[`workshop_tour_${track}_done`]) {
                    return;
                }
                if (track === "office" && !(await user.hasGroup("workshop_os.workshop_os_group_manager"))) {
                    return;
                }
                return this.start(track);
            },
            next: () => show(state.index + 1, 1),
            prev: () => show(state.index - 1, -1),
            finish,
        };
    },
};

export class WorkshopTour extends Component {
    static template = "workshop_os.Tour";
    static props = {};

    setup() {
        this.tour = useService("workshop_tour");
        this.state = useState(this.tour.state);
        this.card = useRef("card");
        this.layout = useState({ rect: null, card: "", placement: "center" });
        const onChange = () => this.reposition();
        const onKey = (ev) => {
            if (!this.state.active) {
                return;
            }
            if (ev.key === "Escape") {
                this.tour.finish();
            } else if (ev.key === "ArrowRight" && !this.state.busy) {
                this.tour.next();
            } else if (ev.key === "ArrowLeft" && !this.state.busy && this.state.index) {
                this.tour.prev();
            }
        };
        let timer;
        onMounted(() => {
            browser.addEventListener("resize", onChange);
            browser.addEventListener("scroll", onChange, true);
            browser.addEventListener("keydown", onKey);
            // The page keeps settling after a step opens (images, lazy rows): follow it for a moment.
            timer = browser.setInterval(onChange, 400);
        });
        onWillUnmount(() => {
            browser.removeEventListener("resize", onChange);
            browser.removeEventListener("scroll", onChange, true);
            browser.removeEventListener("keydown", onKey);
            browser.clearInterval(timer);
        });
        useEffect(
            () => {
                this.reposition();
                this.card.el?.focus({ preventScroll: true });
            },
            () => [this.state.active, this.state.index, this.state.busy],
        );
    }

    get step() {
        return this.state.steps[this.state.index] || {};
    }

    get count() {
        return this.state.steps.length;
    }

    get isLast() {
        return this.state.index === this.count - 1;
    }

    /**
     * Spotlight on the target and the card beside it (computer) or as a sheet (phone). The phone sheet stays at the
     * bottom, so the top of a tall target (the order board) stays in view, and goes up only for a target it would hide
     * that fits in full below a top sheet (the button to receive a truck).
     */
    reposition() {
        if (!this.state.active) {
            return;
        }
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const el = this.state.target?.isConnected ? this.state.target : null;
        let rect = null;
        if (el) {
            const r = el.getBoundingClientRect();
            const pad = 6;
            const top = Math.max(r.top - pad, 4);
            const left = Math.max(r.left - pad, 4);
            const bottom = Math.min(r.bottom + pad, vh - 4);
            const right = Math.min(r.right + pad, vw - 4);
            if (bottom > top && right > left) {
                rect = { top, left, width: right - left, height: bottom - top };
            }
        }
        const cardH = this.card.el?.offsetHeight || 220;
        let placement = "center";
        let card = "";
        if (vw < SMALL) {
            const sheet = cardH + 16;
            const hidden = rect && rect.top + rect.height > vh - sheet;
            placement = hidden && rect.top >= sheet ? "top" : "bottom";
        } else if (rect) {
            const width = Math.min(380, vw - 32);
            const left = Math.min(Math.max(rect.left, 16), vw - width - 16);
            if (rect.top + rect.height + 12 + cardH <= vh - 16) {
                placement = "below";
                card = `top:${rect.top + rect.height + 12}px;left:${left}px;width:${width}px;`;
            } else if (rect.top - 12 - cardH >= 16) {
                placement = "above";
                card = `top:${rect.top - 12 - cardH}px;left:${left}px;width:${width}px;`;
            } else {
                placement = "corner";
                card = `bottom:24px;right:24px;width:${width}px;`;
            }
        }
        const spot = rect
            ? `top:${rect.top}px;left:${rect.left}px;width:${rect.width}px;height:${rect.height}px;`
            : "";
        if (spot !== this.layout.rect || card !== this.layout.card || placement !== this.layout.placement) {
            Object.assign(this.layout, { rect: spot, card, placement });
        }
    }
}

registry.category("services").add("workshop_tour", workshopTourService);
registry.category("main_components").add("workshop_tour", { Component: WorkshopTour });
registry.category("user_menuitems").add("workshop_tour", (env) => ({
    type: "item",
    id: "workshop_tour",
    description: _t("Guided tour"),
    callback: () => env.services.workshop_tour.start(),
    sequence: 5,
}));
