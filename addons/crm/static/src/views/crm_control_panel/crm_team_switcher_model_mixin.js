import { browser } from "@web/core/browser/browser";
import { Domain } from "@web/core/domain";

/**
 * Mixin to process the CRM Team Switcher selected team in the search domain.
 */
export const CrmTeamSwitcherModelMixin = (T) => class CrmTeamSwitcherModelMixin extends T {
    _processSearchDomain(params, domain) {
        const selectedTeamId = JSON.parse(browser.localStorage.getItem("selectedTeamId"));
        if (!selectedTeamId) {
            return domain;
        }
        if (!this.env.searchModel.accessibleCrmTeams?.map((t) => t.id).includes(selectedTeamId)) {
            // Fallback on "All" teams if the selected team is not accessible.
            browser.localStorage.removeItem("selectedTeamId");
            return domain;
        }
        // Update search domain to get the selected team crm.lead records,
        // update context to get the selected team stages (on read group)
        // and set it as the default team on lead records creation.
        params.context = {
            ...params.context,
            has_team_switcher_selection: true,
            default_team_id: selectedTeamId,
        };
        return Domain.and([
            domain,
            [['team_id', '=', selectedTeamId]],
        ]).toList();
    }
};
