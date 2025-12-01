from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _l10n_es_is_edi_sii_applicable(self, move):
        return move.l10n_es_edi_is_required and move.l10n_es_edi_sii_state != 'sent'

    def _get_all_extra_edis(self) -> dict:
        # EXTENDS 'account'
        res = super()._get_all_extra_edis()
        res.update({
            'es_edi_sii': {
                'label': self.env._("Send to SII"),
                'is_applicable': self._l10n_es_is_edi_sii_applicable,
                'help': self.env._("Send the e-invoice data to SII"),
            }
        })
        return res

    # -------------------------------------------------------------------------
    # SENDING METHODS
    # -------------------------------------------------------------------------

    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        super()._call_web_service_before_invoice_pdf_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            if 'es_edi_sii' in invoice_data['extra_edis']:
                invoice._send_l10n_es_sii_document()
                if invoice.l10n_es_edi_sii_error:
                    invoice_data['error'] = {
                        'error_title': self.env._("Error while sending the invoice to SII"),
                        'errors': [invoice.l10n_es_edi_sii_error],
                    }
                if self._can_commit():
                    self.env.cr.commit()
