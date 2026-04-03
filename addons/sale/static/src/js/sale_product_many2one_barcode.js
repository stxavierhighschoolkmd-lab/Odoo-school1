/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    Many2OneBarcodeField,
    many2OneBarcodeField,
} from "@web/views/fields/many2one_barcode/many2one_barcode_field";

export class SolProductMany2OneBarcodeField extends Many2OneBarcodeField {
    setup() {
        super.setup();
        this.notification = useService("notification");
    }

    async updateRecord(value) {
        await super.updateRecord(value);

        if (this.props.record.data.product_type === "combo") {
            this.notification.add(
                _t("Combo products cannot be configured on mobile."),
                { type: "danger" }
            );
            await this.props.record.update({ [this.props.name]: false });
        }
    }
}

export const solProductMany2OneBarcodeField = {
    ...many2OneBarcodeField,
    component: SolProductMany2OneBarcodeField,
};

registry.category("fields").add("sol_product_many2one_barcode", solProductMany2OneBarcodeField);
