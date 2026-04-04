# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale.tests.common import TestSaleCommon


@tagged('post_install', '-at_install')
class TestSaleEarlyPaymentDiscount(TestSaleCommon):

    def test_early_payment_discount(self):
        """Ensure untaxed amount in sale order is correct when early payment discount
        is applied on tax-included price."""
        tax = self.env['account.tax'].create({
            'name': 'Tax 21% included',
            'amount': 21,
            'price_include_override': 'tax_included',
            'type_tax_use': 'sale',
        })

        self.product.list_price = 7.50
        self.product.taxes_id = [Command.set(tax.ids)]

        self.pay_terms_a.early_discount = True
        self.pay_terms_a.early_pay_discount_computation = 'mixed'

        so = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'payment_term_id': self.pay_terms_a.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 7.50,
                'tax_id': [Command.set(tax.ids)],
            })],
        })

        self.assertAlmostEqual(so.amount_untaxed, 6.20, places=2)
