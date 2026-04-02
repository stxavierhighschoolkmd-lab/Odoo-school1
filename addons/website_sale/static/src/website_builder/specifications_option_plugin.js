import { reactive } from "@web/owl2/utils";
import { BuilderAction } from "@html_builder/core/builder_action";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { withSequence } from "@html_editor/utils/resource";
import { _t } from "@web/core/l10n/translation";

class SpecificationsPlugin extends Plugin {
    static id = "specificationsOption";
    static dependencies = ["builderOptions"];
    static shared = [
        "loadSpecs",
        "getExtraFields",
        "getCategories",
        "getCategoryCreateMode",
        "setCategoryCreateMode",
        "clearLoadedSpecs",
    ];

    resources = {
        builder_actions: {
            AddSpecFieldAction,
            RemoveSpecFieldAction,
            CreateCategoryAction,
        },
        has_overlay_options: {
            editableOnly: false,
            hasOption: (el) => el.matches("tr[data-extra-field-id]"),
        },
        get_overlay_buttons: withSequence(10, {
            editableOnly: false,
            getButtons: (el) => {
                if (!el.matches("tr[data-extra-field-id]")) {
                    return [];
                }
                return [{
                    class: "fa fa-trash text-danger",
                    title: _t("Remove Field"),
                    handler: async () => {
                        await this.services.orm.unlink(
                            "website.sale.extra.field",
                            [parseInt(el.dataset.extraFieldId)]
                        );
                        this.clearLoadedSpecs();
                        await this.config.reloadEditor({
                            target: this.dependencies.builderOptions.getReloadSelector(
                                this.document.querySelector(".o_wsale_specss")
                            )
                        });
                    },
                }];
            },
        }),
    };

    setup() {
        this._extraFields = reactive([]);
        this._categories = reactive([]);
        this._categoryCreateMode = reactive({ value: false });
        this._loadedSpecs = null;
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

    async loadSpecs() {
        if (!this._loadedSpecs) {
            const websiteId = this.services.website.currentWebsite.id;

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

            this._loadedSpecs = { fields };

            const displayNameField = fields.find((f) => f.name === "display_name");
            if (displayNameField) {
                const el = this.document.querySelector(
                    ".o_wsale_specss"
                );
                if (el && !el.dataset.pendingFieldId) {
                    el.dataset.pendingFieldId = String(displayNameField.id);
                }
            }
        }
        return this._loadedSpecs;
    }

    clearLoadedSpecs() {
        this._loadedSpecs = null;
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

        // Do not add the same field+category combination twice.
        const extraFields = this.dependencies.specificationsOption.getExtraFields();
        const alreadyExists = extraFields.some(
            (ef) =>
                ef.field_id[0] === fieldId &&
                (ef.category_id ? ef.category_id[0] : false) === categoryId
        );
        if (alreadyExists) {
            return;
        }

        const websiteId = this.services.website.currentWebsite.id;

        await this.services.orm.create(
            "website.sale.extra.field",
            [{ website_id: websiteId, field_id: fieldId, category_id: categoryId }]
        );

        this.dependencies.specificationsOption.clearLoadedSpecs();
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

        this.dependencies.specificationsOption.clearLoadedSpecs();
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
