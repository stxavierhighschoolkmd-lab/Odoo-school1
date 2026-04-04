import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class PaymentPostProcessing extends Interaction {
    static selector = "div[name='o_payment_status']";

    setup() {
        // Create a bus listener to trigger post processing
        this.notificationType = "payment.notify_transaction_processed";
        this.notificationChannel = this.el.dataset.notificationChannel;
        this.busService = this.services.bus_service;
        this.busService.addChannel(this.notificationChannel);
        this.triggerPostProcessingBind = this.triggerPostProcessing.bind(this);
        this.busService.subscribe(this.notificationType, this.triggerPostProcessingBind);

        // Call the postprocessing rpc in case the notification was received before creating the
        // channel.
        rpc("/payment/post_process", { csrf_token: odoo.csrf_token })
            .then((postProcessingData) => {
                debugger;
                if (postProcessingData.is_post_processed)
                    window.location = postProcessingData.landing_route;
            });

        // Redirect automatically after 5 seconds
        this.redirectTimeout = this.waitForTimeout(() => {
            const landingRoute = this.el.dataset.landingRoute;
            if (landingRoute) {
                window.location = landingRoute;
            }
        }, 5000);

        // Make sure bus listener is disposed properly when interaction is destroyed
        this.registerCleanup(() => {
            this.busService.unsubscribe(this.notificationType, this.triggerPostProcessingBind);
            this.busService.deleteChannel(this.notificationChannel);
        });
    }

    triggerPostProcessing() {
        clearTimeout(this.redirectTimeout);
        rpc("/payment/post_process", { csrf_token: odoo.csrf_token })
            .then((postProcessingData) => {
                window.location = postProcessingData.landing_route;
            });
    }
}

registry
    .category("public.interactions")
    .add("payment.payment_post_processing", PaymentPostProcessing);
