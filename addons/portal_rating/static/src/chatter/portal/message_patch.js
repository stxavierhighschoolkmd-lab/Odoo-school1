import { Message } from "@mail/core/common/message";
import { convertBrToLineBreak } from "@mail/utils/common/format";

import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useEffect, useRef } from "@odoo/owl";

Message.components = { ...Message.components, DropdownItem };

patch(Message.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.editRating = false;
        this.state.showFullBody = false;
        this.state.isBodyClamped = false;
        this.richBodyRef = useRef("reviewRichBody");
        useEffect(() => {
            const el = this.richBodyRef.el;
            if (el) {
                this.state.isBodyClamped = el.scrollHeight > el.clientHeight;
            }
        }, () => [this.message.id]);
    },

    toggleBodyExpand() {
        this.state.showFullBody = !this.state.showFullBody;
    },

    get isEditing() {
        return !this.state.editRating && super.isEditing;
    },

    get ratingValue() {
        return this.message.rating_value || this.message.rating_id?.rating;
    },

    onClikEditComment() {
        this.state.editRating = !this.state.editRating;
        if (this.state.editRating) {
            const messageContent = convertBrToLineBreak(
                this.props.message.rating_id.publisher_comment
            );
            this.props.message.composer = {
                message: this.props.message,
                composerHtml: this.props.message.rating_id.publisher_comment,
                portalComment: true,
                selection: {
                    start: messageContent.length,
                    end: messageContent.length,
                    direction: "none",
                },
            };
        } else {
            this.message.composer = null;
        }
    },

    exitEditCommentMode() {
        this.props.message.composer.clear();
        this.message.composer = null;
        this.state.editRating = false;
    },

    async deleteComment() {
        const data = await rpc("/website/rating/comment", {
            rating_id: this.message.rating_id.id,
            publisher_comment: "",
        });
        this.message.rating_id = data;
    },
});
