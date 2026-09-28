import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component } from "@odoo/owl";

/**
 * "Customer link" button of a work order: copies the approval page's address and says so.
 *
 * The clipboard call is the first thing the tap runs, so phones accept it (an iPhone refuses to copy once the tap
 * has waited for the server). Where copying is not allowed, the address stays on screen to be copied by hand.
 */
export class CustomerLinkButton extends Component {
    static template = "workshop_os.CustomerLinkButton";
    static props = { ...standardWidgetProps };

    setup() {
        this.notification = useService("notification");
    }

    async copy() {
        const url = this.props.record.data.public_url;
        try {
            await browser.navigator.clipboard.writeText(url);
            this.notification.add(url, { title: _t("Customer link copied"), type: "success" });
        } catch {
            this.notification.add(url, { title: _t("Customer link"), type: "info", sticky: true });
        }
    }
}

registry.category("view_widgets").add("workshop_customer_link", {
    component: CustomerLinkButton,
    fieldDependencies: [{ name: "public_url", type: "char" }],
});
