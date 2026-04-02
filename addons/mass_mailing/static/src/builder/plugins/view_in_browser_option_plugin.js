import { BuilderAction } from "@html_builder/core/builder_action";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

const VIEW_IN_BROWSER_LINK_SELECTOR = "o_snippet_view_in_browser";
const VIEW_IN_BROWSWER_SNIPPET_NAME = "s_mail_block_header_view";

export class ViewInBrowserOptionPlugin extends Plugin {
    static id = "mass_mailing.ViewInBrowserOptionPlugin";
    static shared = ["isPresent", "insertViewInBrowserLink", "removeViewInBrowserLink"];
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

    isPresent() {
        return Boolean(this.linkElement);
    }

    insertViewInBrowserLink() {
        if (this.isPresent()) {
            return;
        }

        const linkElement = this.snippet.content.cloneNode(true);
        this.editable.querySelector(".o_mail_wrapper .o_mail_wrapper_td").prepend(linkElement);
        this.dependencies.history.addStep();
    }

    removeViewInBrowserLink() {
        if (!this.isPresent()) {
            return;
        }
        this.linkElement.remove();
        this.dependencies.history.addStep();
    }

    get linkElement() {
        return this.editable.querySelector(`.${VIEW_IN_BROWSER_LINK_SELECTOR}`);
    }
}

export class ToggleViewInBrowserAction extends BuilderAction {
    static id = "mass_mailing.ToggleViewInBrowserAction";
    static dependencies = ["mass_mailing.ViewInBrowserOptionPlugin"];

    setup() {
        this.preview = false;
    }

    apply() {
        if (!this.isApplied(...arguments)) {
            this.dependencies["mass_mailing.ViewInBrowserOptionPlugin"].insertViewInBrowserLink();
        } else {
            this.dependencies["mass_mailing.ViewInBrowserOptionPlugin"].removeViewInBrowserLink();
        }
    }

    isApplied() {
        return this.dependencies["mass_mailing.ViewInBrowserOptionPlugin"].isPresent();
    }
}

registry
    .category("mass_mailing-plugins")
    .add(ViewInBrowserOptionPlugin.id, ViewInBrowserOptionPlugin);
