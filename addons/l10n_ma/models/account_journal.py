from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def _update_payment_method_lines(self, payment_type):
        bank_journals = self.filtered(lambda j: j.type == "bank" and j.company_id.chart_template == "ma")
        if not bank_journals:
            return

        account_xmlid = 'account_journal_payment_debit_account_id' if payment_type == 'inbound' else 'account_journal_payment_credit_account_id'
        lines_to_update = bank_journals[f"{payment_type}_payment_method_line_ids"].filtered(
            lambda l: l.payment_method_id.code == 'manual'
        )
        if not lines_to_update:
            return

        account_company_map = {
            company: self.env['account.chart.template']
                .with_company(company)
                .ref(account_xmlid, raise_if_not_found=False)
            for company in lines_to_update.mapped('company_id')
        }
        for company, lines in lines_to_update.grouped('company_id').items():
            if account := account_company_map[company]:
                lines.payment_account_id = account

    def _compute_inbound_payment_method_line_ids(self):
        super()._compute_inbound_payment_method_line_ids()
        self._update_payment_method_lines('inbound')

    def _compute_outbound_payment_method_line_ids(self):
        super()._compute_outbound_payment_method_line_ids()
        self._update_payment_method_lines('outbound')
