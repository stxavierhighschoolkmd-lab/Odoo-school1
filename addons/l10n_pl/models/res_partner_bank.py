from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    l10n_pl_bank_verification_status = fields.Selection(
        selection=[
            ('not_required', 'Not required'),  # Company or Partner not PL, amount under 15.000
            ('valid', 'Valid'),
            ('invalid', 'Invalid'),  # Bank account not referenced (in gov files) for partner's vat number
            ('failed', 'Verification Failed'),  # Missing datas inside odoo or unknown error while calling gov api
        ],
        string="Bank Verification Status",
        readonly=True,
        default='not_required',
        tracking=True,
    )
    l10n_pl_bank_verification_timestamp = fields.Datetime(readonly=True, string="Bank Verification Timestamp")
    l10n_pl_bank_verification_request_id = fields.Char(readonly=True, string="Bank Verification Correlation ID")
    l10n_pl_bank_verification_fail_reason = fields.Selection(
        selection=[
            ('incomplete_partner', 'Partner has no VAT or no bank account'),
            ('not_found_partner', 'Partner VAT not found in gov files'),
            ('unknown', 'An error occurred during check with Government API'),
        ],
        string='Failure Reason',
        readonly=True,
    )

    def _l10n_pl_status_at_date(self, date):
        self.ensure_one()
        if self.l10n_pl_bank_verification_timestamp and self.l10n_pl_bank_verification_timestamp.date() == date:
            return self.l10n_pl_bank_verification_status
        return 'unverified'
