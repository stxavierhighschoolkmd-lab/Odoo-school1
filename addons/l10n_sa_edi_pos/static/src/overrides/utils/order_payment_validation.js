import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.dialog = this.pos.env.services.dialog;
    },

    async validateOrder(isForceValidate) {
        const order = this.order;
        // the isAnySettleLine() is only available if enterprise:pos_settle_due module is installed
        const settleLineCount = order.lines.filter((line) => line.isAnySettleLine?.()).length;
        if (settleLineCount && settleLineCount !== order.lines.length) {
            return this.dialog.add(AlertDialog, {
                title: _t("Settlement Error"),
                body: _t(
                    "Please remove the new order lines from the order to proceed with the settlement."
                ),
            });
        }
        await super.validateOrder(...arguments);
    },
});
