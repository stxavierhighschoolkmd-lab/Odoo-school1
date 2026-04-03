from datetime import datetime

from odoo import fields, models


class L10nPlAccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pl_bank_verification_status = fields.Selection(
        selection=[
            ('not_required', 'Not required'),  # Company or Partner not PL, amount under 15.000
            ('valid', 'Valid'),
            ('invalid', 'Invalid'),  # Bank account not referenced (in gov files) for partner's vat number
            ('failed', 'Verification Failed'),  # Missing datas inside odoo or unknown error while calling gov api
        ],
        string="Status",
        readonly=True,
        default='not_required',
        tracking=True,
    )
    l10n_pl_bank_verification_timestamp = fields.Datetime("Timestamp", readonly=True)
    l10n_pl_bank_verification_request_id = fields.Char("Correlation ID", readonly=True)
    l10n_pl_bank_verification_fail_reason = fields.Selection(
        selection=[
            ('incomplete_partner', 'Partner has no VAT or no bank account'),
            ('not_found_partner', 'Partner VAT not found in gov files'),
            ('unknown', 'An error occurred during check with Government API'),
        ],
        string='Failure Reason',
        readonly=True,
    )

    def action_post(self):
        # EXTENDS account.payment
        super().action_post()
        if self.company_id.country_code != 'PL':
            return
        PaymentRegister = self.env['account.payment.register']
        partners_to_check = self.env['res.partner']
        date = datetime.now().date()
        for pay in self:
            partner = pay.partner_id
            if not PaymentRegister._payment_need_check(partner, pay.payment_type, [pay.amount], pay.currency_id):
                continue
            if partner._is_vat_void(partner.vat) or not partner.bank_ids:
                pay.write({
                    'l10n_pl_bank_verification_status': 'failed',
                    'l10n_pl_bank_verification_timestamp': date,
                    'l10n_pl_bank_verification_fail_reason': 'incomplete_partner',
                })
                if partner.bank_ids:
                    PaymentRegister._write_status_on_partner_banks(partner.bank_ids, 'failed', 'incomplete_partner')
                continue
            partner_bank = pay.partner_bank_id or partner.bank_ids[0]
            if partner_bank._l10n_pl_status_at_date(date) not in ('unverified', 'failed'):
                pay._write_pl_bank_fiels_on_payment(partner_bank)
                continue
            partners_to_check |= partner

        PaymentRegister._build_endpoints_and_update_bank_accounts(partners_to_check, date)

        for pay in self:
            partner = pay.partner_id
            if not PaymentRegister._payment_need_check(partner, pay.payment_type, [pay.amount], pay.currency_id):
                continue

            partner_bank = pay.partner_bank_id
            if not partner_bank and partner.bank_ids:
                partner_bank = partner.bank_ids[0]
            if partner_bank:
                pay._write_pl_bank_fiels_on_payment(partner_bank)

    # ===============================
    # HELPERS
    # ===============================

    def _write_pl_bank_fiels_on_payment(self, partner_bank):
        self.ensure_one()
        self.write({
            'l10n_pl_bank_verification_status': partner_bank.l10n_pl_bank_verification_status,
            'l10n_pl_bank_verification_timestamp': partner_bank.l10n_pl_bank_verification_timestamp,
            'l10n_pl_bank_verification_request_id': partner_bank.l10n_pl_bank_verification_request_id,
            'l10n_pl_bank_verification_fail_reason': partner_bank.l10n_pl_bank_verification_fail_reason,
        })
