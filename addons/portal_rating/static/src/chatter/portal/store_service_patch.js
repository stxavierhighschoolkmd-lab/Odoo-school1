import { Message } from "@mail/core/common/message_model";
import { Thread } from "@mail/core/common/thread";
import { Store } from "@mail/core/common/store_service";
import { PortalChatterService } from "@portal/chatter/portal/portal_chatter_service";

import { patch } from "@web/core/utils/patch";

// Scoped to review chatters only to avoid affecting eg. /my/orders/ chatter.
let isReviewChatter = false;

patch(PortalChatterService.prototype, {
    setup() {
        super.setup(...arguments);
        if (document.querySelector(".o_portal_chatter")?.getAttribute("data-display_rating") === "True") {
            this.store.FETCH_LIMIT = 3;
            isReviewChatter = true;
        }
    },
});

patch(Message.prototype, {
    get bubbleColor() {
        if (isReviewChatter) return undefined;
        return super.bubbleColor;
    },
});

patch(Thread.prototype, {
    applyScroll() {
        super.applyScroll(...arguments);
        if (this.env.displayRating) {
            this.loadOlderState.ready = false;
            this.loadNewerState.ready = false;
        }
    },
});

patch(Store.prototype, {
    async getMessagePostParams({ postData }) {
        const params = await super.getMessagePostParams(...arguments);
        if (postData.rating_value) {
            params.post_data.rating_value = postData.rating_value;
        }
        return params;
    },
});
