import { patch } from "@web/core/utils/patch";
import { fields } from "@mail/model/misc";
import { ResUsers } from "@mail/core/common/res_users_model";
import { getRelevantEmployee } from "./hr_employee_model";

patch(ResUsers.prototype, {
    setup() {
        super.setup();
        this.employee_ids = fields.Many("hr.employee", {
            inverse: "user_id",
        });
        this.employee_id = fields.One("hr.employee", {
            compute() {
                return getRelevantEmployee(this.employee_ids);
            },
        });
    },
});
