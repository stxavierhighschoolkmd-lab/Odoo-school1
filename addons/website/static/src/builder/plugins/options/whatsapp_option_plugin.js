import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { BuilderAction } from "@html_builder/core/builder_action";
import { useDomState } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class WhatsappOption extends BaseOptionComponent {
    static id = "whatsapp_option";
    static template = "website.WhatsappOption";
    setup() {
        super.setup();
        this.state = useDomState((editingElement) => ({
            whatsappNumber: editingElement.dataset.whatsappNumber,
        }));
    }
}

class WhatsappOptionPlugin extends Plugin {
    static id = "whatsappOption";
    /** @type {import("plugins").WebsiteResources} */
    resources = {
        builder_actions: {
            ToggleChatBoxAction,
            AgentNameAction,
            AgentDescriptionAction,
            DefaultMessageAction,
            WhatsappNumberAction,
        },
        content_not_editable_selectors: ".s_whatsapp",
        replace_media_dialog_params_processors: this.applyImagesMediaDialogParams.bind(this),
        on_media_replaced_handlers: this.onMediaReplaced.bind(this),
        should_remove_overlay_options_predicates: (el) => {
            if (el.matches(".s_whatsapp")) {
                return true;
            }
        },
        is_valid_for_sibling_dropzone_predicates: (el) => {
            if (el.closest(".s_whatsapp")) {
                return false;
            }
        },
        on_snippet_dropped_handlers: ({ snippetEl }) => {
            // Open chatbox when whatsapp snippet is dropped.
            snippetEl.querySelector(".s_whatsapp .chatbox")?.classList.remove("d-none");
        },
        clean_for_save_processors: (root) => {
            root.querySelector(".s_whatsapp .chatbox")?.classList.add("d-none");
        },
    };
    applyImagesMediaDialogParams(params) {
        if (
            params.node?.nodeType === Node.ELEMENT_NODE &&
            params.node.matches(".s_whatsapp .wa-agent-img")
        ) {
            params.visibleTabs = ["IMAGES"];
        }
    }
    onMediaReplaced({ newMediaEl }) {
        // Ensure the chatbox is visible when we replace media.
        if (
            newMediaEl?.nodeType === Node.ELEMENT_NODE &&
            newMediaEl.matches(".s_whatsapp .wa-agent-img")
        ) {
            newMediaEl
                .closest(".s_whatsapp")
                ?.querySelector(".chatbox")
                ?.classList.remove("d-none");
        }
    }
}

export class ToggleChatBoxAction extends BuilderAction {
    static id = "toggleChatBox";
    apply({ editingElement }) {
        // Ensure the chatbox is visible when changing the chatbox elements.
        editingElement.querySelector(".chatbox")?.classList.remove("d-none");
    }
}

export class AgentNameAction extends BuilderAction {
    static id = "agentName";
    static dependencies = ["builderActions"];
    apply({ editingElement, value }) {
        editingElement.querySelector(".wa-agent-name").textContent = value;
        this.dependencies.builderActions.getAction("toggleChatBox").apply({
            editingElement: editingElement,
        });
    }
}

export class AgentDescriptionAction extends BuilderAction {
    static id = "agentDescription";
    static dependencies = ["builderActions"];
    apply({ editingElement, value }) {
        editingElement.querySelector(".wa-agent-description").textContent = value;
        this.dependencies.builderActions.getAction("toggleChatBox").apply({
            editingElement: editingElement,
        });
    }
}

export class DefaultMessageAction extends BuilderAction {
    static id = "defaultMessage";
    static dependencies = ["builderActions"];
    apply({ editingElement, value }) {
        editingElement.querySelector(".wa-agent-msg").textContent = value;
        this.dependencies.builderActions.getAction("toggleChatBox").apply({
            editingElement: editingElement,
        });
    }
}

export class WhatsappNumberAction extends BuilderAction {
    static id = "whatsappNumber";
    getValue({ editingElement }) {
        return editingElement.dataset.whatsappNumber;
    }
    apply({ editingElement, value }) {
        if (value) {
            editingElement.dataset.whatsappNumber = value;
        }
    }
}

registry.category("website-options").add(WhatsappOption.id, WhatsappOption);
registry.category("website-plugins").add(WhatsappOptionPlugin.id, WhatsappOptionPlugin);
