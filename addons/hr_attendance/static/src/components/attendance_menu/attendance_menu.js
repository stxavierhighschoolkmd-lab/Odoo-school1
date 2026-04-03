import { useState } from "@web/owl2/utils";
import { Component, onWillStart } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { deserializeDateTime, serializeDateTime } from "@web/core/l10n/dates";
import { Time } from "@web/core/l10n/time";
import { _t } from "@web/core/l10n/translation";
import { rpc, ConnectionLostError } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { formatFloatTime } from "@web/views/fields/formatters";
import { TimePicker } from "@web/core/time_picker/time_picker";
import { useService } from "@web/core/utils/hooks";
import { isIosApp } from "@web/core/browser/feature_detection";
import { BreakDurationDialog } from "@hr_attendance/components/break_duration_dialog/break_duration_dialog";

export class ActivityMenu extends Component {
    static components = { Dropdown, DropdownItem, TimePicker };
    static props = [];
    static template = "hr_attendance.attendance_menu";

    setup() {
        this.ui = useService("ui");
        this.dialog = useService("dialog");
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.lazySession = useService("lazy_session");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.state = useState({
            employee: null,
            todayAttendanceRecords: [],
            checkedIn: false,
            isDisplayed: false,
            reviewAttendanceId: null,
            editingAttendanceId: null,
            savingAttendance: false,
            editDraft: {
                checkIn: null,
                checkOut: null,
                breakDuration: "0",
            },
        });

        this.dropdown = useDropdownState();

        onWillStart(() => {
            this.lazySession.getValue("attendance_user_data", (employee) => {
                if (employee) {
                    this.state.employee = employee;
                    this._searchReadEmployeeFill();
                }
            });
        });
    }

    async searchReadEmployee() {
        this.state.employee = await rpc("/hr_attendance/attendance_user_data");
        this._searchReadEmployeeFill();
    }

    _searchReadEmployeeFill() {
        if (!this.employee?.id) {
            this.state.isDisplayed = false;
            this.state.todayAttendanceRecords = [];
            return;
        }

        this.state.isDisplayed = this.employee.display_systray;
        this.state.checkedIn = this.employee.attendance_state === "checked_in";

        this.state.todayAttendanceRecords = [...(this.employee.today_attendance_ids || [])].sort(
            (attendanceA, attendanceB) =>
                deserializeDateTime(attendanceA.check_in).ts -
                deserializeDateTime(attendanceB.check_in).ts
        );

        const fallbackReviewId =
            this.employee.last_attendance?.id || this.todayAttendanceRecords.at(-1)?.id || null;
        if (!this._getAttendanceById(this.state.reviewAttendanceId)) {
            this.state.reviewAttendanceId = fallbackReviewId;
        }
        if (this.state.editingAttendanceId && !this._getAttendanceById(this.state.editingAttendanceId)) {
            this.cancelInlineEdit();
        }

    }

    get employee() {
        return this.state.employee;
    }

    get employeeName() {
        return this.employee?.name || "";
    }

    get todayAttendanceRecords() {
        return this.state.todayAttendanceRecords;
    }

    get todayAttendanceSessions() {
        return this._buildAttendanceSessions();
    }

    get attendanceReview() {
        return this._buildAttendanceReview(this._getAttendanceById(this.state.reviewAttendanceId));
    }

    get hasCheckedInToday() {
        return this.todayAttendanceSessions.length > 0;
    }

    _buildAttendanceSessions() {
        return this.todayAttendanceRecords.map((att) => {
            const checkInDate = deserializeDateTime(att.check_in);
            const checkOutDate = att.check_out ? deserializeDateTime(att.check_out) : null;
            const duration = att.check_out ? att.worked_hours : this.employee.last_attendance_worked_hours;
            return {
                id: att.id,
                canEdit: Boolean(att.can_edit),
                selected: att.id === this.state.reviewAttendanceId,
                rangeLabel: `${this._formatAttendanceTime(checkInDate)} - ${
                    checkOutDate ? this._formatAttendanceTime(checkOutDate) : _t("Now")
                }`,
                durationLabel: this._formatCompactDuration(duration),
            };
        });
    }

    _getAttendanceById(attendanceId) {
        if (!attendanceId) {
            return this.employee?.last_attendance || null;
        }
        return (
            this.todayAttendanceRecords.find((attendance) => attendance.id === attendanceId) ||
            (this.employee?.last_attendance?.id === attendanceId ? this.employee.last_attendance : null)
        );
    }

