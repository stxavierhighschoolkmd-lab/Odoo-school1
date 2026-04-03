import { user } from "@web/core/user";

export async function userHasEmployeeInCurrentCompany(orm) {
    const [read_user] = await orm.read("res.users", [user.userId], ["employee_ids","employee_id"]);
    return (await orm.searchCount("hr.employee", [["id", "in", [...read_user.employee_ids, read_user.employee_id[0]]], ["company_id", "=", user.activeCompany.id]])) !== 0;
}
