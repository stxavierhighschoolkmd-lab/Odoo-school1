import { Record, fields } from "@mail/core/common/record";
import { user } from "@web/core/user";

export function getRelevantEmployee(employees) {
    const activeEmployees = (employees ?? []).filter((e) => e.active);
    const sortedEmployees = activeEmployees.sort(
        (e1, e2) => (e1.user_id?.id ?? Infinity) - (e2.user_id?.id ?? Infinity) || e2.id - e1.id
    );
    return (
        sortedEmployees.find((employee) => employee.company_id?.id === user.activeCompany?.id) ||
        sortedEmployees[0]
    );
}

export class HrEmployee extends Record {
    static _name = "hr.employee";
    static id = "id";

    /** @type {number} */
    id;
    /** @type {number} */
    company_id = fields.One("res.company");
    department_id = fields.One("hr.department");
    /** @type {string} */
    job_title;
    work_contact_id = fields.One("res.partner");
    user_id = fields.One("res.users");
    /** @type {string} */
    work_email;
    work_location_id = fields.One("hr.work.location");
    /** @type {string} */
    work_phone;
    /** @type {Boolean} */
    active;
}

HrEmployee.register();
