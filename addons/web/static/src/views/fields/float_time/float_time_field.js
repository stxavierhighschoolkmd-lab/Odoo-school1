import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useInputField } from "../input_field_hook";
import { standardFieldProps } from "../standard_field_props";
import { parseFloatTime } from "../parsers";
import { FloatTime } from "./float_time";

export class FloatTimeField extends FloatTime {
    static props = { ...standardFieldProps, ...FloatTime.props };

    getUseInputRef() {
        return useInputField({
            getValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: (v) => parseFloatTime(v, this.props.unit),
        });
    }

    get floatValue() {
        return this.props.record.data[this.props.name];
    }
}

export const floatTimeField = {
    component: FloatTimeField,
    displayName: _t("Time"),
    supportedOptions: [
        {
            label: _t("Show seconds"),
            name: "show_seconds",
            type: "boolean",
        },
        {
            label: _t("Type"),
            name: "type",
            type: "string",
            default: "text",
        },
        {
            label: _t("Numeric"),
            name: "numeric",
            type: "boolean",
        },
        {
            label: _t("Unit"),
            name: "unit",
            type: "selection",
            default: "hours",
            choices: [
                { label: _t("Hours"), value: "hours" },
                { label: _t("Minutes"), value: "minutes" },
                { label: _t("Seconds"), value: "seconds" },
            ],
        },
    ],
    supportedTypes: ["float"],
    isEmpty: () => false,
    extractProps: ({ options }) => ({
        showSeconds: Boolean(options.show_seconds),
        numeric: Boolean(options.numeric),
        unit: options.unit,
    }),
};

registry.category("fields").add("float_time", floatTimeField);
