import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onWillUnmount, useState } from "@odoo/owl";

const { DateTime } = luxon;

/** Plate drawn as a Mercosur plate, so it reads like the real thing across the yard views. */
export class PlateField extends Component {
    static template = "workshop_os.PlateField";
    static props = { ...standardFieldProps, size: { type: String, optional: true } };

    get value() {
        return this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("workshop_plate", {
    component: PlateField,
    displayName: _t("Plate"),
    supportedTypes: ["char"],
    extractProps: ({ options }) => ({ size: options.size }),
});

/** "2h 15min in this stage", refreshed every minute. */
export class ElapsedField extends Component {
    static template = "workshop_os.ElapsedField";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({ now: DateTime.now() });
        const timer = setInterval(() => (this.state.now = DateTime.now()), 60000);
        onWillUnmount(() => clearInterval(timer));
    }

    get label() {
        const since = this.props.record.data[this.props.name];
        if (!since) {
            return "";
        }
        return formatElapsed(this.state.now.diff(since, "minutes").minutes);
    }
}

export function formatElapsed(minutes) {
    minutes = Math.max(0, Math.floor(minutes));
    if (minutes < 60) {
        return _t("%(m)s min", { m: minutes });
    }
    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
        return _t("%(h)sh %(m)smin", { h: hours, m: minutes % 60 });
    }
    return _t("%(d)sd %(h)sh", { d: Math.floor(hours / 24), h: hours % 24 });
}

registry.category("fields").add("workshop_elapsed", {
    component: ElapsedField,
    displayName: _t("Time elapsed"),
    supportedTypes: ["datetime"],
});
