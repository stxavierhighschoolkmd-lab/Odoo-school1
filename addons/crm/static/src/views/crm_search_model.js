import { SearchModel } from "@web/search/search_model";
import { onWillStart } from "@odoo/owl";

export class CrmSearchModel extends SearchModel {
    setup() {
        super.setup(...arguments);

        onWillStart(async () => {
            // Retrieve user accessible teams for the CRM Team Switcher.
            this.accessibleCrmTeams = await this.orm
                .cache({
                    // Using update "once" (default) to only update accessible teams on page reload.
                    type: "disk",
                    callback: (result, hasChanged) => {
                        if (hasChanged) {
                            this.accessibleCrmTeams = result;
                        }
                    },
                })
                .searchRead("crm.team", [], ["id", "name"], { order: "name asc" });
        });
    }
}
