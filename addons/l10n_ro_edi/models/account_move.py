import requests

from odoo import models, fields, _, api, modules, tools


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_ro_edi_document_ids = fields.One2many(
        comodel_name='l10n_ro_edi.document',
        inverse_name='invoice_id',
    )
    l10n_ro_edi_state = fields.Selection(
        selection=[
            ('invoice_sent', 'Sent'),
            ('invoice_validated', 'Validated'),
        ],
        string='E-Factura Status',
        compute='_compute_l10n_ro_edi_state',
        store=True,
        help="""- Sent: Successfully sent to the SPV, waiting for validation
                - Validated: Sent & validated by the SPV
                - Error: Sending error or validation error from the SPV""",
    )
    l10n_ro_edi_attachment_id = fields.Many2one(comodel_name='ir.attachment')
    l10n_ro_edi_index = fields.Char(string='E-Factura Index', readonly=True, copy=False)

    ################################################################################
    # Compute Methods
    ################################################################################

    @api.depends('l10n_ro_edi_document_ids', 'l10n_ro_edi_document_ids.state')
    def _compute_l10n_ro_edi_state(self):
        self.l10n_ro_edi_state = False
        for move in self:
            for document in move.l10n_ro_edi_document_ids.sorted():
                if document.state in ('invoice_sent', 'invoice_validated'):
                    move.l10n_ro_edi_state = document.state
                    break

    @api.depends('l10n_ro_edi_state')
    def _compute_show_reset_to_draft_button(self):
        """ Prevent user to reset move to draft when there's an
            active sending document or a successful response has been received """
        # EXTENDS 'account'
        super()._compute_show_reset_to_draft_button()
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and move.l10n_ro_edi_state in ('invoice_sent', 'invoice_validated') and move.l10n_ro_edi_document_ids.sorted()[:1].state != 'invoice_sending_failed':
                move.show_reset_to_draft_button = False

    ################################################################################
    # Romanian Document Shorthands & Helpers
    ################################################################################

    def _l10n_ro_edi_create_attachment_values(self, raw, res_model=None, res_id=None):
        """ Shorthand for creating the attachment_id values on the invoice's document """
        self.ensure_one()
        res_model = res_model or self._name
        res_id = res_id or self.id
        name = self.name or ""
        return {
            'name': f"ciusro_signature_{name.replace('/', '_')}.xml",
            'res_model': res_model,
            'res_id': res_id,
            'raw': raw,
            'type': 'binary',
            'mimetype': 'application/xml',
        }

    def _l10n_ro_edi_create_document_invoice_sent(self, values: dict):
        """ Shorthand for creating a ``l10n_ro_edi.document`` of state ``invoice_sent``.

        :param values: dictionary of {'key_loading': <str>, 'attachment_raw': <bytes>}
        :return: ``l10n_ro_edi.document`` object """
        self.ensure_one()
        document = self.env['l10n_ro_edi.document'].sudo().create({
            'invoice_id': self.id,
            'state': 'invoice_sent',
            'key_loading': values['key_loading'],
        })
        attachment_values = self._l10n_ro_edi_create_attachment_values(
            raw=values['attachment_raw'],
            res_model=document._name,
            res_id=document.id,
        )
        document.attachment_id = self.env['ir.attachment'].sudo().create(attachment_values)
        return document

    def _l10n_ro_edi_create_document_invoice_sending_failed(self, values: dict):
        """ Shorthand for creating a ``l10n_ro_edi.document`` of state ``invoice_sending_failed``.
        The ``attachment_raw`` and ``key_loading`` dictionary values is optional in case the error is from pre_send.

        :param values: dictionary of {
            'error': <str>,
            'key_loading': <optional str>,
            'attachment_raw': <optional str>,
        }
        :return: ``l10n_ro_edi.document`` object """
        self.ensure_one()
        document = self.env['l10n_ro_edi.document'].sudo().create({
            'invoice_id': self.id,
            'state': 'invoice_sending_failed',
            'message': values['error'],
        })
        if values.get('key_loading'):
            document.key_loading = values['key_loading']
        if values.get('attachment_raw'):
            attachment_values = self._l10n_ro_edi_create_attachment_values(
                raw=values['attachment_raw'],
                res_model=document._name,
                res_id=document.id,
            )
            document.attachment_id = self.env['ir.attachment'].sudo().create(attachment_values)
        return document

    def _l10n_ro_edi_create_document_invoice_validated(self, values: dict):
        """ Shorthand for creating a ``l10n_ro_edi.document`` of state `invoice_validated`.
        The created attachment are saved on both the document and on the invoice.

        :param values: dictionary containing 'key_loading', 'key_signature', 'key_certificate', and 'attachment_raw'
        :return: ``l10n_ro_edi.document`` object """
        self.ensure_one()
        document = self.env['l10n_ro_edi.document'].sudo().create({
            'invoice_id': self.id,
            'state': 'invoice_validated',
            'key_loading': values['key_loading'],
            'key_signature': values['key_signature'],
            'key_certificate': values['key_certificate'],
        })
        attachment = self.env['ir.attachment'].sudo().create(self._l10n_ro_edi_create_attachment_values(values['attachment_raw']))
        document.attachment_id = self.l10n_ro_edi_attachment_id = attachment
        return document

    def _l10n_ro_edi_update_document_invoice_sending_failed(self, document, values: dict):
        """ Shorthand for updating a ``l10n_ro_edi.document`` to state ``invoice_sending_failed``.

        :param document: ``l10n_ro_edi.document`` recordset to update
        :param values: dictionary of {
            'error': <str>,
            'key_loading': <optional str>,
            'attachment_raw': <optional str>,
        }
        :return: ``l10n_ro_edi.document`` object """
        self.ensure_one()
        write_vals = {
            'state': 'invoice_sending_failed',
            'message': values['error'],
        }
        if values.get('key_loading'):
            write_vals['key_loading'] = values['key_loading']
        document.sudo().write(write_vals)

        if values.get('attachment_raw'):
            if document.attachment_id:
                document.attachment_id.sudo().unlink()
            attachment_values = self._l10n_ro_edi_create_attachment_values(
                raw=values['attachment_raw'],
                res_model=document._name,
                res_id=document.id,
            )
            document.attachment_id = self.env['ir.attachment'].sudo().create(attachment_values)
        return document

    def _l10n_ro_edi_upsert_document_invoice_sending_failed(self, values: dict):
        """ Create or update a ``l10n_ro_edi.document`` of state ``invoice_sending_failed``.
        If a failed document already exists, it will be updated; otherwise, a new one is created.

        :param values: dictionary of {
            'error': <str>,
            'key_loading': <optional str>,
            'attachment_raw': <optional str>,
        }
        :return: ``l10n_ro_edi.document`` object """
        self.ensure_one()
        existing_failed = self._l10n_ro_edi_get_failed_documents()[:1]
        if existing_failed:
            return self._l10n_ro_edi_update_document_invoice_sending_failed(existing_failed, values)
        return self._l10n_ro_edi_create_document_invoice_sending_failed(values)

    def _l10n_ro_edi_update_document_invoice_validated(self, document, values: dict):
        """ Shorthand for updating a ``l10n_ro_edi.document`` to state ``invoice_validated``.

        :param document: ``l10n_ro_edi.document`` recordset to update
        :param values: dictionary containing 'key_loading', 'key_signature', 'key_certificate', and 'attachment_raw'
        :return: ``l10n_ro_edi.document`` object """
        self.ensure_one()
        document.sudo().write({
            'state': 'invoice_validated',
            'key_loading': values['key_loading'],
            'key_signature': values['key_signature'],
            'key_certificate': values['key_certificate'],
        })
        if document.attachment_id:
            document.attachment_id.sudo().unlink()
        attachment = self.env['ir.attachment'].sudo().create(
            self._l10n_ro_edi_create_attachment_values(values['attachment_raw'])
        )
        document.attachment_id = self.l10n_ro_edi_attachment_id = attachment
        return document

    def _l10n_ro_edi_get_attachment_file_name(self):
        """ Returns the signature file attachment's name from ``l10n_ro_edi.document``/``invoice_validated`` """
        self.ensure_one()
        return f"ciusro_{self.name.replace('/', '_')}.xml"

    def _l10n_ro_edi_get_failed_documents(self):
        """ Shorthand for getting all l10n_ro_edi.document in invoice_sending_failed state """
        self.ensure_one()
        return self.l10n_ro_edi_document_ids.filtered(lambda d: d.state == 'invoice_sending_failed')

    def _l10n_ro_edi_get_sent_and_failed_documents(self):
        """ Shorthand for getting all l10n_ro_edi.document in ``invoice_sent`` and ``invoice_sending_failed`` state """
        self.ensure_one()
        return self.l10n_ro_edi_document_ids.filtered(lambda d: d.state in ('invoice_sent', 'invoice_sending_failed'))

    ################################################################################
    # Send Logics
    ################################################################################

    def _l10n_ro_edi_get_pre_send_errors(self, xml_data='', assert_xml=False):
        """ Compute all possible common errors before sending the XML to the SPV """
        self.ensure_one()
        errors = []
        if not self.company_id.l10n_ro_edi_access_token:
            errors.append(_('Romanian access token not found. Please generate or fill it in the settings.'))
        if not xml_data and assert_xml:
            errors.append(_('CIUS-RO XML attachment not found.'))
        return errors

    def _l10n_ro_edi_send_invoice(self, xml_data):
        """
        This method send xml_data to the Romanian SPV using the single invoice's (self) data.
        The invoice's company and move_type will be used to calculate the required params in the send request.

        - Pre-check any errors from the invoice's pre_send check before sending

            - if error -> update existing failed document or create a new one, clear index
            - else -> continue to the next step

        - Send to E-Factura, and based on the result:

            - if error -> update existing failed document or create a new one, update index
            - if success -> create a new sending document, set index

        :param xml_data: string of the xml data to be sent
        """
        self.ensure_one()
        if errors := self._l10n_ro_edi_get_pre_send_errors(xml_data, True):
            self._l10n_ro_edi_upsert_document_invoice_sending_failed({'error': '\n'.join(errors)})
            self.l10n_ro_edi_index = False
            return

        self.env['res.company']._with_locked_records(self)
        result = self.env['l10n_ro_edi.document']\
                    .with_context(is_b2b=self.partner_id.commercial_partner_id.is_company)\
                    ._request_ciusro_send_invoice(
            company=self.company_id,
            xml_data=xml_data,
            move_type=self.move_type,
        )
        result['attachment_raw'] = xml_data
        if 'error' in result:  # result == {'error': <str>, 'attachment_raw': <bytes>}
            self._l10n_ro_edi_upsert_document_invoice_sending_failed(result)
            self.l10n_ro_edi_index = result.get('key_loading', False)
            self.message_post(body=_("Error when trying to send the E-Factura to the SPV: %s",
                                    result['error']))
        else:  # result == {'key_loading': <str>, 'attachment_raw': <bytes>}; initial sending successful
            self._l10n_ro_edi_create_document_invoice_sent(result)
            self.l10n_ro_edi_index = result['key_loading']
            self.message_post(body=_(
                "E-Factura has been sent and is now being validated by the SPV with index key: %s",
                result['key_loading'],
            ))

    def _l10n_ro_edi_fetch_invoice_sent_documents(self):
        """
        This method loops over all invoice with sending document in `self`. For each of them,
        it pre-checks error and make a fetch request for the invoice. Based on the answer, it will then:

        - if no answer is received, it will do nothing on the selected invoice
        - if error -> update the active sending document to error state
        - else (receives `key_download`) -> immediately make a download request and process it:

            - if error -> update the active sending document to error state
            - if success -> update the active sending document to validated state
        """
        session = requests.Session()
        invoices_to_fetch = self.filtered(lambda inv: inv.l10n_ro_edi_state == 'invoice_sent')

        for invoice in invoices_to_fetch:
            active_sending_document = invoice.l10n_ro_edi_document_ids.filtered(lambda d: d.state == 'invoice_sent')[:1]

            if errors := invoice._l10n_ro_edi_get_pre_send_errors():
                invoice._l10n_ro_edi_update_document_invoice_sending_failed(active_sending_document, {'error': '\n'.join(errors)})
                continue

            previous_raw = active_sending_document.attachment_id.sudo().raw
            self.env['res.company']._with_locked_records(invoices_to_fetch)
            result = self.env['l10n_ro_edi.document']._request_ciusro_fetch_status(
                company=invoice.company_id,
                key_loading=invoice.l10n_ro_edi_index,
                session=session,
            )

            if result == {}:  # SPV is still processing the XML (no answer yet); do nothing
                continue
            elif 'error' in result:  # Fetch error / SPV finished validating the XML and sends back a disapproval answer
                result['key_loading'] = invoice.l10n_ro_edi_index
                result['attachment_raw'] = previous_raw
                invoice._l10n_ro_edi_update_document_invoice_sending_failed(active_sending_document, result)
                invoice.message_post(body=_("Error when trying to fetch the E-Factura from the SPV: %s",
                                            result['error']))
            else:  # result == {'key_download': <str>}; SPV finished validation and sends us an approval answer
                # use the obtained key_download to immediately make a download request and process them
                final_result = self.env['l10n_ro_edi.document']._request_ciusro_download_answer(
                    company=invoice.company_id,
                    key_download=result['key_download'],
                    session=session,
                    status=result['state_status'],
                )
                final_result['key_loading'] = invoice.l10n_ro_edi_index
                if final_result.get('error'):
                    final_error_message = final_result['error'].replace('\t', '')
                    final_result.update({
                        'attachment_raw': previous_raw,
                        'error': final_error_message,
                    })
                    invoice._l10n_ro_edi_update_document_invoice_sending_failed(active_sending_document, final_result)
                    invoice.message_post(body=_("Error when trying to download the E-Factura answer from the SPV: %s",
                                                final_error_message))
                else:
                    invoice._l10n_ro_edi_update_document_invoice_validated(active_sending_document, final_result)

            if not tools.config['test_enable'] and not modules.module.current_test:
                self._cr.commit()
