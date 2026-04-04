# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account.tests.test_invoice_taxes import TestInvoiceTaxes
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class L10nMXTestTaxRounding(TestInvoiceTaxes):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('mx')
    def setUpClass(cls):
        super().setUpClass()

    def test_tax_rounding_method_mx(self):
        tax_53 = self.percent_tax(53.0, price_include_override='tax_included', include_base_amount=True)
        tax_16 = self.percent_tax(16.0, price_include_override='tax_included')
        invoice = self._create_invoice(
            [(330.00, tax_53 | tax_16)],
        )
        invoice.action_post()

        self.assertEqual(invoice.amount_total, 330.00)
