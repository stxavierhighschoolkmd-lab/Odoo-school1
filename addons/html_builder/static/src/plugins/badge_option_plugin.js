import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class BadgeOptionPlugin extends Plugin {
    static id = "badgeOption";
    /** @type {import("plugins").BuilderResources} */
    resources = {
        so_content_addition_selectors: [".s_badge"],
        is_node_splittable_predicates: (node) => {
            if (node.classList?.contains("s_badge")) {
                return false;
            }
        },
    };
}

export class BadgeTranslationPlugin extends Plugin {
    static id = "badgeTranslation";
    /** @type {import("plugins").WebsiteResources} */
    resources = {
        require_repeat_translation_state_background_selectors: "span.s_badge",
    };
}

registry.category("translation-plugins").add(BadgeTranslationPlugin.id, BadgeTranslationPlugin);
registry.category("builder-plugins").add(BadgeOptionPlugin.id, BadgeOptionPlugin);