    _buildAttendanceReview(attendance) {
        if (!(attendance && attendance.check_in)) {
            return null;
        }
        const checkIn = deserializeDateTime(attendance.check_in);
        const checkOut = attendance.check_out ? deserializeDateTime(attendance.check_out) : null;
        const daySummary = this._getReviewSummary(attendance);
        return {
            id: attendance.id,
            canEdit: Boolean(attendance.can_edit),
            dateLabel: this._formatAttendanceDateLabel(checkIn, checkOut),
            entries: [
                {
                    key: "check_in",
                    label: _t("Check In"),
                    time: this._formatAttendanceTime(checkIn),
                    location: attendance.in_location || false,
                    pending: false,
                },
                {
                    key: "check_out",
                    label: _t("Check Out"),
                    time: checkOut ? this._formatAttendanceTime(checkOut) : _t("Pending"),
                    location: checkOut ? attendance.out_location || false : false,
                    pending: !checkOut,
                },
            ],
            showBreakSummary: Boolean(this.employee.break_management_enabled),
            breakDisplay: formatFloatTime(daySummary.breakDuration, { numeric: true }),
            totalDisplay: formatFloatTime(daySummary.workedHours, { numeric: true }),
            sessions: this.todayAttendanceSessions,
        };
    }

    _formatAttendanceDateLabel(checkIn, checkOut) {
        const options = {
            weekday: "long",
            day: "numeric",
            month: "short",
        };
        const startLabel = checkIn.toLocaleString(options);
        if (!(checkOut && !checkIn.hasSame(checkOut, "day"))) {
            return startLabel;
        }
        return `${startLabel} - ${checkOut.toLocaleString(options)}`;
    }

