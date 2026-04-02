import { BuilderAction } from "@html_builder/core/builder_action";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { unwrapContents } from "@html_editor/utils/dom";
import { setHrefUrl } from "@html_builder/plugins/utils";

export class ClickableBlockOptionPlugin extends Plugin {
    static id = "clickableBlockOptionPlugin";
    /** @type {import("plugins").WebsiteResources} */
    resources = {
        builder_actions: {
            SetBlockClickableAction,
            SetBlockAnchorUrlAction,
        },
        is_empty_link_legit_predicates: (linkEl) => {
            if (linkEl.matches("a.stretched-link[href]")) {
                return true;
            }
        },
        can_have_hover_effect_predicates: (el) => this.canHaveHoverEffect(el),
    };

    canHaveHoverEffect(el) {
        return !el.parentElement.closest("*:has(> .stretched-link)");
    }
}

class SetBlockClickableAction extends BuilderAction {
    static id = "setBlockClickable";
    apply({ editingElement }) {
        // Remove all text links since they won't be clickable anymore.
        // Keep the buttons for cosmetic purpose
        editingElement.querySelectorAll("a:not(.btn)").forEach((linkEl) => unwrapContents(linkEl));
        editingElement
            .querySelectorAll("img")
            .forEach((imgEl) => imgEl.classList.remove("o_image_popup"));
        const anchorEl = document.createElement("a");
        anchorEl.classList.add("stretched-link", "position-static");
        editingElement.prepend(anchorEl);
    }
    clean({ editingElement }) {
        editingElement.querySelector(":scope > a.stretched-link")?.remove();
    }
    isApplied({ editingElement }) {
        return !!editingElement.querySelector(":scope > a.stretched-link");
    }
}

class SetBlockAnchorUrlAction extends BuilderAction {
    static id = "setBlockAnchorUrl";
    apply({ editingElement, value }) {
        const linkEl = editingElement.querySelector(":scope > a.stretched-link");
        if (linkEl) {
            setHrefUrl(linkEl, value);
        }
    }
    getValue({ editingElement }) {
        const linkEl = editingElement.querySelector(":scope > a.stretched-link");
        return linkEl?.getAttribute("href") || "";
    }
}

registry.category("website-plugins").add(ClickableBlockOptionPlugin.id, ClickableBlockOptionPlugin);
