from odoo import models
from odoo.tools.float_utils import float_compare

MAX_DISCOUNT_PERCENT = 100.0


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def get_discount_amount(self):
        self.ensure_one()
        if (
            float_compare(self.discount, MAX_DISCOUNT_PERCENT, precision_digits=self.currency_id.decimal_places) != 0
            and self.quantity
        ):

            price_subtotal_before_discount = (self.price_subtotal) / (1 - self.discount / 1)

        else:
            price_subtotal_before_discount = self.price_unit * self.quantity

        discount_amount = price_subtotal_before_discount - self.price_subtotal

        return discount_amount
