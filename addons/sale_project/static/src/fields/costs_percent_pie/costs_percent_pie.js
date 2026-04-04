import { registry } from "@web/core/registry";
import { formatMonetary } from "@web/views/fields/formatters";
import { PercentPieField, percentPieField } from "@web/views/fields/percent_pie/percent_pie_field";

export class CostsPercentPieField extends PercentPieField {
    static template = "sale_project.CostsPercentPieField";

    static props = {
        ...PercentPieField.props,
        cost_name: { type: String, optional: true },
    };

    get formattedCost() {
        const value = this.props.record.data[this.props.cost_name] || 0;
        return formatMonetary(value, { data: this.props.record.data, currency_field: "currency_id" });
    }
}

export const costsPercentPieField = {
    ...percentPieField,
    component: CostsPercentPieField,
    extractProps: (fieldInfo, dynamicInfo) => {
        const props = percentPieField.extractProps(fieldInfo, dynamicInfo);
        props.cost_name = fieldInfo.attrs.cost_name;
        return props;
    },
};

registry.category("fields").add("costs_percentpie", costsPercentPieField);
