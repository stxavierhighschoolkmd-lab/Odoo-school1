# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import fields, models, SUPERUSER_ID
from odoo.exceptions import UserError


class L10nVnEdiViettelStockSendWizard(models.TransientModel):
    _name = 'l10n_vn_edi_viettel_stock.send_wizard'
    _description = 'Send Transfer Note to SInvoice'

    picking_id = fields.Many2one(comodel_name='stock.picking', string='Transfer', required=True)
    send_to_sinvoice = fields.Boolean(string='Send to SInvoice', default=True)

    def action_send(self):
        self.ensure_one()
        if not self.send_to_sinvoice:
            return

        picking = self.picking_id
        errors = picking._l10n_vn_edi_check_configuration()
        if errors:
            raise UserError('\n'.join(errors))

        # Generate the transfer note JSON payload
        json_data = picking._l10n_vn_edi_generate_transfer_note_json()

        # Store the JSON file as an attachment on the picking
        self.env['ir.attachment'].with_user(SUPERUSER_ID).create({
            'name': f'{picking.name.replace("/", "_")}_sinvoice.json',
            'raw': json.dumps(json_data, ensure_ascii=False).encode('utf-8'),
            'mimetype': 'application/json',
            'res_model': picking._name,
            'res_id': picking.id,
            'res_field': 'l10n_vn_edi_sinvoice_file',
        })
        picking.invalidate_recordset(fnames=[
            'l10n_vn_edi_sinvoice_file_id',
            'l10n_vn_edi_sinvoice_file',
        ])

        # Send to SInvoice
        errors = picking._l10n_vn_edi_send_transfer_note(json_data)
        if errors:
            raise UserError('\n'.join(errors))

        # Fetch the XML and PDF files from SInvoice
        file_errors = picking._l10n_vn_edi_fetch_files()
        if file_errors:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': file_errors['error_title'],
                    'message': '\n'.join(file_errors['errors']),
                    'type': 'warning',
                    'sticky': True,
                },
            }
