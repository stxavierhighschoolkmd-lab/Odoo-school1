import { DiscussContent } from "@mail/core/public_web/discuss_content";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(DiscussContent.prototype, {
    setup() {
        super.setup(...arguments);
        this.store = useService("mail.store");
    },
    get meetingStatus() {
        const userId = this.thread?.channel?.correspondent?.persona?.main_user_id?.id;
        if (!userId) {
            return null;
        }
        const status = this.store.userMeetingStatuses?.[userId];
        if (status && status.until) {
            const untilDate = luxon.DateTime.fromSQL(status.until, { zone: "utc" });
            if (untilDate > luxon.DateTime.now()) {
                return {
                    until: untilDate.toLocal().toLocaleString(luxon.DateTime.TIME_SIMPLE),
                };
            }
        }
        return null;
    },
});
