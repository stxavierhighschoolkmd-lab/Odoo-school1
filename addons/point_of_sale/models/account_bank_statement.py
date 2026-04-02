# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    pos_session_id = fields.Many2one('pos.session', string="Session", copy=False, index='btree_not_null')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        journal_ids = records.journal_id.ids

        # Update the cash register balance when bank statement lines are created for the POS session's cash
        # journal in the opening control state to ensure accurate starting balances.
        if journal_ids and (sessions := self.env['pos.session'].search([
            ('cash_journal_id', 'in', journal_ids),
            ('state', '=', 'opening_control'),
        ])):
            for session in sessions:
                session.cash_register_balance_start = session.cash_journal_id.current_statement_balance
                session.config_id._notify(('SESSION_UPDATED', {'session_id': session.id}))

        return records
