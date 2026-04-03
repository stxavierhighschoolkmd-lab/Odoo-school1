import { registry } from "@web/core/registry";
import { formatFloat } from "@web/core/utils/numbers";

export function formatMailingPercentage(value, options = {}) {
    value = value || 0;
    options = Object.assign({ trailingZeros: false, thousandsSep: "" }, options);
    if (!options.digits && options.field) {
        options.digits = options.field.digits;
    }
    const formatted = formatFloat(value, options);
    return `${formatted}${options.noSymbol ? "" : "%"}`;
}

/**
 * Add the format function to the gloabl `formatters` as it will be used by the
 * `ListRenderer.computeAggregates` when trying to format the value provided by
 * the `mailing_percentage` widget.
 */
registry.category("formatters").add("mailing_percentage", formatMailingPercentage);
