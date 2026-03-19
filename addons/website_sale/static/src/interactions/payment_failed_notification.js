import { browser } from "@web/core/browser/browser";
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class PaymentFailedNotification extends Interaction {
    static selector = ".o_cart_products_table";
    setup() {
        // Add a notification service to send notification when there"s a payment error.
        const errorMessage = new URLSearchParams(window.location.search).get("payment_error");
        if (errorMessage) {
            this.notification = this.services.notification;
            this.notification.add(errorMessage, { type: "danger", sticky: true });
        }
    }
}

registry
    .category("public.interactions")
    .add("website_sale.payment_failed_notification", PaymentFailedNotification);
