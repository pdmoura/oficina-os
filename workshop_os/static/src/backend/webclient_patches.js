import { titleService } from "@web/core/browser/title_service";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { FormController } from "@web/views/form/form_controller";

// Browser tabs read "<page> - <shop>": the shop's name always goes last, after whatever the page sets.
patch(titleService, {
    start() {
        const title = super.start(...arguments);
        const brand = session.workshop_app_name;
        if (brand) {
            const setParts = title.setParts;
            title.setParts = (parts) => {
                setParts({ ...parts, workshop_brand: null });
                setParts({ workshop_brand: brand });
            };
            title.setParts({});
        }
        return title;
    },
});

// Field borders stay visible, as Odoo already shows them on phones: on a desktop an empty field otherwise looks
// like a plain label and nothing says where to type.
patch(FormController.prototype, {
    get className() {
        return { ...super.className, o_field_highlight: true };
    },
});
