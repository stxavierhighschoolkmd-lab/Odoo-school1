import { DiscussChannel } from "@mail/discuss/core/common/discuss_channel_model";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").DiscussChannel} */
const discussChannelPatch = {
    get isAllowedToCreateLead() {
        return (
            this.channel_type === "livechat" &&
            this.store.has_access_livechat &&
            this.store.has_access_create_lead
        );
    },
};
patch(DiscussChannel.prototype, discussChannelPatch);
