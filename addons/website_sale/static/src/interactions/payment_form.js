import { patch } from '@web/core/utils/patch';
import { redirect } from '@web/core/utils/urls';

import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {

    /**
     * Create an event listener for the payment submit buttons located outside the payment form.
     *
     * Buttons that are inside the payment form are ignored as they are already handled by the
     * payment form.
     *
     * @override
     */
    setup() {
        super.setup();
        const submitButtons = document.querySelectorAll('button[name="o_payment_submit_button"]');
        const boundSubmitForm = this.submitForm.bind(this);
        submitButtons.forEach(submitButton => {
            if (!this.el.contains(submitButton)) { // The button is outside the payment form.
                submitButton.addEventListener('click', boundSubmitForm);
                this.registerCleanup(
                    () => submitButton.removeEventListener('click', boundSubmitForm)
                );
            }
        });
    },

    /**
     * Redirect the user if the checkout progress wasn't complete at the transaction creation.
     * @override
     */
    _handlePaymentProcessingError(processingValues) {
        if (processingValues.redirect) {
            redirect(processingValues.redirect);
        } else {
            super._handlePaymentProcessingError(processingValues);
        }
    },
});
