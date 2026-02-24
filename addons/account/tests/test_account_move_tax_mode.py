from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo import Command
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestDocumentTaxModeCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.tax_10_excl = cls.env['account.tax'].create({
            'name': '10% Tax (Excluded)',
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'amount': 10,
            'company_id': cls.env.company.id,
        })
        cls.tax_20_excl = cls.env['account.tax'].create({
            'name': '20% Tax (Excluded)',
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'amount': 20,
            'company_id': cls.env.company.id,
        })
        cls.test_product_a = cls.env['product.product'].create({
            'name':'Test Product A',
            'list_price':1000.0,
            'taxes_id':[Command.set([cls.tax_10_excl.id])],
            'company_id': cls.env.company.id,
        })

    def _test_tax_mode_change_with_product(self, document, line):
        self.assertEqual(document.document_tax_mode, 'tax_excluded')
        document_expected_values = [{
            'amount_tax': 100,
            'amount_untaxed': 1000,
            'amount_total': 1100,
        }]
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(document, document_expected_values)

        document.document_tax_mode = 'tax_included'
        self.assertEqual(line.price_unit, 1100)
        self.assertRecordValues(document, document_expected_values)

    def _test_tax_mode_change_manual_price_unit_with_product(self, document, line):
        self.assertEqual(document.document_tax_mode, 'tax_excluded')
        document_expected_values = [{
            'amount_tax': 100,
            'amount_untaxed': 1000,
            'amount_total': 1100,
        }]
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(document, document_expected_values)

        line.price_unit = 2000
        new_document_expected_values_tax_excl = [{
            'amount_tax': 200,
            'amount_untaxed': 2000,
            'amount_total': 2200,
        }]
        self.assertRecordValues(document, new_document_expected_values_tax_excl)

        # When the price_unit is manually changed it will remain the same when the tax mode is changed,
        # while the total amounts will be adapted.
        new_document_expected_values_tax_incl = [{
            'amount_tax': 181.82,
            'amount_untaxed': 1818.18,
            'amount_total': 2000,
        }]
        document.document_tax_mode = 'tax_included'
        self.assertEqual(line.price_unit, 2000)
        self.assertRecordValues(document, new_document_expected_values_tax_incl)

    def _test_tax_mode_change_add_tax_with_product(self, document, line):
        self.assertEqual(document.document_tax_mode, 'tax_excluded')
        document_expected_values = [{
            'amount_tax': 100,
            'amount_untaxed': 1000,
            'amount_total': 1100,
        }]
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(document, document_expected_values)
        line.tax_ids |= self.tax_20_excl

        new_document_expected_values = [{
            'amount_tax': 300,
            'amount_untaxed': 1000,
            'amount_total': 1300,
        }]
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(document, new_document_expected_values)

        document.document_tax_mode = 'tax_included'
        self.assertEqual(line.price_unit, 1300)
        self.assertRecordValues(document, new_document_expected_values)


@tagged('post_install', '-at_install')
class TestAccountMoveTaxMode(TestDocumentTaxModeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice_one_line_with_product = cls._create_invoice_one_line(
            product_id=cls.test_product_a,
            company_id=cls.env.company.id,
        )
        cls.invoice_one_line_without_product = cls._create_invoice_one_line(
            price_unit=1000,
            tax_ids=cls.tax_10_excl,
        )

    def test_account_move_tax_mode_change_with_product(self):
        invoice = self.invoice_one_line_with_product
        self._test_tax_mode_change_with_product(invoice, invoice.invoice_line_ids)

    def test_account_move_tax_mode_change_manual_price_unit_with_product(self):
        invoice = self.invoice_one_line_with_product
        self._test_tax_mode_change_manual_price_unit_with_product(invoice, invoice.invoice_line_ids)

    def test_account_move_tax_mode_change_add_tax_with_product(self):
        invoice = self.invoice_one_line_with_product
        self._test_tax_mode_change_add_tax_with_product(invoice, invoice.invoice_line_ids)

    def _test_account_move_tax_mode_change_add_tax_without_product(self):
        invoice = self.invoice_one_line_without_product
        self.assertEqual(invoice.document_tax_mode, 'tax_excluded')
        invoice_expected_values = [{
            'amount_tax': 100,
            'amount_untaxed': 1000,
            'amount_total': 1100,
        }]
        line = invoice.invoice_line_ids
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(invoice, invoice_expected_values)

        line.tax_ids |= self.tax_20_excl
        self.assertEqual(line.price_unit, 1000)
        new_invoice_expected_values_tax_excl = [{
            'amount_tax': 300,
            'amount_untaxed': 1000,
            'amount_total': 1300,
        }]
        self.assertRecordValues(invoice, new_invoice_expected_values_tax_excl)

        new_invoice_expected_values_tax_incl = [{
            'amount_tax': 230.77,
            'amount_untaxed': 769.23,
            'amount_total': 1000,
        }]
        invoice.document_tax_mode = 'tax_included'
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(invoice, new_invoice_expected_values_tax_incl)

    def test_tax_mode_change_without_product(self):
        invoice = self.invoice_one_line_without_product
        self.assertEqual(invoice.document_tax_mode, 'tax_excluded')
        invoice_expected_values_before_tax_mode_change = [{
            'amount_tax': 100,
            'amount_untaxed': 1000,
            'amount_total': 1100,
        }]
        line = invoice.invoice_line_ids
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(invoice, invoice_expected_values_before_tax_mode_change)

        invoice_expected_values_after_tax_mode_change = [{
            'amount_tax': 90.91,
            'amount_untaxed': 909.09,
            'amount_total': 1000,
        }]
        invoice.document_tax_mode = 'tax_included'
        self.assertEqual(line.price_unit, 1000)
        self.assertRecordValues(invoice, invoice_expected_values_after_tax_mode_change)
