# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBaseDocumentLayout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_company_vat_appears_in_documents(self):
        self.env.company.vat = 'BE987654321'
        rendered = self.env['ir.ui.view']._render_template(
            'web.company_address_list',
            {
                'company': self.env.company,
                'forced_vat': False,
            },
        )
        self.assertIn('BE987654321', rendered)
