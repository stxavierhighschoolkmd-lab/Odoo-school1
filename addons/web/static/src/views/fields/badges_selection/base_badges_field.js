import { Component } from "@odoo/owl";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { hasTouch } from "@web/core/browser/feature_detection";
import { standardFieldProps } from "../standard_field_props";
import { useState, useLayoutEffect } from "@web/owl2/utils";

export class BaseBadgesField extends Component {
    static template = "web.BaseBadgesField";
    static props = {
        ...standardFieldProps,
        badgeLimit: { type: Number, optional: true },
        placeholder: { type: String, optional: true },
        options: { type: Array },
        string: { type: String },
        value: [String, Number, Boolean, { value: null }],
        onChange: { type: Function },
        canDeselect: { type: Boolean, optional: true },
    };
    static components = {
        SelectMenu,
    };

    setup() {
        this.state = useState({
            options: [...this.props.options],
        });

        useLayoutEffect(
            () => {
                this._reorderOptions(this.props.value);
            },
            () => [this.props.value, this.props.options]
        );
    }

    /**
     * Logic to move the selected value into the visible range
     * if it currently resides in the "More" menu.
     */
    _reorderOptions(currentValue) {
        const limit = this.props.badgeLimit;
        if (!limit) {
            return;
        }

        const optionIndex = this.state.options.findIndex((option) => option[0] === currentValue);

        if (optionIndex >= limit) {
            const newOptions = [...this.state.options];
            const [selectedOption] = newOptions.splice(optionIndex, 1);

            const leftPart = newOptions.slice(0, limit - 1);
            const rightPart = newOptions.slice(limit - 1);

            this.state.options = [...leftPart, selectedOption, ...rightPart];
        }
    }

    get options() {
        return this.state.options;
    }

    get placeholder() {
        return `+${this.options.length - this.props.badgeLimit}`;
        // return this.props.placeholder || this.props.record.fields[this.props.name].string;
    }

    get string() {
        return this.props.string;
    }

    get value() {
        return this.props.value;
    }

    get hasMoreThanMax() {
        return this.props.badgeLimit && this.options.length > this.props.badgeLimit;
    }

    get badgesOptions() {
        if (!this.hasMoreThanMax) {
            return this.options;
        }

        return this.options.slice(0, this.props.badgeLimit);
    }

    get selectOptions() {
        if (!this.hasMoreThanMax) {
            return [];
        }

        return this.options
            .slice(this.props.badgeLimit)
            .map(([value, label, icon]) => ({ value, label, icon }));
    }

    get isBottomSheet() {
        return this.env.isSmall && hasTouch();
    }

    stringify(value) {
        return JSON.stringify(value);
    }

    onChange(value) {
        if (value === this.value && this.props.canDeselect) {
            this.props.onChange(false);
        } else {
            this.props.onChange(value);
        }
    }

    getBadgeClassNames(option = false) {
        return this.props.readonly ? "" : { active: this.value === option[0] };
    }
}

export const extractStandardFieldProps = (props = {}) => ({
    id: props.id,
    name: props.name,
    readonly: props.readonly,
    record: props.record,
});