    _formatAttendanceTime(dateTime) {
        return dateTime.toLocaleString({
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    _formatCompactDuration(duration) {
        return formatFloatTime(duration || 0, { numeric: true }).replace(":", "h");
    }

    _parseDateTimeInputValue(value) {
        return value?.isValid ? value : null;
    }

    _getAttendanceFieldDateTime(attendance, fieldName) {
        const attendanceField = fieldName === "checkIn" ? "check_in" : "check_out";
        return attendance?.[attendanceField] ? deserializeDateTime(attendance[attendanceField]) : null;
    }

    _getInlineTimeValue(dateTime) {
        const value = this._parseDateTimeInputValue(dateTime);
        return value ? new Time(value.toObject()) : null;
    }

    _getInlineEditBaseDate(fieldName) {
        const currentDraftValue = this._parseDateTimeInputValue(this.state.editDraft[fieldName]);
        if (currentDraftValue) {
            return currentDraftValue;
        }
        const attendance = this._getAttendanceById(this.state.editingAttendanceId);
        const attendanceValue = this._getAttendanceFieldDateTime(attendance, fieldName);
        if (attendanceValue) {
            return attendanceValue;
        }
        if (fieldName === "checkOut") {
            return (
                this._parseDateTimeInputValue(this.state.editDraft.checkIn) ||
                this._getAttendanceFieldDateTime(attendance, "checkIn")
            );
        }
        return null;
    }

    _formatBreakDurationInputValue(durationHours) {
        return String(Math.max(durationHours || 0, 0));
    }

    _parseBreakDurationInputValue(durationValue) {
        return Math.max(Number(durationValue) || 0, 0);
    }

    _getAttendanceMetrics(attendance, { includeDraft = false } = {}) {
        const isEditingAttendance = includeDraft && attendance.id === this.state.editingAttendanceId;
        if (isEditingAttendance) {
            const checkInDate = this._parseDateTimeInputValue(this.state.editDraft.checkIn);
            const checkOutDate = this._parseDateTimeInputValue(this.state.editDraft.checkOut);
            if (checkInDate?.isValid) {
                const breakDuration = checkOutDate?.isValid
                    ? this._parseBreakDurationInputValue(this.state.editDraft.breakDuration)
                    : 0;
                const endDate = checkOutDate?.isValid ? checkOutDate : luxon.DateTime.now();
                const workedHours = Math.max(endDate.diff(checkInDate, "minutes").minutes / 60 - breakDuration, 0);
                return {
                    breakDuration,
                    workedHours,
                };
            }
        }
        return {
            breakDuration: attendance.check_out ? attendance.break_duration || 0 : 0,
            workedHours: attendance.check_out
                ? attendance.worked_hours || 0
                : this.employee.last_attendance_worked_hours || 0,
        };
    }

    _getAttendanceDaySummary({ includeDraft = false } = {}) {
        return this.todayAttendanceRecords.reduce(
            (summary, attendance) => {
                const metrics = this._getAttendanceMetrics(attendance, { includeDraft });
                summary.breakDuration += metrics.breakDuration;
                summary.workedHours += metrics.workedHours;
                return summary;
            },
            { breakDuration: 0, workedHours: 0 }
        );
    }

    _getReviewSummary(attendance, { includeDraft = false } = {}) {
        if (!attendance) {
            return { breakDuration: 0, workedHours: 0 };
        }
        if (this.todayAttendanceRecords.some((todayAttendance) => todayAttendance.id === attendance.id)) {
            return this._getAttendanceDaySummary({ includeDraft });
        }
        return this._getAttendanceMetrics(attendance, { includeDraft });
    }

    _serializeDateTimeInputValue(inputValue) {
        const dateTime = this._parseDateTimeInputValue(inputValue);
        if (!dateTime) {
            return false;
        }
        return serializeDateTime(dateTime.set({ second: 0, millisecond: 0 }));
    }

    _getInlineEditErrorMessage(error) {
        return error?.data?.message || error?.message || _t("Could not update this attendance.");
    }

    updateInlineDateTimeDraft(fieldName, value) {
        if (fieldName) {
            const baseDate = this._getInlineEditBaseDate(fieldName);
            const timeValue = Time.from(value);
            let nextDateTime = baseDate && timeValue ? baseDate.set(timeValue.toObject()) : null;
            if (fieldName === "checkOut" && nextDateTime) {
                const originalCheckOut = this._getAttendanceFieldDateTime(
                    this._getAttendanceById(this.state.editingAttendanceId),
                    "checkOut"
                );
                const checkInDateTime = this._parseDateTimeInputValue(this.state.editDraft.checkIn);
                if (!originalCheckOut && checkInDateTime && nextDateTime < checkInDateTime) {
                    nextDateTime = nextDateTime.plus({ days: 1 });
                }
            }
            this.state.editDraft[fieldName] = nextDateTime;
        }
    }

    selectAttendance(attendanceId) {
        if (this.state.editingAttendanceId && this.state.editingAttendanceId !== attendanceId) {
            return;
        }
        if (!this._getAttendanceById(attendanceId)) {
            return;
        }
        this.state.reviewAttendanceId = attendanceId;
    }

    isEditingReview(review) {
        return Boolean(review && this.state.editingAttendanceId === review.id);
    }

    startInlineEdit(attendanceId = this.state.reviewAttendanceId) {
        const attendance = this._getAttendanceById(attendanceId);
        if (!(attendance && attendance.can_edit)) {
            return;
        }
        this.state.reviewAttendanceId = attendance.id;
        this.state.editingAttendanceId = attendance.id;
        this.state.editDraft.checkIn = deserializeDateTime(attendance.check_in);
        this.state.editDraft.checkOut = attendance.check_out ? deserializeDateTime(attendance.check_out) : null;
        this.state.editDraft.breakDuration = this._formatBreakDurationInputValue(
            attendance.break_duration || 0
        );
    }

    cancelInlineEdit() {
        this.state.editingAttendanceId = null;
        this.state.savingAttendance = false;
        if (!this.state.reviewAttendanceId && this.employee?.last_attendance?.id) {
            this.state.reviewAttendanceId = this.employee.last_attendance.id;
        }
    }

    getReviewBreakDisplay(review) {
        if (!this.isEditingReview(review)) {
            return review.breakDisplay;
        }
        const attendance = this._getAttendanceById(review.id);
        return formatFloatTime(
            this._getReviewSummary(attendance, { includeDraft: true }).breakDuration,
            { numeric: true }
        );
    }

    getReviewTotalDisplay(review) {
        if (!this.isEditingReview(review)) {
            return review.totalDisplay;
        }
        const attendance = this._getAttendanceById(review.id);
        return formatFloatTime(
            this._getReviewSummary(attendance, { includeDraft: true }).workedHours,
            { numeric: true }
        );
    }

    async saveInlineEdit() {
        const attendanceId = this.state.editingAttendanceId;
        if (!attendanceId || this.state.savingAttendance) {
            return;
        }
        if (!this._parseDateTimeInputValue(this.state.editDraft.checkIn)) {
            this.notification.add(_t("Check-in is required."), {
                title: _t("Attendance Error"),
                type: "danger",
            });
            return;
        }
        this.state.savingAttendance = true;
        try {
            const vals = {
                check_in: this._serializeDateTimeInputValue(this.state.editDraft.checkIn),
                check_out: this.state.editDraft.checkOut
                    ? this._serializeDateTimeInputValue(this.state.editDraft.checkOut)
                    : false,
                break_duration: this.state.editDraft.checkOut
                    ? this._parseBreakDurationInputValue(this.state.editDraft.breakDuration)
                    : 0,
            };
            await this.orm.write("hr.attendance", [attendanceId], vals);
            this.state.editingAttendanceId = null;
            await this.searchReadEmployee();
        } catch (error) {
            this.notification.add(this._getInlineEditErrorMessage(error), {
                title: _t("Attendance Error"),
                type: "danger",
            });
        } finally {
            this.state.savingAttendance = false;
        }
    }

    splitTime(timeStr) {
        const [h, m] = timeStr.split(":");
        return { h, m };
    }

    async checking(latitude = false, longitude = false, breakDurationHours = null) {
        try {
            this.state.employee = await rpc("/hr_attendance/systray_check_in_out", {
                latitude,
                longitude,
                break_duration: breakDurationHours,
            });
            this._searchReadEmployeeFill();
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                this.notification.add(_t("Connection lost. Check in/out could not be recorded."), {
                    title: _t("Attendance Error"),
                    type: "danger",
                    sticky: false,
                });
            } else {
                throw error;
            }
        } finally {
            this._attendanceInProgress = false;
        }
    }

    confirmChecking(breakDurationHours = null) {
        this.dialogService.add(ConfirmationDialog, {
            body: _t("Unable to get a valid location. Do you want to proceed with your check-in/out anyway?"),
            confirmLabel: _t("Proceed Anyway"),
            confirm: async () => await this.checking(false, false, breakDurationHours),
            cancel: () => (this._attendanceInProgress = false),
        });
    }

    async signInOut() {
        this.dropdown.close();
        if (this._attendanceInProgress) {
            return;
        }
        this._attendanceInProgress = true;

        try {
            await this.searchReadEmployee();
            if (!this.employee || !this.employee.id) {
                this._attendanceInProgress = false;
                return;
            }
            let breakDurationHours = null;
            if (this.employee.break_management_enabled && this.employee.attendance_state === "checked_in") {
                const minutes = await this.requestBreakDuration();
                if (minutes === null) {
                    this._attendanceInProgress = false;
                    return;
                }
                breakDurationHours = (Number(minutes) || 0) / 60;
            }
            const trackingEnabled = this.employee && this.employee.device_tracking_enabled;
            if (trackingEnabled && !isIosApp() && navigator.geolocation && navigator.onLine) {
                navigator.geolocation.getCurrentPosition(
                    async ({ coords: { latitude, longitude } }) => {
                        await this.checking(latitude, longitude, breakDurationHours);
                    },
                    () => {
                        this.confirmChecking(breakDurationHours);
                    },
                    {
                        enableHighAccuracy: true,
                        timeout: 10000,
                    }
                );
            } else if (trackingEnabled) {
                this.confirmChecking(breakDurationHours);
            } else {
                await this.checking(false, false, breakDurationHours);
            }
        } catch (error) {
            this._attendanceInProgress = false;
            throw error;
        }
    }

    async requestBreakDuration() {
        return new Promise((resolve) => {
            let settled = false;
            const finalize = (value) => {
                if (!settled) {
                    settled = true;
                    resolve(value);
                }
            };
            this.dialog.add(BreakDurationDialog, {
                employeeName: this.employee?.name,
                defaultMinutes: 0,
                onConfirm: (minutes) => finalize(minutes),
                onCancel: () => finalize(null),
            });
        });
    }
}

export const systrayAttendance = {
    Component: ActivityMenu,
};

registry
    .category("systray")
    .add("hr_attendance.attendance_menu", systrayAttendance, { sequence: 70 });
