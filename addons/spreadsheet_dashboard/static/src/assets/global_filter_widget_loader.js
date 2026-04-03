import { useState } from "@web/owl2/utils";
import { Component, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class GlobalFilterWidgetLoader extends Component {
    static template = xml`
        <t t-if="this.state.Component" t-component="this.state.Component" t-props="this.props"/>
        <span t-else="" class="text-muted">Loading global filters…</span>
    `;
    static props = {
        ...standardFieldProps,
        dashboard: { type: String, optional: true },
    };

    setup() {
        this.state = useState({ Component: null });

        onWillStart(async () => {
            await loadBundle("spreadsheet.o_spreadsheet");
            const module = await odoo.loader.modules.get(
                "@spreadsheet_dashboard/bundle/global_filter_widget/global_filter_widget"
            );
            if (!module?.GlobalFilterWidget) {
                throw new Error(_t("Global Filters component not found"));
            }
            this.state.Component = module.GlobalFilterWidget;
        });
    }
}

registry.category("fields").add("global_filters", {
    component: GlobalFilterWidgetLoader,
    displayName: _t("Global Filters"),
    supportedOptions: [
        {
            label: _t("Dashboard"),
            name: "dashboard",
            type: "string",
        },
    ],
    supportedTypes: ["json"],
    isEmpty: () => false,
    extractProps({ options }) {
        return { dashboard: options.dashboard };
    },
});
