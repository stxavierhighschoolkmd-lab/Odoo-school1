import { reactive } from "@web/owl2/utils";
import { Plugin } from "@html_editor/plugin";
import { unwrapContents } from "@html_editor/utils/dom";
import { isRedundantElement, isStylable } from "@html_editor/utils/dom_info";
import { selectElements } from "@html_editor/utils/dom_traversal";
import {
    convertNumericToUnit,
    getCSSVariableValue,
    getHtmlStyle,
    getFontSizeDisplayValue,
    FONT_SIZE_CLASSES,
} from "@html_editor/utils/formatting";
import { _t } from "@web/core/l10n/translation";
import { READ, withSequence } from "@html_editor/utils/resource";
import { FontSizeSelector } from "./font_size_selector";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";

/** @typedef {import("plugins").LazyTranslatedString} LazyTranslatedString */

export const fontSizeItems = [
    { variableName: "display-1-font-size", className: "display-1-fs" },
    { variableName: "display-2-font-size", className: "display-2-fs" },
    { variableName: "display-3-font-size", className: "display-3-fs" },
    { variableName: "display-4-font-size", className: "display-4-fs" },
    { variableName: "h1-font-size", className: "h1-fs" },
    { variableName: "h2-font-size", className: "h2-fs" },
    { variableName: "h3-font-size", className: "h3-fs" },
    { variableName: "h4-font-size", className: "h4-fs" },
    { variableName: "h5-font-size", className: "h5-fs" },
    { variableName: "h6-font-size", className: "h6-fs" },
    { variableName: "font-size-base", className: "base-fs" },
    { variableName: "small-font-size", className: "o_small-fs" },
];

export class FontSizePlugin extends Plugin {
    static id = "fontSize";
    static dependencies = ["format", "selection"];
    /** @type {import("plugins").EditorResources} */
    resources = {
        toolbar_items: [
            withSequence(20, {
                id: "font-size",
                groupId: "font",
                namespaces: ["compact", "expanded"],
                description: _t("Select font size"),
                Component: FontSizeSelector,
                props: {
                    getItems: () => this.fontSizeItems,
                    getDisplay: () => this.fontSize,
                    onFontSizeInput: (size) => {
                        this.dependencies.format.formatSelection("fontSize", {
                            formatProps: { size },
                            applyStyle: true,
                        });
                        this.updateFontSizeSelectorParams();
                    },
                    onSelected: (item) => {
                        this.dependencies.format.formatSelection("setFontSizeClassName", {
                            formatProps: { className: item.className },
                            applyStyle: true,
                        });
                        this.updateFontSizeSelectorParams();
                    },
                    onBlur: () => this.dependencies.selection.focusEditable(),
                    document: this.document,
                },
                isAvailable: isHtmlContentSupported,
                isDisabled: (sel, nodes) => nodes.some((node) => !isStylable(node)),
            }),
        ],

        /** Handlers */
        on_selectionchange_handlers: withSequence(
            READ,
            this.updateFontSizeSelectorParams.bind(this)
        ),
        on_undone_handlers: this.updateFontSizeSelectorParams.bind(this),
        on_redone_handlers: this.updateFontSizeSelectorParams.bind(this),
        normalize_processors: this.normalize.bind(this),

        is_format_class_predicates: (className) => {
            if ([...FONT_SIZE_CLASSES, "o_default_font_size"].includes(className)) {
                return true;
            }
        },
    };

    setup() {
        this.fontSize = reactive({ displayName: "" });
    }

    normalize(root) {
        for (const el of selectElements(root, "small")) {
            if (isRedundantElement(el)) {
                unwrapContents(el);
            }
        }
    }

    get fontSizeName() {
        const sel = this.dependencies.selection.getSelectionData().deepEditableSelection;
        if (!sel) {
            return fontSizeItems[0].name;
        }
        return Math.round(getFontSizeDisplayValue(sel, this.document));
    }

    get fontSizeItems() {
        const style = getHtmlStyle(this.document);
        const nameAlreadyUsed = new Set();
        return fontSizeItems
            .flatMap((item) => {
                const strValue = getCSSVariableValue(item.variableName, style);
                if (!strValue) {
                    return [];
                }
                const remValue = parseFloat(strValue);
                const pxValue = convertNumericToUnit(remValue, "rem", "px", style);
                const roundedValue = Math.round(pxValue);
                if (nameAlreadyUsed.has(roundedValue)) {
                    return [];
                }
                nameAlreadyUsed.add(roundedValue);

                return [{ ...item, tagName: "span", name: roundedValue }];
            })
            .sort((a, b) => a.name - b.name);
    }

    updateFontSizeSelectorParams() {
        this.fontSize.displayName = this.fontSizeName;
    }
}
