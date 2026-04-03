import { ControlPanel } from "@web/search/control_panel/control_panel";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";

export class CrmControlPanel extends ControlPanel {
    static template = "crm.ControlPanel";

    setup() {
        super.setup();
        this.accessibleTeams = this.env.searchModel.accessibleCrmTeams;
        this.selectedTeamIdKey = "selectedTeamId";
        this.state.selectedTeamId = JSON.parse(browser.localStorage.getItem(this.selectedTeamIdKey));
    }

    get allTeamsLabel() {
        return _t("All");
    }

    get selectedTeamName() {
        const selectedTeam = this.accessibleTeams.find((team) => team.id === this.state.selectedTeamId);
        return selectedTeam?.name || this.allTeamsLabel;
    }

    get showTeamSwitcher() {
        return this.accessibleTeams.length > 1;
    }

    /**
     * Select the team, save it in local storage and update the search model.
     * The selected team stages and "crm.lead" records are displayed,
     * and the team is set as default on lead creation.
     */
    onClickTeam(teamId) {
        if (this.state.selectedTeamId === teamId) {
            return;
        }
        this.state.selectedTeamId = teamId;
        if (this.state.selectedTeamId) {
            browser.localStorage.setItem(this.selectedTeamIdKey, this.state.selectedTeamId);
        } else {
            // "All" selected: remove the local storage key
            // to prevent restricting the search domain.
            browser.localStorage.removeItem(this.selectedTeamIdKey);
        }
        this.env.searchModel.search();
    }
}
