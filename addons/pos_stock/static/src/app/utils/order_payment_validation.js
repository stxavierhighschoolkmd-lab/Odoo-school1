import { patch } from "@web/core/utils/patch";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

patch(OrderPaymentValidation.prototype, {
    shouldAskForPartner() {
        return (
            super.shouldAskForPartner() || (this.order.shipping_date && !this.order.getPartner())
        );
    },
});
