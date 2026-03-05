import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { BuilderAction } from "@html_builder/core/builder_action";
import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { reactive, useState } from "@web/owl2/utils";
import { onWillStart } from "@odoo/owl";

export class SpecificationsOption extends BaseOptionComponent {
    static template = "website_sale.SpecificationsOption";
    static selector = "#product_full_spec .o_wsale_specss";
    static editableOnly = false;
    static dependencies = ["specificationsOption"];
    static title = "Specifications";
    static reloadTarget = true;

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
            "#product_full_spec .o_wsale_specss"
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

class SpecificationsPlugin extends Plugin {
    static id = "specificationsOption";
    static shared = [
        "loadSpecs",
        "getExtraFields",
        "getCategories",
        "getCategoryCreateMode",
        "setCategoryCreateMode",
    ];

    resources = {
        builder_options: [SpecificationsOption],
        builder_actions: {
            AddSpecFieldAction,
            RemoveSpecFieldAction,
            CreateCategoryAction,
        },
    };

    setup() {
        this._extraFields = reactive([]);
        this._categories = reactive([]);
        this._categoryCreateMode = reactive({ value: false });
        this._cache = null;
    }

    getExtraFields() {
        return this._extraFields;
    }

    getCategories() {
        return this._categories;
    }

    getCategoryCreateMode() {
        return this._categoryCreateMode;
    }

    setCategoryCreateMode(value) {
        this._categoryCreateMode.value = value;
    }

    _getWebsiteId() {
        return this.services.website.currentWebsite.id;
    }

    async loadSpecs() {
        if (!this._cache) {
            const websiteId = this._getWebsiteId();

            const [fields, categories, extraFields] = await Promise.all([
                this.services.orm.searchRead(
                    "ir.model.fields",
                    [
                        ["model", "=", "product.template"],
                        ["ttype", "in", ["char", "binary"]],
                    ],
                    ["id", "name", "field_description"]
                ),
                this.services.orm.searchRead(
                    "product.attribute.category",
                    [],
                    ["id", "name"]
                ),
                this.services.orm.searchRead(
                    "website.sale.extra.field",
                    [["website_id", "=", websiteId]],
                    ["id", "field_id", "category_id", "label", "name"]
                ),
            ]);

            this._categories.splice(0, this._categories.length, ...categories);
            this._extraFields.splice(0, this._extraFields.length, ...extraFields);

            this._cache = { fields };

            const displayNameField = fields.find((f) => f.name === "display_name");
            if (displayNameField) {
                const el = this.document.querySelector(
                    "#product_full_spec .o_wsale_specss"
                );
                if (el && !el.dataset.pendingFieldId) {
                    el.dataset.pendingFieldId = String(displayNameField.id);
                }
            }
        }
        return this._cache;
    }
}

class AddSpecFieldAction extends BuilderAction {
    static id = "addSpecField";
    static dependencies = ["specificationsOption", "builderOptions"];

    setup() {
        this.canTimeout = false;
        this.reload = true;
    }

    async apply({ editingElement }) {
        const fieldId = parseInt(editingElement.dataset.pendingFieldId);
        const categoryId =
            parseInt(editingElement.dataset.pendingCategoryId) || false;

        if (!fieldId) {
            return;
        }

        // Guard: do not add the same field+category combination twice.
        const extraFields = this.dependencies.specificationsOption.getExtraFields();
        const alreadyExists = extraFields.some(
            (ef) =>
                ef.field_id[0] === fieldId &&
                (ef.category_id ? ef.category_id[0] : false) === categoryId
        );
        if (alreadyExists) {
            return;
        }

        // Guard: skip if the field has no value on the current product template.
        const productTemplateEl = this.document.querySelector("[data-product-template-id]");
        if (productTemplateEl) {
            const productTemplateId = parseInt(productTemplateEl.dataset.productTemplateId);
            if (productTemplateId) {
                // Get the technical field name from ir.model.fields.
                const [fieldRecord] = await this.services.orm.read(
                    "ir.model.fields",
                    [fieldId],
                    ["name"]
                );
                if (fieldRecord) {
                    const [productRecord] = await this.services.orm.read(
                        "product.template",
                        [productTemplateId],
                        [fieldRecord.name]
                    );
                    const val = productRecord?.[fieldRecord.name];
                    if (!val) {
                        return;
                    }
                }
            }
        }

        const websiteId = this.services.website.currentWebsite.id;

        const [newId] = await this.services.orm.create(
            "website.sale.extra.field",
            [{ website_id: websiteId, field_id: fieldId, category_id: categoryId }]
        );

        const [newRecord] = await this.services.orm.searchRead(
            "website.sale.extra.field",
            [["id", "=", newId]],
            ["id", "field_id", "category_id", "label", "name"]
        );

        extraFields.push(newRecord);

        // Clear cache so loadSpecs re-fetches fresh data after reload.
        this.dependencies.specificationsOption._cache = null;

        this.dependencies.builderOptions.setNextTarget(editingElement);
    }
}

class RemoveSpecFieldAction extends BuilderAction {
    static id = "removeSpecField";
    static dependencies = ["specificationsOption", "builderOptions"];

    setup() {
        this.canTimeout = false;
        this.reload = true;
    }

    async apply({ editingElement, value }) {
        const recordId = parseInt(value);
        if (!recordId) {
            return;
        }

        await this.services.orm.unlink("website.sale.extra.field", [recordId]);

        const extraFields = this.dependencies.specificationsOption.getExtraFields();
        const index = extraFields.findIndex((ef) => ef.id === recordId);
        if (index !== -1) {
            extraFields.splice(index, 1);
        }

        // Clear cache so loadSpecs re-fetches fresh data after reload.
        this.dependencies.specificationsOption._cache = null;

        this.dependencies.builderOptions.setNextTarget(editingElement);
    }
}

class CreateCategoryAction extends BuilderAction {
    static id = "createCategory";
    static dependencies = ["specificationsOption", "builderOptions"];

    setup() {
        this.canTimeout = false;
        this.reload = false;
    }

    async apply({ editingElement }) {
        const name = (editingElement.dataset.pendingNewCategoryName || "").trim();
        if (!name) {
            return;
        }

        const [newId] = await this.services.orm.create(
            "product.attribute.category",
            [{ name }]
        );

        const categories = this.dependencies.specificationsOption.getCategories();
        categories.push({ id: newId, name });

        editingElement.dataset.pendingCategoryId = String(newId);
        delete editingElement.dataset.pendingNewCategoryName;
        this.dependencies.specificationsOption.setCategoryCreateMode(false);

        this.dependencies.builderOptions.setNextTarget(editingElement);
    }
}

registry
    .category("website-plugins")
    .add(SpecificationsPlugin.id, SpecificationsPlugin);
