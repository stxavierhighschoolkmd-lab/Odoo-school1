import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { useDomState } from "@html_builder/core/utils";
import { BuilderColorPicker } from "@html_builder/core/building_blocks/builder_colorpicker";
import { BuilderSelect } from "@html_builder/core/building_blocks/builder_select";
import { BuilderSelectItem } from "@html_builder/core/building_blocks/builder_select_item";
import { BuilderNumberInput } from "@html_builder/core/building_blocks/builder_number_input";
import { BuilderAction } from "@html_builder/core/builder_action";
import { StyleAction, withoutTransition } from "@html_builder/core/core_builder_action_plugin";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { BorderConfigurator } from "@html_builder/plugins/border_configurator_option";
import {
    BUTTON_SHAPES,
    BUTTON_SIZES,
    BUTTON_TYPES,
    computeButtonClasses,
    getButtonShape,
    getButtonSize,
    getButtonType,
} from "@html_editor/utils/button_style";
import { closestPath, findNode } from "@html_editor/utils/dom_traversal";

export class ButtonStyleOptionPlugin extends Plugin {
    static id = "buttonStyleOption";
    resources = {
        builder_actions: { ButtonStyleAction, ButtonFillColorAction },
    };
}

export class ButtonStyleOption extends BaseOptionComponent {
    static id = "button_style_option";
    static template = "html_builder.ButtonStyleOption";
    static components = {
        BuilderColorPicker,
        BuilderSelect,
        BuilderSelectItem,
        BuilderNumberInput,
        BorderConfigurator,
    };
    static dependencies = ["history"];

    buttonSizesData = BUTTON_SIZES;
    buttonShapesData = BUTTON_SHAPES;
    buttonTypesData = BUTTON_TYPES;

    setup() {
        super.setup();
        this.state = useDomState((el) => ({
            buttonStyles: this.getButtonStyles(el),
            buttonCombinationClass: this.findColorCombination(el),
            type: getButtonType(el),
        }));
    }

    goToThemeTab() {
        this.env.editColorCombination(
            parseInt(this.state.buttonCombinationClass.replace("o_cc", ""))
        );
    }

    getButtonStyles(el) {
        const buttonVariants = {
            primary: "btn-primary",
            secondary: "btn-secondary",
        };
        const previewVariables = [
            "background-color",
            "border",
            "border-radius",
            "color",
            "font-family",
            "font-weight",
            "text-transform",
        ];

        const buttonContainerEl = el.parentElement;
        const styles = { primary: "", secondary: "", custom: "" };
        for (const [variantName, variantClass] of Object.entries(buttonVariants)) {
            const tempButtonEl = document.createElement("a");
            tempButtonEl.className = `btn ${variantClass}`;
            this.dependencies.history.ignoreDOMMutations(() =>
                buttonContainerEl.appendChild(tempButtonEl)
            );
            const computedStyle = getComputedStyle(tempButtonEl);
            for (const style of previewVariables) {
                const value = computedStyle.getPropertyValue(style);
                if (value) {
                    styles[variantName] += `${style}: ${value};`;
                }
            }
            this.dependencies.history.ignoreDOMMutations(() => tempButtonEl.remove());
        }
        return styles;
    }

    findColorCombination(el) {
        // Crawl the DOM upwards until a cc class is found, otherwise return cc1
        const ccClasses = ["o_cc1", "o_cc2", "o_cc3", "o_cc4", "o_cc5"];
        let matchedClass;
        findNode(closestPath(el), (node) => {
            matchedClass = ccClasses.find((cls) => node.classList?.contains(cls));
            return !!matchedClass;
        });
        return matchedClass !== undefined ? matchedClass : ccClasses[0];
    }
}

export class ButtonStyleAction extends BuilderAction {
    static id = "buttonStyleAction";

    apply({ editingElement, params, value }) {
        const mode = params.mainParam;
        if (mode === "type") {
            this.applyDefaultInlineStyle(editingElement, value);
        }

        editingElement.className = computeButtonClasses(editingElement, {
            type: mode === "type" ? value : getButtonType(editingElement),
            size: mode === "size" ? value : getButtonSize(editingElement),
            shape: mode === "shape" ? value : getButtonShape(editingElement),
        });
    }

    applyDefaultInlineStyle(el, currentType) {
        const styleProps = ["color", "backgroundColor", "backgroundImage", "border"];
        if (currentType === "custom") {
            withoutTransition(el, () => {
                const computedStyle = el.ownerDocument.defaultView.getComputedStyle(el);
                for (const prop of styleProps) {
                    if (computedStyle[prop] !== "none") {
                        el.style[prop] = computedStyle[prop];
                    }
                }
                if (computedStyle.borderStyle === "none") {
                    el.style.borderStyle = "solid";
                }
            });
        } else {
            for (const prop of styleProps) {
                el.style[prop] = "";
            }
        }
    }

    getValue({ editingElement, params }) {
        const mode = params.mainParam;
        switch (mode) {
            case "type":
                return getButtonType(editingElement);
            case "size":
                return getButtonSize(editingElement);
            case "shape":
                return getButtonShape(editingElement);
        }
    }

    isApplied({ editingElement, params, value }) {
        return this.getValue({ editingElement, params }) === value;
    }
}

export class ButtonFillColorAction extends StyleAction {
    static id = "buttonFillColorAction";
    static dependencies = ["color"];

    getValue(context) {
        // This override is needed because when the button is in outline mode,
        // the color is not shown unless we hover the button
        const { editingElement: el } = context;
        return el.style.backgroundColor || el.style.backgroundImage || super.getValue(context);
    }
}

registry.category("builder-plugins").add(ButtonStyleOptionPlugin.id, ButtonStyleOptionPlugin);
registry.category("builder-options").add(ButtonStyleOption.id, ButtonStyleOption);
