from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _compute_qr_code(self):
        in_pay = self.filtered(lambda pay: pay.company_id.country_code == 'IN')
        in_pay.qr_code = False
        super(AccountPaymentRegister, self - in_pay)._compute_qr_code()
