from odoo.addons.account.tests.test_account_move_tax_mode import TestDocumentTaxModeCommon
from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestSaleOrderTaxMode(TestDocumentTaxModeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.tax_10_excl_purchase = cls.env['account.tax'].create({
            'name': '10% Tax (Excluded)',
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'amount': 10,
            'company_id': cls.env.company.id,
        })
        cls.test_product_a.update({
            'standard_price': 1000,
            'supplier_taxes_id': cls.tax_10_excl_purchase.id,
        })
        cls.purchase_order_one_line_with_product = cls.env['purchase.order'].create([{
            'partner_id': cls.partner_a.id,
            'order_line': [
                Command.create({'product_id': cls.test_product_a.id}),
            ],
        }])

    def test_purchase_order_tax_mode_change_with_product(self):
        purchase_order = self.purchase_order_one_line_with_product
        self._test_tax_mode_change_with_product(purchase_order, purchase_order.order_line)

    def test_purchase_order_tax_mode_change_manual_price_unit_with_product(self):
        purchase_order = self.purchase_order_one_line_with_product
        self._test_tax_mode_change_manual_price_unit_with_product(purchase_order, purchase_order.order_line)
    
    def test_account_move_tax_mode_change_add_tax_with_product(self):
        purchase_order = self.invoice_one_line_with_product
        self._test_tax_mode_change_add_tax_with_product(purchase_order, purchase_order.order_line)
