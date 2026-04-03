
from lxml import etree

from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.l10n_tr_nilvera_einvoice.tests.test_xml_ubl_tr_common import (
    TestUBLTRCommon,
)


@tagged("post_install_l10n", "post_install", "-at_install")
class TestUBLTRXMLDecode(TestUBLTRCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.account_edi_xml_ubl_tr = cls.env["account.edi.xml.ubl.tr"]
        cls.invoice_basic_sale_einvoice_tree = cls._load_xml_tree("l10n_tr_nilvera_einvoice/tests/expected_xmls/invoice_basic_sale_einvoice.xml")

    # =====================================================================
    # Helper: Load XML once
    # =====================================================================
    @classmethod
    def _load_xml_tree(cls, path):
        with file_open(path, "rb") as xml_file:
            return etree.fromstring(xml_file.read())

    def test_discounts_are_properly_added_to_invoice_lines(self):
        invoice = self.env["account.move"].create({"move_type": 'out_invoice'})
        self.account_edi_xml_ubl_tr._import_fill_invoice(
            invoice, self.invoice_basic_sale_einvoice_tree, 1,
        )

        product_line_id = invoice.invoice_line_ids.filtered(lambda l: l.name == 'product_a')[:1]
        global_discount_line_ids = invoice.invoice_line_ids.filtered(lambda l: l.name == 'Discount')[:1]

        self.assertEqual(
            product_line_id.discount,
            12.0,
            "The discount on line was not correctly imported from the XML.",
        )
        self.assertFalse(global_discount_line_ids, "Nilvera moves should not have any global discount line")
