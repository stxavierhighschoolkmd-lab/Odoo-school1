# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    @api.model
    def _setup_payment_method(self, code):
        if code == "wire_transfer" and not self._get_provider_payment_method(code):
            self.env["account.payment.method"].sudo().create({
                "name": "Wire Transfer",
                "code": code,
                "payment_type": "inbound",
            })
        else:
            super()._setup_payment_method(code)
