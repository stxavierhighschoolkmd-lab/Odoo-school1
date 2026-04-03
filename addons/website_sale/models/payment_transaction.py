# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _send_invoice(self):
        """Override of `sale` to archive guest contacts."""
<<<<<<< 400b7b20b57ada0d9b9863948fef6392de590aed
        confirmed_orders = super()._check_amount_and_confirm_order()
        confirmed_orders.filtered("website_id")._archive_partner_if_no_user()
        return confirmed_orders
||||||| a16bc72c26c0b597673746e8c751662236a5bb65
        confirmed_orders = super()._check_amount_and_confirm_order()
        confirmed_orders.filtered('website_id')._archive_partner_if_no_user()
        return confirmed_orders
=======
        super()._send_invoice()
        self.sale_order_ids.filtered(
            lambda so: so.state == "sale" and so.website_id
        )._archive_partner_if_no_user()
>>>>>>> 55fdfb67590d5b71d25e59c9790675b5e6683e65
