import { Record } from "@web/model/record";
import { Record as RecordDataPoint } from "@web/model/relational_model/record"
import { FormRenderer } from "@web/views/form/form_renderer";
import { Component, useRef, useState } from "@odoo/owl";
import { executeButtonCallback, useViewButtons } from "@web/views/view_button/view_button_hook";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { ViewButton } from "@web/views/view_button/view_button";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { serializeDate } from "@web/core/l10n/dates";

export class ResourceCalendarAttendancePopover extends Component {
    static template = "resource.ResourceCalendarAttendancePopover";
    static components = {
        Record,
        Dropdown,
        DropdownItem,
        FormRenderer,
        ViewButton,
    };
    static props = {
        close: Function,
        onReload: Function,
        endOcurrenceDateTime: { type: luxon.DateTime, optional: true },
        startOcurrenceDateTime: { type: luxon.DateTime, optional: true },
        originalRecord: { type: Object, optional: true },
        recordProps: { type: Object },
        archInfo: { type: Object },
        context: { type: Object },
        delta: { type: Number, optional: true },
    };
    static additionalFieldsToFetch = [
        { name: "calendar_id", type: "many2one", readonly: false },
        { name: "display_name", type: "char", readonly: false },
        { name: "date", type: "date", readonly: false },
        { name: "duration_based", type: "boolean", readonly: false },
        { name: "recurrency_excluded_occurences", type: "json", readonly: false },
    ];

    setup() {
        this.notification = useService("notification");
        this.rootRef = useRef("root");
        this.orm = useService("orm");
        this.state = useState({ hasRecurrencyChanged: false })
        useViewButtons(this.rootRef, {
            reload: this.props.onReload,
            afterExecuteAction: this.props.close,
        });
    }

    getDateWithDelta(date) {
        return date.plus(this.props.delta);
    }

    getDate(date) {
        if (this.props.delta) {
            return this.getDateWithDelta(date);
        }
        return date;
    }

    get currentRecordProps() {
        return {
            ...this.props.recordProps,
            resId: this.props.originalRecord?.id,
            mode: "edit",
            context: this.props.context,
            hooks: {
                onRootLoaded: (root) => {
                    root.canSaveOnUpdate = false;
                    if (this.props.delta) {
                        const start = this.getDateWithDelta(this.props.startOcurrenceDateTime)
                        const end = this.getDateWithDelta(this.props.endOcurrenceDateTime)
                        root.update({
                            date: start,
                            hour_from: start.hour + start.minute / 60,
                            hour_to: end.hour + end.minute / 60,
                        });
                    }
                },
                onRecordChanged: (record, changes) => {
                    this.state.hasRecurrencyChanged = Object.keys(changes).some((field) =>
                        field.includes("recurrency")
                    );
                },
            },
        };
    }

    isFakeRecord(record) {
        return this.props.startOcurrenceDateTime.toISODate() !== record._values.date.toISODate();
    }

    async onSave(record, mode) {
        await executeButtonCallback(this.rootRef.el, async () => {
            if (await record.checkValidity()) {
                try {
                    switch (mode) {
                        case "one": {
                            await this.orm.call(record.resModel, "create_ad_hoc", [
                                [record.resId],
                                serializeDate(this.getDate(this.props.startOcurrenceDateTime)),
                                await record.getChanges(),
                            ]);
                            break;
                        }
                        case "following": {
                            await this.orm.call(record.resModel, "create_new_recurrency", [
                                [record.resId],
                                serializeDate(this.getDate(this.props.startOcurrenceDateTime)),
                                await record.getChanges(),
                            ]);
                            break;
                        }
                        default:
                            await record.save();
                    }
                    await this.props.onReload();
                    this.props.close();
                } catch (error) {
                    return this.notification.add(_t(error.data.message), { type: "danger" });
                }
            }
        });
    }

    onDiscard(record) {
        if (this.props.delta) {
            this.props.close();
        } else {
            record.discard();
            this.state.hasRecurrencyChanged = false;
        }
    }

    async onDelete(record, mode) {
        await executeButtonCallback(this.rootRef.el, async () => {
            switch (mode) {
                case "one":
                    await this.orm.call(record.resModel, "exclude_occurence", [
                        [record.resId],
                        serializeDate(this.getDate(this.props.startOcurrenceDateTime)),
                    ]);
                    break;
                case "following":
                    await this.orm.call(record.resModel, "stop_recurrency", [
                        [record.resId],
                        serializeDate(this.getDate(this.props.startOcurrenceDateTime)),
                    ]);
                    break;
                default:
                    await record.delete()
            }
            this.props.close();
            await this.props.onReload();
        });
    }
}
