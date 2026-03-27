import { Store } from "@mail/core/common/store_service";

import { fields } from "@mail/model/export";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { patch } from "@web/core/utils/patch";

/** @type {import("models").Store} */
const StorePatch = {
    setup() {
        super.setup(...arguments);
        this._previousUserMeetingStatuses = {};
        this.userMeetingStatuses = fields.Attr(
            {},
            {
                onUpdate() {
                    const oldValue = this._previousUserMeetingStatuses || {};
                    const newValue = this.userMeetingStatuses;
                    this.userMeetingStatuses = {
                        ...oldValue,
                        ...newValue,
                    };
                    this._previousUserMeetingStatuses = { ...this.userMeetingStatuses };
                },
            }
        );
    },
    onUpdateActivityGroups() {
        super.onUpdateActivityGroups(...arguments);
        for (const group of Object.values(this.activityGroups)) {
            if (group.type === "meeting") {
                for (const meeting of group.meetings) {
                    if (meeting.start) {
                        const date = deserializeDateTime(meeting.start);
                        meeting.formattedStart = formatDateTime(date, {
                            format: localization.timeFormat,
                        });
                    }
                }
            }
        }
    },
};
patch(Store.prototype, StorePatch);
