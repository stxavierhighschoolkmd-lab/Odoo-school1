import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { useDomState } from "@html_builder/core/utils";
import { getCSSVariableValue, getHtmlStyle } from "@html_editor/utils/formatting";
import { _t } from "@web/core/l10n/translation";
import { CustomizeWebsiteVariableAction } from "../customize_website_plugin";

const FONT_WEIGHT_OPTIONS = [
    { label: _t("Thin"), value: 100 },
    { label: _t("Extra Light"), value: 200 },
    { label: _t("Light"), value: 300 },
    { label: _t("Regular"), value: 400 },
    { label: _t("Medium"), value: 500 },
    { label: _t("Semi Bold"), value: 600 },
    { label: _t("Bold"), value: 700 },
    { label: _t("Extra Bold"), value: 800 },
    { label: _t("Black"), value: 900 },
];

function unquote(value) {
    if (value.startsWith("'")) {
        return value.substring(1, value.length - 1);
    }
    return value;
}

function getParsedWeight(value) {
    const normalized = `${value || ""}`.trim().toLowerCase();
    if (normalized === "normal") {
        return 400;
    }
    if (normalized === "bold") {
        return 700;
    }
    const parsed = Number.parseInt(normalized, 10);
    return Number.isNaN(parsed) ? null : parsed;
}

function parseFontFaceWeight(weightDescriptor) {
    const tokens = `${weightDescriptor || ""}`.trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) {
        return [];
    }
    if (tokens.length === 2) {
        const min = getParsedWeight(tokens[0]);
        const max = getParsedWeight(tokens[1]);
        if (min !== null && max !== null) {
            return FONT_WEIGHT_OPTIONS.filter(
                ({ value }) => value >= Math.min(min, max) && value <= Math.max(min, max)
            ).map(({ value }) => value);
        }
    }
    const weight = getParsedWeight(tokens[0]);
    return weight === null ? [] : [weight];
}

function resolveFontWeight(currentWeight, availableWeights) {
    if (availableWeights.includes(currentWeight)) {
        return currentWeight;
    }
    // If currentWeight is not available for the font, we take the closer one
    return [...availableWeights].sort(
        (a, b) => Math.abs(a - currentWeight) - Math.abs(b - currentWeight)
    )[0];
}

export class FontWeightPicker extends BaseOptionComponent {
    static template = "website.FontWeightPicker";
    static props = {
        label: { type: String },
        variable: { type: String },
        weights: { type: Array },
        level: { type: Number, optional: true },
        disabled: { type: Boolean, optional: true },
        tooltip: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = {
        level: 0,
        disabled: false,
    };

    get actionParam() {
        return {
            mainParam: this.props.variable,
        };
    }
}

export class ThemeFontWeightOption extends BaseOptionComponent {
    static template = "website.ThemeFontWeightOption";
    static components = { FontWeightPicker };
    static dependencies = ["themeTab"];
    static props = {
        fontVariable: { type: String },
        regularVariable: { type: String, optional: true },
        lightVariable: { type: String, optional: true },
        boldVariable: { type: String, optional: true },
    };

    setup() {
        super.setup();
        this.state = useDomState(async () => {
            const fontName = this.getFontName(getHtmlStyle(this.document));
            const availableWeights = await this.getAvailableWeights(fontName);
            const regularWeight = this.getCurrentWeight(
                this.props.regularVariable,
                availableWeights
            );
            return {
                availableWeights,
                regularWeight,
            };
        });
    }

    get boldTooltip() {
        return this.isBoldDisabled ? _t("This font is missing font weight") : undefined;
    }

    get isBoldDisabled() {
        return (this.state.regularWeight || 0) > 700;
    }

    getFontName(style) {
        return unquote(getCSSVariableValue(this.props.fontVariable, style));
    }

    async getAvailableWeights(fontName) {
        const cachedWeights = this.dependencies.themeTab.getCachedFontWeights(fontName);
        if (cachedWeights) {
            return cachedWeights;
        }
        const availableWeightValues = new Set();
        const normalizedFontName = unquote(fontName);
        if (normalizedFontName && this.document.fonts) {
            await this.document.fonts.ready;
            for (const fontFace of this.document.fonts) {
                if (unquote(fontFace.family) !== normalizedFontName) {
                    continue;
                }
                for (const weight of parseFontFaceWeight(fontFace.weight)) {
                    availableWeightValues.add(weight);
                }
            }
        }
        const availableWeights = FONT_WEIGHT_OPTIONS.filter(({ value }) =>
            availableWeightValues.has(value)
        );
        this.dependencies.themeTab.setCachedFontWeights(fontName, availableWeights);
        return availableWeights;
    }

    getCurrentWeight(weightVariable, availableWeights) {
        if (!weightVariable) {
            return null;
        }
        const variableWeight = getParsedWeight(
            getCSSVariableValue(weightVariable, getHtmlStyle(this.document))
        );
        if (variableWeight === null) {
            return null;
        }
        return resolveFontWeight(
            variableWeight,
            availableWeights.map(({ value }) => value)
        );
    }
}

export class CustomizeWebsiteFontWeightAction extends CustomizeWebsiteVariableAction {
    static id = "customizeWebsiteFontWeight";

    getValue({ params }) {
        return super.getValue({ params }) || null;
    }

    isApplied({ params, value }) {
        return this.getValue({ params }) === value;
    }
}
