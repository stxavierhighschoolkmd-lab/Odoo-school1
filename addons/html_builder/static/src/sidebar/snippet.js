import { Image } from "@html_builder/core/img";
import { handleMatrixKeyNavigation } from "@html_builder/utils/backend_utils";
import { Component } from "@odoo/owl";

export class Snippet extends Component {
    static template = "html_builder.Snippet";
    static components = { Image };
    static props = {
        snippetModel: { type: Object },
        snippet: { type: Object },
        onClickHandler: { type: Function },
        disabledTooltip: { type: String },
    };

    get snippet() {
        return this.props.snippet;
    }

    onInstallableHover(ev) {
        if (this.snippet.isInstallable) {
            ev.currentTarget
                .querySelector(".o_install_btn")
                .classList.toggle("visually-hidden-focusable", ev.type !== "mouseover");
        }
    }

    onBtnKeydown(ev) {
        handleMatrixKeyNavigation(ev, {
            containerEl: ev.currentTarget.closest(".o_snippets_container_body"),
            focusedItemSelector: ".o_snippet",
            focusableElSelector: ".o_snippet_thumbnail_area, .o_install_btn",
        });
    }

    onClickInstall() {
        this.props.snippetModel.installSnippetModule(
            this.props.snippet,
            this.env.editor.config.installSnippetModule
        );
    }
}
