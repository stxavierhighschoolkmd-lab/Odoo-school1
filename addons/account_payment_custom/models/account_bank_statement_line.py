# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    @api.model_create_multi
    def create(self, vals_list):
        statement_lines = super().create(vals_list)

        wire_transfer_cron = self.env.ref(
            "account_payment_custom.cron_auto_confirm_paid_wire_transfer_txs", False
        )
        if wire_transfer_cron:
            wire_transfer_cron._trigger()

        return statement_lines

    def _cron_confirm_wire_transfer_transactions(self):
        """Confirm pending wire transfer payment transactions for which a matching bank statement is
         found.

        Note: This method is called by the `cron_auto_confirm_paid_wire_transfer_txs` cron.
        :return: None
        """
        tx_ids_by_company = self.env["payment.transaction"]._read_group(
            domain=[
                ("provider_code", "=", "custom"),
                ("payment_method_id.code", "=", "wire_transfer"),
                ("state", "=", "pending"),
            ],
            groupby=["company_id"],
            aggregates=["id:array_agg"],
        )
        for company, tx_ids in tx_ids_by_company:
            txs = self.env["payment.transaction"].browse(tx_ids)
            statement_lines = self.search([
                ("company_id", "=", company.id),
                ("payment_ref", "in", txs.mapped("reference")),
            ])
            if not statement_lines:
                continue

            lines_by_ref = statement_lines.grouped("payment_ref")
            for tx in txs:
                potential_lines = lines_by_ref.get(tx.reference, self)
                matching_line = potential_lines.filtered(
                    lambda line: (
                        (
                            line.partner_id == tx.partner_id.commercial_partner_id
                            or (
                                not line.partner_id
                                and line.partner_name == tx.partner_id.commercial_partner_id.name
                            )
                        )
                        and line.currency_id == tx.currency_id
                        and tx.currency_id.compare_amounts(line.amount, tx.amount) == 0
                    )
                )[:1]
                if matching_line:
                    tx._set_done()
