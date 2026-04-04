import { Activity } from "@mail/core/web/activity";
import { isToday } from "@mail/utils/common/dates";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(Activity.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.isToday = isToday;
    },
    get dateFormat() {
        return luxon.DateTime.DATE_FULL;
    },
    get meeting() {
        return this.props.activity.calendar_event_id;
    },
    get timeFormat() {
        return luxon.DateTime.TIME_SIMPLE;
    },
    async onClickReschedule() {
        await this.props.activity.rescheduleMeeting();
    },
});
