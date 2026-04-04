from odoo.addons.l10n_in.tests.common import L10nInTestInvoicingCommon
from odoo.tests import Form, tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestL10nInStandardFlow(L10nInTestInvoicingCommon):
    """ Tests involving standard flows that are not related to PoS but may be affected by it """

    def test_open_payment_register(self):
        self.env['res.partner.bank'].create({
            'acc_number': '0144748555',
            'partner_id': self.partner_a.id,
            'allow_out_payment': True,
        })
        bill = self._create_invoice('in_invoice', post=True)
        wizard = Form(self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=bill.ids))
        self.assertTrue(wizard)
