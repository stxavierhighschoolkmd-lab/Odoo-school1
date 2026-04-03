import { registry } from "@web/core/registry";
import { resizeTextArea } from "@web/core/utils/autoresize";
import { Interaction } from "@web/public/interaction";

export class LinkedinMessageEditorInteraction extends Interaction {
    static selector = ".o_card_campaign_linkedin_share_composer textarea[name='text']";
    dynamicContent = {
        _root: { "t-on-input": this.onInput },
    };

    onInput() {
        resizeTextArea(this.el, { minimumHeight: 128 });
    }
}

registry
    .category("public.interactions")
    .add("marketing_card.linkedin_message_editor", LinkedinMessageEditorInteraction);
