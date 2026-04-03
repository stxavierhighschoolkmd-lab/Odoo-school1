import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Field } from "@web/views/fields/field";

export class PartnerField extends Component {
    static components = { Field };
    static props = {
        ...standardFieldProps,
    };

    static template = "account.PartnerField";

}
registry.category("fields").add("partner_field", {
    component: PartnerField,
});
