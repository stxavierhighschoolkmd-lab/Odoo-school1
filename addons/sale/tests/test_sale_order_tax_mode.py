from odoo.addons.account.tests.test_account_move_tax_mode import TestDocumentTaxModeCommon
from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestSaleOrderTaxMode(TestDocumentTaxModeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('sales_team.group_sale_salesman')
        cls.sale_order_one_line_with_product = cls._create_sale_order_one_line(
            product_id=cls.test_product_a,
            company_id=cls.env.company.id,
            confirm=False,
        )

    def test_sale_order_tax_mode_change_with_product(self):
        sale_order = self.sale_order_one_line_with_product
        self._test_tax_mode_change_with_product(sale_order, sale_order.order_line)

    def test_sale_order_tax_mode_change_manual_price_unit_with_product(self):
        sale_order = self.sale_order_one_line_with_product
        self._test_tax_mode_change_manual_price_unit_with_product(sale_order, sale_order.order_line)
    
    def test_account_move_tax_mode_change_add_tax_with_product(self):
        sale_order = self.sale_order_one_line_with_product
        self._test_tax_mode_change_add_tax_with_product(sale_order, sale_order.order_line)
