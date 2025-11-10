import { Component } from "@odoo/owl";
import { BreakDurationDialog } from "@hr_attendance/components/break_duration_dialog/break_duration_dialog";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

export class CheckInOut extends Component {
    static template = "hr_attendance.CheckInOut";
    static props = {
        checkedIn: Boolean,
        employeeId: Number,
        nextAction: String,
    };

    setup() {
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.onClickSignInOut = useDebounced(this.signInOut, 200, { immediate: true });
    }

    async signInOut() {
        let breakDurationHours = null;
        if (this.props.checkedIn) {
            const [employee] = await this.orm.read("hr.employee", [this.props.employeeId], ["name", "company_id", "attendance_state"]);
            if (employee?.attendance_state === "checked_in" && employee.company_id?.[0]) {
                const [company] = await this.orm.read("res.company", [employee.company_id[0]], ["attendance_break_management"]);
                if (company?.attendance_break_management) {
                    const minutes = await this.requestBreakDuration(employee.name);
                    if (minutes === null) {
                        return;
                    }
                    breakDurationHours = (Number(minutes) || 0) / 60;
                }
            }
        }
        navigator.geolocation.getCurrentPosition(
            ({coords: {latitude, longitude}}) => {
                this.orm.call("hr.employee", "update_last_position", [
                    [this.props.employeeId],
                    latitude,
                    longitude
                ])
            },
            err => {
                this.orm.call("hr.employee", "update_last_position", [
                    [this.props.employeeId],
                    false,
                    false
                ])
            })
        const result = await this.orm.call("hr.employee", "attendance_manual_with_break", [
            [this.props.employeeId],
            breakDurationHours,
        ]);
        if (result.action) {
            this.actionService.doAction(result.action);
        } else if (result.warning) {
            this.notification.add(result.warning, {type: "danger"});
        }
    }

    async requestBreakDuration(employeeName) {
        return new Promise((resolve) => {
            let settled = false;
            const finalize = (value) => {
                if (!settled) {
                    settled = true;
                    resolve(value);
                }
            };
            this.dialog.add(BreakDurationDialog, {
                employeeName,
                defaultMinutes: 0,
                onConfirm: (minutes) => finalize(minutes),
                onCancel: () => finalize(null),
            });
        });
    }
}
