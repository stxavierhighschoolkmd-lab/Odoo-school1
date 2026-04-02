import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

const cogMenuRegistry = registry.category("cogMenu");

const BUTTON_CONFIG = {
    fetch: {
        action: "button_fetch_in_einvoices",
        field: "show_fetch_in_einvoices_button",
        journalType: "purchase",
        label: _t("Fetch e-Invoices"),
    },
    refresh: {
        action: "button_refresh_out_einvoices_status",
        field: "show_refresh_out_einvoices_status_button",
        journalType: "sale",
        label: _t("Refresh e-Invoices Status"),
    },
};

function getButtonConfig(searchModel) {
    const { globalContext, context } = searchModel;
    if (globalContext.show_fetch_in_einvoices_button) {
        return BUTTON_CONFIG.fetch;
    }
    if (globalContext.show_refresh_out_einvoices_status_button) {
        return BUTTON_CONFIG.refresh;
    }

    if ((context.default_move_type || "").startsWith("in_")) {
        return BUTTON_CONFIG.fetch;
    }
    if ((context.default_move_type || "").startsWith("out_")) {
        return BUTTON_CONFIG.refresh;
    }

    return null;
}

async function getRelevantJournalIds(searchModel) {
    const journalId = searchModel.globalContext.default_journal_id;
    if (journalId) {
        return [journalId];
    }

    const buttonConfig = getButtonConfig(searchModel);
    if (!buttonConfig) {
        return [];
    }

    // The button-visibility fields are computed/unstored, so filter after reading.
    const journals = await searchModel.orm.searchRead(
        "account.journal",
        [["type", "=", buttonConfig.journalType]],
        ["id", buttonConfig.field],
        { context: searchModel.context }
    );
    return journals.filter((j) => j[buttonConfig.field]).map((j) => j.id);
}

export class FetchEInvoices extends Component {
    static template = "account.FetchEInvoices";
    static props = {};
    static components = { DropdownItem };

    setup() {
        super.setup();
        this.action = useService("action");
    }

    get buttonAction() {
        return getButtonConfig(this.env.searchModel)?.action;
    }

    get buttonLabel() {
        return getButtonConfig(this.env.searchModel)?.label;
    }

    async fetchEInvoices() {
        const journalIds = await getRelevantJournalIds(this.env.searchModel);
        if (!journalIds.length || !this.buttonAction) {
            return;
        }

        await this.action.doActionButton({
            type: "object",
            resIds: journalIds,
            name: this.buttonAction,
            resModel: "account.journal",
            onClose: () => window.location.reload(),
        });
    }
}

export const fetchEInvoicesActionMenu = {
    Component: FetchEInvoices,
    groupNumber: ACTIONS_GROUP_NUMBER,
    isDisplayed: async ({ searchModel }) => {
        if (searchModel.resModel !== "account.move") {
            return false;
        }

        return Boolean((await getRelevantJournalIds(searchModel)).length);
    },
};

cogMenuRegistry.add("account-fetch-e-invoices", fetchEInvoicesActionMenu, { sequence: 11 });
