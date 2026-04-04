import { useState } from "@web/owl2/utils";
import { formatFloatTime } from "../formatters";
import { useInput } from "../input_field_hook";
import { useNumpadDecimal } from "../numpad_decimal_hook";
import { parseFloatTime } from "../parsers";

import { Component } from "@odoo/owl";
import { usePopover } from "@web/core/popover/popover_hook";

export class FloatTime extends Component {
    static template = "web.FloatTime";
    static props = {
        showSeconds: { type: Boolean, optional: true },
        numeric: { type: Boolean, optional: true },
        unit: {
            type: [{ value: "hours" }, { value: "minutes" }, { value: "seconds" }],
            optional: true,
        },
        value: { type: Number, optional: true },
        onUpdateValue: { type: Function, optional: true },
    };
    static defaultProps = {
        numeric: false,
        unit: "hours",
    };

    setup() {
        this.inputFloatTimeRef = this.getUseInputRef();

        this.state = useState({
            formattedResult: "",
            value: this.props.value ?? 0,
        });
        this.resultPopover = usePopover(DurationPopover, {
            position: "bottom",
        });
        useNumpadDecimal();
    }

    // Value Mapping, to override if value is stored out of component (e.g. record)

    getUseInputRef() {
        return useInput({
            getValue: () => this.state.value,
            getFormattedValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: (v) => parseFloatTime(v, this.props.unit),
            setValue: (v) => {
                this.state.value = v;
                this.props.onUpdateValue?.(v);
            },
        }).inputRef;
    }

    get floatValue() {
        return this.state.value;
    }

    // Component Logic

    onValueChange(ev) {
        const currentInput = ev.target.value;
        this.state.formattedResult = formatFloatTime(
            parseFloatTime(currentInput, this.props.unit),
            {
                showSeconds: this.props.showSeconds,
                numeric: this.props.numeric,
                unit: this.props.unit,
            }
        );
        if (currentInput === this.state.formattedResult && this.resultPopover.isOpen) {
            this.resultPopover.close();
        } else if (currentInput !== this.state.formattedResult && !this.resultPopover.isOpen) {
            this.resultPopover.open(this.inputFloatTimeRef.el, {
                state: this.state,
            });
        }
    }

    openPopover() {
        const duration = parseFloatTime(this.inputFloatTimeRef.el.value, this.props.unit);
        this.state.formattedResult = formatFloatTime(duration, {
            showSeconds: this.props.showSeconds,
            numeric: this.props.numeric,
            unit: this.props.unit,
        });
        this.resultPopover.open(this.inputFloatTimeRef.el, {
            state: this.state,
        });
    }

    closePopover() {
        this.resultPopover.close();
    }

    get formattedValue() {
        return formatFloatTime(this.floatValue, {
            showSeconds: this.props.showSeconds,
            numeric: this.props.numeric,
            unit: this.props.unit,
        });
    }
}

class DurationPopover extends Component {
    static template = "web.DurationPopover";
    static props = {
        state: { type: Object, optional: true },
        close: { type: Function, optional: true },
    };
}
