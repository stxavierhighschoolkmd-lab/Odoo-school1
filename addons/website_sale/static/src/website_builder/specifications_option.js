import { useState } from "@web/owl2/utils";
import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class SpecificationsOption extends BaseOptionComponent {
    static id = "specifications_option";
    static template = "website_sale.SpecificationsOption";
    static dependencies = ["specificationsOption"];

    setup() {
        super.setup();
        const { loadSpecs, getExtraFields, getCategories, getCategoryCreateMode } =
            this.dependencies.specificationsOption;

        this.state = useState({ fields: [] });

        this.categories = useState(getCategories());
        this.extraFields = useState(getExtraFields());
        this.categoryCreateMode = useState(getCategoryCreateMode());

        onWillStart(async () => {
            const data = await loadSpecs();
            this.state.fields = data.fields;
        });
    }

    _getEditingElement() {
        return this.env.editor.document.querySelector(
            ".o_wsale_specss"
        );
    }

    openCategoryCreate() {
        this.categoryCreateMode.value = true;
    }

    cancelCategoryCreate() {
        this.categoryCreateMode.value = false;
        const el = this._getEditingElement();
        if (el) {
            delete el.dataset.pendingNewCategoryName;
        }
    }
}

registry
    .category("website-options")
    .add(SpecificationsOption.id, SpecificationsOption);


class SpecFieldRowOption extends BaseOptionComponent {
    static id = "spec_field_row_option";
    static template = "website_sale.SpecFieldRowOption";

}
registry.category("website-options").add(SpecFieldRowOption.id, SpecFieldRowOption);
