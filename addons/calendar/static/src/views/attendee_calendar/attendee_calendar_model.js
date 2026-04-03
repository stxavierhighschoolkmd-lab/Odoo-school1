import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { askRecurrenceUpdatePolicy } from "@calendar/views/ask_recurrence_update_policy_hook";
import {
    deleteConfirmationMessage,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";

export class AttendeeCalendarModel extends CalendarModel {
    static services = [...CalendarModel.services, "dialog", "orm"];

    setup(params, services) {
        super.setup(...arguments);
        this.dialog = services.dialog;
        this.rpc = rpc;
        this.activeTemporaryPartnerIds = null;
        this.visibleTemporaryPartnerIds = null;
    }

    /**
     * @override
     */
    async load() {
        const res = await super.load(...arguments);
        if (!this._loaded) {
            const [credentialStatus, syncStatus, defaultDuration] = await Promise.all([
                rpc("/calendar/check_credentials"),
                this.orm.call("res.users", "check_synchronization_status", [[user.userId]]),
                this.orm.call("calendar.event", "get_default_duration"),
            ]);
            this.syncStatus = syncStatus;
            this.credentialStatus = credentialStatus;
            this.defaultDuration = defaultDuration;
            this._loaded = true;
        }
        return res;
    }

    get attendees() {
        return this.data.attendees;
    }

    uniquePartnerIds(partnerIds) {
        return [...new Set(partnerIds.filter(Boolean))];
    }

    getPartnerFilterIds(filters, { activeOnly = false } = {}) {
        return this.uniquePartnerIds(
            filters
                .filter(
                    (filter) =>
                        filter.type !== "all" && filter.value && (!activeOnly || filter.active)
                )
                .map((filter) => filter.value)
        );
    }

    isTemporaryPartnerFilterMode(fieldName) {
        return fieldName === "partner_ids" && !!this.meta?.context?.calendar_temporary_filter;
    }

    getDefaultTemporaryPartnerFilterIds() {
        return this.uniquePartnerIds(this.meta?.context?.default_partner_ids || []);
    }

    updateCalendarFiltersContext(filters = []) {
        const activePartnerIds = this.getPartnerFilterIds(filters, { activeOnly: true });
        const isTemporaryPartnerFilterMode = this.isTemporaryPartnerFilterMode("partner_ids");
        if (isTemporaryPartnerFilterMode) {
            this.activeTemporaryPartnerIds = activePartnerIds;
        }
        user.updateContext({
            calendar_filters: {
                all: filters.length > 0 && filters.every((filter) => filter.active),
                user: filters.find((filter) => filter.type === "user")?.active ?? false,
                temporary: isTemporaryPartnerFilterMode,
                partner_ids: activePartnerIds,
            },
        });
    }

    makeTemporaryPartnerFilter(partnerId, label) {
        return {
            type: "temporary",
            recordId: `temporary_${partnerId}`,
            value: partnerId,
            label,
            active: true,
            canRemove: false,
            colorIndex: partnerId,
            hasAvatar: !!partnerId,
        };
    }

    async applyTemporaryPartnerFilters(filters) {
        const visibleTemporaryPartnerIds =
            this.visibleTemporaryPartnerIds ??
            this.uniquePartnerIds([
                ...this.getPartnerFilterIds(filters),
                ...this.getDefaultTemporaryPartnerFilterIds(),
            ]);
        const activeTemporaryPartnerIds =
            this.activeTemporaryPartnerIds ??
            this.uniquePartnerIds([
                ...this.getPartnerFilterIds(filters, { activeOnly: true }),
                ...this.getDefaultTemporaryPartnerFilterIds(),
            ]);
        this.visibleTemporaryPartnerIds = visibleTemporaryPartnerIds;
        const temporaryPartnerIdSet = new Set(activeTemporaryPartnerIds);
        const updatedFilters = filters.map((filter) => ({
            ...filter,
            active: temporaryPartnerIdSet.has(filter.value),
        }));
        const existingPartnerIds = new Set(this.getPartnerFilterIds(updatedFilters));
        const missingPartnerIds = visibleTemporaryPartnerIds.filter(
            (partnerId) => !existingPartnerIds.has(partnerId)
        );
        if (!missingPartnerIds.length) {
            return updatedFilters;
        }
        const partners = await this.orm.searchRead(
            "res.partner",
            [["id", "in", missingPartnerIds]],
            ["display_name"],
            {
                context: { active_test: false },
            }
        );
        const partnerById = new Map(partners.map((partner) => [partner.id, partner]));
        for (const partnerId of missingPartnerIds) {
            const filter = this.makeTemporaryPartnerFilter(
                partnerId,
                partnerById.get(partnerId)?.display_name || this.defaultFilterLabel
            );
            filter.active = temporaryPartnerIdSet.has(partnerId);
            updatedFilters.push(filter);
        }
        return updatedFilters;
    }

    /**
     * @override
     *
     * Upon updating a record with recurrence, we need to ask how it will affect recurrent events.
     */
    async updateRecord(record) {
        const rec = this.records[record.id];
        if (rec.rawRecord.recurrency) {
            const recurrenceUpdate = await askRecurrenceUpdatePolicy(this.dialog);
            if (!recurrenceUpdate) {
                return this.notify();
            }
            record.recurrenceUpdate = recurrenceUpdate;
        }
        return await super.updateRecord(...arguments);
    }

    /**
     * @override
     */
    buildRawRecord(partialRecord, options = {}) {
        const result = super.buildRawRecord(partialRecord, {
            ...options,
            duration_hour: this.defaultDuration,
        });
        if (partialRecord.recurrenceUpdate) {
            result.recurrence_update = partialRecord.recurrenceUpdate;
        }
        return result;
    }

    /**
     * Load the filter section and add both 'user' and 'everybody' filters to the context.
     * @override
     */
    async loadFilterSection(fieldName, filterInfo, previousSection) {
        const result = await super.loadFilterSection(fieldName, filterInfo, previousSection);
        if (result?.filters) {
            if (this.isTemporaryPartnerFilterMode(fieldName)) {
                result.filters = await this.applyTemporaryPartnerFilters(result.filters);
            }
            this.updateCalendarFiltersContext(result.filters);
        }
        return result;
    }

    /**
     * @override
     */
    async createFilter(fieldName, filterValue) {
        if (!this.isTemporaryPartnerFilterMode(fieldName)) {
            return super.createFilter(...arguments);
        }
        const filterValues = Array.isArray(filterValue) ? filterValue : [filterValue];
        this.visibleTemporaryPartnerIds = this.uniquePartnerIds([
            ...(this.visibleTemporaryPartnerIds || []),
            ...filterValues,
        ]);
        this.activeTemporaryPartnerIds = this.uniquePartnerIds([
            ...(this.activeTemporaryPartnerIds || []),
            ...filterValues,
        ]);
        return super.createFilter(...arguments);
    }

    /**
     * @override
     */
    async updateFilters(fieldName, filters, active) {
        if (!this.isTemporaryPartnerFilterMode(fieldName)) {
            return super.updateFilters(...arguments);
        }
        this.keepLast.add(Promise.resolve());
        for (const filter of filters) {
            filter.active = active;
        }
        this.updateCalendarFiltersContext(this.data.filterSections[fieldName]?.filters || []);
        await this.debouncedLoad();
    }

    /**
     * @override
     */
    async unlinkFilter(fieldName, recordId) {
        if (this.isTemporaryPartnerFilterMode(fieldName)) {
            const section = this.data.filterSections[fieldName];
            const filter = section?.filters.find(
                (currentFilter) => currentFilter.recordId === recordId
            );
            if (filter?.value) {
                this.visibleTemporaryPartnerIds = (this.visibleTemporaryPartnerIds || []).filter(
                    (partnerId) => partnerId !== filter.value
                );
                this.activeTemporaryPartnerIds = (this.activeTemporaryPartnerIds || []).filter(
                    (partnerId) => partnerId !== filter.value
                );
            }
        }
        return super.unlinkFilter(...arguments);
    }

    /**
     * @override
     */
    async updateData(data) {
        await super.updateData(...arguments);
        await this.updateAttendeeData(data);
    }

    /**
     * Split the events to display an event for each attendee with the correct status.
     * If the all filter is activated, we don't display an event for each attendee and keep
     * the previous behavior to display a single event.
     */
    async updateAttendeeData(data) {
        const attendeeFilters = data.filterSections.partner_ids;
        let isEveryoneFilterActive = false;
        let attendeeIds = [];
        const eventIds = Object.keys(data.records).map((id) => Number.parseInt(id));
        if (attendeeFilters) {
            const allFilter = attendeeFilters.filters.find((filter) => filter.type === "all");
            isEveryoneFilterActive = (allFilter && allFilter.active) || false;
            attendeeIds = attendeeFilters.filters
                .filter((filter) => filter.type !== "all" && filter.value)
                .map((filter) => filter.value);
        }
        data.attendees = await this.orm.call("res.partner", "get_attendee_detail", [
            attendeeIds,
            eventIds,
        ]);
        const currentPartnerId = user.partnerId;
        if (!isEveryoneFilterActive && attendeeFilters) {
            const activeAttendeeIds = new Set(
                attendeeFilters.filters
                    .filter((filter) => filter.type !== "all" && filter.value && filter.active)
                    .map((filter) => filter.value)
            );
            // Duplicate records per attendee
            const newRecords = {};
            let duplicatedRecordIdx = -1;
            for (const event of Object.values(data.records)) {
                const eventData = event.rawRecord;
                const attendees =
                    eventData.partner_ids && eventData.partner_ids.length
                        ? eventData.partner_ids
                        : [eventData.partner_id[0]];
                let duplicatedRecords = 0;
                for (const attendee of attendees) {
                    if (!activeAttendeeIds.has(attendee)) {
                        continue;
                    }
                    // Records will share the same rawRecord.
                    const record = { ...event };
                    const attendeeInfo = data.attendees.find(
                        (a) => a.id === attendee && a.event_id === event.id
                    );
                    record.attendeeId = attendee;
                    // Colors are linked to the partner_id but in this case we want it linked
                    // to attendeeId
                    record.colorIndex = attendee;
                    if (attendeeInfo) {
                        record.attendeeStatus = attendeeInfo.status;
                        record.isAlone = attendeeInfo.is_alone;
                        record.isCurrentPartner = attendeeInfo.id === currentPartnerId;
                        record.calendarAttendeeId = attendeeInfo.attendee_id;
                    }
                    const recordId = duplicatedRecords ? duplicatedRecordIdx-- : record.id;
                    // Index in the records
                    record._recordId = recordId;
                    newRecords[recordId] = record;
                    duplicatedRecords++;
                }
            }
            data.records = newRecords;
        } else {
            for (const event of Object.values(data.records)) {
                const eventData = event.rawRecord;
                event.attendeeId = eventData.partner_id && eventData.partner_id[0];
                const attendeeInfo = data.attendees.find(
                    (a) => a.id === currentPartnerId && a.event_id === event.id
                );
                if (attendeeInfo) {
                    event.isAlone = attendeeInfo.is_alone;
                    event.calendarAttendeeId = attendeeInfo.attendee_id;
                }
            }
        }
    }

    /**
     * Archives a record, ask for the recurrence update policy in case of recurrent event.
     */
    async archiveRecord(record) {
        let recurrenceUpdate = false;
        if (record.rawRecord.recurrency) {
            recurrenceUpdate = await askRecurrenceUpdatePolicy(this.dialog);
            if (!recurrenceUpdate) {
                return;
            }
        } else {
            const confirm = await new Promise((resolve) => {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("Bye-bye, record!"),
                    body: deleteConfirmationMessage,
                    confirm: resolve.bind(null, true),
                    confirmLabel: _t("Delete"),
                    cancel: () => resolve.bind(null, false),
                    cancelLabel: _t("No, keep it"),
                });
            });
            if (!confirm) {
                return;
            }
        }
        await this._archiveRecord(record.id, recurrenceUpdate);
    }

    async _archiveRecord(id, recurrenceUpdate) {
        if (!recurrenceUpdate && recurrenceUpdate !== "self_only") {
            await this.orm.call(this.resModel, "action_archive", [[id]]);
        } else {
            await this.orm.call(this.resModel, "action_mass_archive", [[id], recurrenceUpdate]);
        }
        await this.load();
    }

    normalizeRecord(rawRecord) {
        const normalizedRecord = super.normalizeRecord(rawRecord);
        if (rawRecord.effective_privacy === "private") {
            normalizedRecord.titleIcon = "fa fa-lock";
        }
        return normalizedRecord;
    }
}
