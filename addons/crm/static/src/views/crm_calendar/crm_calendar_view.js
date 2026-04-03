import { calendarView } from "@web/views/calendar/calendar_view";
import { CrmCalendarModel } from "@crm/views/crm_calendar/crm_calendar_model";
import { CrmControlPanel } from "@crm/views/crm_control_panel/crm_control_panel";
import { CrmSearchModel } from "@crm/views/crm_search_model";
import { registry } from "@web/core/registry";

export const crmCalendarView = {
    ...calendarView,
    ControlPanel: CrmControlPanel,
    Model: CrmCalendarModel,
    SearchModel: CrmSearchModel,
};
registry.category("views").add("crm_calendar", crmCalendarView);
