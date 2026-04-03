# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.addons.l10n_hu_edi.models.l10n_hu_edi_connection import format_timestamp
from odoo.addons.l10n_hu_edi_receive.models.l10n_hu_edi_connection import L10nHuEdiConnection


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def l10n_hu_edi_show_nav_sync_button(self, company_ids):
        return any(company.l10n_hu_edi_server_mode in ('test', 'production') for company in self.browse(company_ids))

    def l10n_hu_edi_receive_inbound_invoices(self, datetime_from, datetime_to):
        self.ensure_one()

        with L10nHuEdiConnection(self.env) as connection:
            credentials = self.sudo()._l10n_hu_edi_get_credentials_dict()
            digests = connection.query_invoice_digest(credentials, format_timestamp(datetime_from), format_timestamp(datetime_to))
            moves_vals = connection.query_invoice_data(credentials, digests)

        post_process_data_list = [move_vals.pop('post_process_data') for move_vals in moves_vals]
        moves = self.env['account.move'].create(moves_vals)
        self.env['account.move']._l10n_hu_edi_check_amounts_mismatch(zip(moves, post_process_data_list))
        return moves
