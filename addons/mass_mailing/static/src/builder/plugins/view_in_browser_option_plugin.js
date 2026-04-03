import { BuilderAction } from "@html_builder/core/builder_action";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

const VIEW_IN_BROWSER_LINK_CLASS = "o_snippet_view_in_browser";
const VIEW_IN_BROWSWER_SNIPPET_NAME = "s_mail_block_header_view";

export class ViewInBrowserOptionPlugin extends Plugin {
    static id = "viewInBrowserOptionPlugin";
    static shared = ["getViewInBrowserLink", "insertViewInBrowserLink", "removeViewInBrowserLink"];
    static dependencies = ["history"];

    resources = {
        builder_actions: {
            ToggleViewInBrowserAction,
        },
    };

    setup() {
        this.snippet = this.config.snippetModel.snippetStructures.find(
            (s) => s.name === VIEW_IN_BROWSWER_SNIPPET_NAME
        );
        this.snippet.isDisabled = true; // Hide the snippet from the snippet library
    }

    insertViewInBrowserLink() {
        if (this.getViewInBrowserLink()) {
            return;
        }

        const linkElement = this.snippet.content.cloneNode(true);
        this.editable.querySelector(".o_mail_wrapper .o_mail_wrapper_td").prepend(linkElement);
        this.dependencies.history.addStep();
    }

    removeViewInBrowserLink() {
        const link = this.getViewInBrowserLink();
        if (!link) {
            return;
        }
        link.remove();
        this.dependencies.history.addStep();
    }

    getViewInBrowserLink() {
        return this.editable.querySelector(`.${VIEW_IN_BROWSER_LINK_CLASS}`);
    }
}

export class ToggleViewInBrowserAction extends BuilderAction {
    static id = "mass_mailing.ToggleViewInBrowserAction";
    static dependencies = ["viewInBrowserOptionPlugin"];

    setup() {
        this.preview = false;
    }

    apply() {
        if (!this.isApplied(...arguments)) {
            this.dependencies["viewInBrowserOptionPlugin"].insertViewInBrowserLink();
        } else {
            this.dependencies["viewInBrowserOptionPlugin"].removeViewInBrowserLink();
        }
    }

    isApplied() {
        return this.dependencies["viewInBrowserOptionPlugin"].getViewInBrowserLink();
    }
}

registry
    .category("mass_mailing-plugins")
    .add(ViewInBrowserOptionPlugin.id, ViewInBrowserOptionPlugin);
