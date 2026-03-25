import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { useService } from "@web/core/utils/hooks";
import { ResourceCalendarAttendancePopover } from "../../components/resource_calendar_attendance_popover/resource_calendar_attendance_popover";
import { serializeDate } from "@web/core/l10n/dates";
import { usePopover } from "@web/core/popover/popover_hook";

export class ResourceCalendarAttendanceCalendarCommonRenderer extends CalendarCommonRenderer {
    static components = {
        ...CalendarCommonRenderer,
    };

    setup() {
        super.setup();
        this.popover = usePopover(ResourceCalendarAttendancePopover, {
            position: "right",
            onClose: () => {
                this.fc.api.unselect();
                this.popoverPromise.resolve();
            },
        });
        this.resourceCalendarAttendancePopoverService = useService(
            "resourceCalendarAttendancePopoverService"
        );
        this.resourceCalendarAttendancePopoverService.setup(
            this.props.model.meta,
            ResourceCalendarAttendancePopover.additionalFieldsToFetch
        );
    }

    get interactiveOptions() {
        return {
            ...super.interactiveOptions,
            selectable: this.props.model.canCreate,
            forceEventDuration: true,
        };
    }

    eventClassNames({ el, event }) {
        const classes = super.eventClassNames({ el, event });
        const pastEventClass = classes.indexOf("o_past_event");
        if (pastEventClass != -1 && luxon.DateTime.now() <= event.end) {
            classes.splice(pastEventClass, 1);
        }
        return classes;
    }

    onEventDragStart(info) {
        this.popover.close();
        if (info.event.allDay) {
            const hours = Math.floor(info.event.extendedProps.forcedDuration);
            const minutes = Math.round((info.event.extendedProps.forcedDuration - hours) * 60);
            info.view.calendar.setOption(
                "defaultTimedEventDuration",
                `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`
            );
        }
        super.onEventDragStart(...arguments);
    }

    onEventResize(info) {
        const res = super.onEventResize(...arguments)
        return res;
    }

    onEventResizeStart(info) {
        this.popover.close();
        super.onEventResizeStart(...arguments);
    }

    async onEventDrop(info) {
        if (info.oldEvent.allDay) {
            info.view.calendar.setOption("defaultTimedEventDuration", "01:00");
        }
        const record = this.props.model.records[info.event.id];
        if (record.rawRecord.recurrency) {
            this.fc.api.unselect();
            const dropTarget = document.elementFromPoint(
                info.jsEvent.clientX,
                info.jsEvent.clientY
            );
            dropTarget.fcSeg = info.el.fcSeg
            record.delta = info.delta;
            this.openPopover(dropTarget, record);
            this.popoverPromise.promise.then(() => {
                this.props.model.load()
            });
        } else {
            super.onEventDrop(...arguments);
        }
    }

    async onSelect(info) {
        info.jsEvent?.preventDefault();
        this.popoverPromise = Promise.withResolvers();
        const start = luxon.DateTime.fromJSDate(info.start);
        const end = luxon.DateTime.fromJSDate(info.end);
        this.popover.open(
            info.jsEvent?.toElement ?? info.view.calendar.el.querySelector(".fc-event-mirror"),
            {
                ...this.getPopoverProps(null),
                context: {
                    ...this.props.model.meta.context,
                    default_date: serializeDate(start),
                    default_hour_from: start.hour + start.minute / 60,
                    default_hour_to: end.hour + end.minute / 60,
                },
            },
            `o_cw_popover card o_calendar_color_0`
        );
    }

    handleDateClick(info) {
        super.handleDateClick(info);
        if (this.props.model.hasMultiCreate) {
            this.onDateClick(info);
        }
    }

    onDateClick(info) {
        const date = luxon.DateTime.fromJSDate(info.date);
        info?.view?.calendar.select(date.toISO(), date.plus({ hours: 1 }).toISO());
    }

    mapRecordsToEvents() {
        const { records } = this.props.model.data;
        const events = [];
        Object.values(records).forEach((r) => {
            if (r.rawRecord.other_dates.length) {
                r.rawRecord.other_dates.forEach((date) => {
                    const temp_record = this.props.model.normalizeRecord({
                        ...r.rawRecord,
                        date: date,
                    });
                    events.push(this.convertRecordToEvent(temp_record));
                });
            }
            events.push(this.convertRecordToEvent(r));
        });
        return events;
    }

    convertRecordToEvent(record) {
        const res = super.convertRecordToEvent(...arguments);
        res.forcedDuration = record.duration;
        return res;
    }

    /**
     * @override
     */
    getPopoverProps(record) {
        return {
            onReload: async () => await this.props.model.load(),
            startOcurrenceDateTime: record?.startOcurrenceDateTime,
            endOcurrenceDateTime: record?.endOcurrenceDateTime,
            originalRecord: record?.rawRecord,
            recordProps: this.resourceCalendarAttendancePopoverService.recordProps,
            archInfo: this.resourceCalendarAttendancePopoverService.archInfo,
            context: this.props.model.meta.context,
            delta: record?.delta,
        };
    }

    openPopover(target, record) {
        this.popoverPromise = Promise.withResolvers();
        const start = new luxon.DateTime.fromJSDate(target.fcSeg.start);
        const end = new luxon.DateTime.fromJSDate(target.fcSeg.end);
        record.startOcurrenceDateTime = start.set({
            hour: record.start.hour,
            minute: record.start.minute,
        });
        record.endOcurrenceDateTime = end.set({
            hour: record.end.hour,
            minute: record.end.minute,
        });
        return super.openPopover(...arguments);
    }
}
