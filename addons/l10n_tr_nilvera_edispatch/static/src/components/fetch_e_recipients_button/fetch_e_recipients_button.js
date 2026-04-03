import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class FetchERecipientsButton extends Component {
    static template = "l10n_tr_nilvera_edispatch.fetch_e_recipients_button";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    runAction() {
        this.action.doAction("stock_picking.button_l10n_tr_nilvera_fetch_edispatch_purchase_attachments");
    }
}

export const FetchERecipientsButtonActionMenu = {
    Component: FetchERecipientsButton,
    isDisplayed: ({ config, searchModel}) =>
        searchModel.resModel === "stock.picking" &&
        config.viewSubType === 'vpicktree' &&
        config.company_id.l10n_tr_nilvera_api_key,
};

registry.category("cogMenu").add("stock-picking-fetch-erecipients", FetchERecipientsButtonActionMenu);
