# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    pos_payment_method_id = fields.Many2one(
        'pos.payment.method',
        string="Payment Method",
        compute='_compute_pos_payment_method',
        store=True)

    @api.depends('pos_payment_method_id.type')
    def _compute_pos_payment_method(self):
        for statement in self:
            statement.pos_payment_method_id = self.env['pos.payment.method'].search([
                ('account_bank_statement_id', '=', statement.id),
            ], limit=1)
