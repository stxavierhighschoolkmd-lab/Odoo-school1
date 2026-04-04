# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import uuid

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.addons.l10n_vn_edi_viettel.models.sinvoice_service import SInvoiceService


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # EDI Fields
    l10n_vn_edi_state = fields.Selection(
        string='SInvoice Status',
        selection=[
            ('ready_to_send', 'Ready to Send'),
            ('sent', 'Sent'),
        ],
        copy=False,
        readonly=True,
    )
    l10n_vn_edi_transaction_id = fields.Char(
        string='SInvoice Transaction ID',
        help='Technical field to store the transaction ID if needed',
        export_string_translation=False,
        copy=False,
    )
    l10n_vn_edi_symbol_id = fields.Many2one(
        comodel_name='l10n_vn_edi_viettel.sinvoice.symbol',
        string='SInvoice Symbol',
        compute='_compute_l10n_vn_edi_symbol_id',
        readonly=False,
        store=True,
    )
    l10n_vn_edi_invoice_number = fields.Char(
        string='SInvoice Number',
        help='Invoice Number as appearing on SInvoice.',
        copy=False,
        readonly=True,
    )
    l10n_vn_edi_reservation_code = fields.Char(
        string='Secret Code',
        help='Secret code that can be used by a customer to lookup an invoice on SInvoice.',
        copy=False,
        readonly=True,
    )
    l10n_vn_edi_issue_date = fields.Datetime(
        string='Issue Date',
        help='Date of issue of the invoice on the e-invoicing system.',
        copy=False,
        readonly=True,
    )

    # File Fields
    l10n_vn_edi_sinvoice_file_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute=lambda self: self._l10n_vn_edi_compute_linked_attachment_id('l10n_vn_edi_sinvoice_file_id', 'l10n_vn_edi_sinvoice_file'),
        depends=['l10n_vn_edi_sinvoice_file'],
        copy=False,
        readonly=True,
        export_string_translation=False,
    )
    l10n_vn_edi_sinvoice_file = fields.Binary(
        string='SInvoice JSON File',
        copy=False,
        readonly=True,
        export_string_translation=False,
    )
    l10n_vn_edi_sinvoice_xml_file_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute=lambda self: self._l10n_vn_edi_compute_linked_attachment_id('l10n_vn_edi_sinvoice_xml_file_id', 'l10n_vn_edi_sinvoice_xml_file'),
        depends=['l10n_vn_edi_sinvoice_xml_file'],
        copy=False,
        readonly=True,
        export_string_translation=False,
    )
    l10n_vn_edi_sinvoice_xml_file = fields.Binary(
        string='SInvoice XML File',
        copy=False,
        readonly=True,
        export_string_translation=False,
    )
    l10n_vn_edi_sinvoice_pdf_file_id = fields.Many2one(
        comodel_name='ir.attachment',
        compute=lambda self: self._l10n_vn_edi_compute_linked_attachment_id('l10n_vn_edi_sinvoice_pdf_file_id', 'l10n_vn_edi_sinvoice_pdf_file'),
        depends=['l10n_vn_edi_sinvoice_pdf_file'],
        copy=False,
        readonly=True,
        export_string_translation=False,
    )
    l10n_vn_edi_sinvoice_pdf_file = fields.Binary(
        string='SInvoice PDF File',
        copy=False,
        readonly=True,
        export_string_translation=False,
    )

    # Metadata Fields for Transportation
    # Order/Contract
    l10n_vn_edi_economic_contract_no = fields.Char(
        string='Internal Transfer No/Economic Contract',
        compute='_compute_l10n_vn_edi_economic_contract_no',
        copy=False,
        readonly=False,
        store=True,
    )
    l10n_vn_edi_date = fields.Date(
        string='Internal Transfer Date',
        copy=False,
    )
    l10n_vn_edi_command_of = fields.Char(
        string='Issued by / Of',
        copy=False,
    )
    l10n_vn_edi_command_des = fields.Char(
        string='About',
        copy=False,
    )
    l10n_vn_edi_for_organization = fields.Char(
        string='With / For Organization',
        copy=False,
    )
    l10n_vn_edi_contract_no = fields.Char(
        string='Contract No (Transportation Contract)',
        copy=False,
    )
    l10n_vn_edi_command_date = fields.Date(
        string='Contract Date',
        copy=False,
    )
    l10n_vn_edi_invoice_note = fields.Text(
        string='Note / Remark',
        copy=False,
    )
    # Vehicle
    l10n_vn_edi_vehicle = fields.Char(
        string='Transport Vehicle',
        copy=False,
    )
    l10n_vn_edi_transformer = fields.Char(
        string="Carrier's Name",
        copy=False,
    )
    l10n_vn_edi_vehicle_number = fields.Char(
        string='Vehicle/Plate No',
        copy=False,
    )
    l10n_vn_edi_trip_number = fields.Char(
        string='Trip Number',
        copy=False,
    )
    # Dispatch
    l10n_vn_edi_export_at = fields.Char(
        string='Dispatch Warehouse',
        compute='_compute_l10n_vn_edi_export_at',
        readonly=False,
        store=True,
    )
    l10n_vn_edi_export_at_no = fields.Char(
        string='Dispatch Warehouse Code',
        copy=False,
    )
    l10n_vn_edi_bpx_kho = fields.Char(
        string='Dispatch Department',
        copy=False,
    )
    l10n_vn_edi_exporter_name = fields.Char(
        string="Dispatcher's Full Name",
        copy=False,
    )
    l10n_vn_edi_export_date = fields.Date(
        string='Dispatch Date',
        copy=False,
    )
    # Receipt
    l10n_vn_edi_import_at = fields.Char(
        string='Receiving Warehouse',
        compute='_compute_l10n_vn_edi_import_at',
        copy=False,
        readonly=False,
        store=True,
    )
    l10n_vn_edi_import_at_no = fields.Char(
        string='Receiving Warehouse Code',
        copy=False,
    )
    l10n_vn_edi_import_date = fields.Date(
        string='Receipt Date',
        copy=False,
    )
    l10n_vn_edi_tax_code_buyer = fields.Char(
        string="Buyer's Tax Code",
        copy=False,
    )
    # Goods
    l10n_vn_edi_quantity_certification = fields.Char(
        string='Quality Certification',
        copy=False,
    )
    l10n_vn_edi_date_certification = fields.Date(
        string='Certification Date',
        copy=False,
    )
    l10n_vn_edi_data_of_seal = fields.Char(
        string='Seal Data / Figures',
        copy=False,
    )
    l10n_vn_edi_number_of_seal = fields.Char(
        string='Number of Seals',
        copy=False,
    )
    # Others
    l10n_vn_edi_object = fields.Char(
        string='Subject / Object',
        copy=False,
    )
    l10n_vn_edi_cua = fields.Char(
        string='Of',
        copy=False,
    )
    l10n_vn_edi_internal_no = fields.Char(
        string='Internal Number',
        copy=False,
    )
    l10n_vn_edi_explain = fields.Text(
        string='Explanation / Description',
        copy=False,
    )

    # View Fields
    l10n_vn_edi_show_send_button = fields.Boolean(
        compute='_compute_l10n_vn_edi_show_send_button',
    )

    @api.depends(
        'state',
        'location_dest_id.usage',
        'location_dest_id.warehouse_id',
        'location_id.warehouse_id',
        'picking_type_id.default_location_dest_id.subcontractor_ids',
        'company_id.l10n_vn_edi_send_transfer_note',
        'l10n_vn_edi_state',
    )
    def _compute_l10n_vn_edi_show_send_button(self):
        for picking in self:
            is_inter_warehouse = (
                picking.location_dest_id.usage == 'internal'
                and picking.location_dest_id.warehouse_id != picking.location_id.warehouse_id
            )
            is_subcontractor_transfer = (
                picking.location_dest_id.usage == 'internal'
                and picking.picking_type_id.default_location_dest_id.subcontractor_ids
            )
            is_transit = picking.location_dest_id.usage == 'transit'
            is_not_receipts = picking.picking_type_id.code != 'incoming'

            picking.l10n_vn_edi_show_send_button = (
                picking.company_id.l10n_vn_edi_send_transfer_note
                and picking.l10n_vn_edi_state != 'sent'
                and picking.state in ('assigned', 'done')
                and (is_inter_warehouse or is_subcontractor_transfer or is_transit)
                and is_not_receipts
            )

    @api.depends('name', 'state')
    def _compute_l10n_vn_edi_economic_contract_no(self):
        for picking in self:
            if not picking.l10n_vn_edi_economic_contract_no and picking.name != '/':
                picking.l10n_vn_edi_economic_contract_no = picking.name

    @api.depends('location_id.warehouse_id')
    def _compute_l10n_vn_edi_export_at(self):
        for picking in self:
            if not picking.l10n_vn_edi_export_at:
                picking.l10n_vn_edi_export_at = picking.location_id.warehouse_id.name or ''

    @api.depends('location_dest_id.warehouse_id')
    def _compute_l10n_vn_edi_import_at(self):
        for picking in self:
            if not picking.l10n_vn_edi_import_at:
                picking.l10n_vn_edi_import_at = picking.location_dest_id.warehouse_id.name or ''

    @api.depends('picking_type_id.warehouse_id.l10n_vn_edi_sinvoice_symbol_id', 'company_id.l10n_vn_edi_default_sinvoice_symbol_id')
    def _compute_l10n_vn_edi_symbol_id(self):
        for picking in self:
            if picking.company_id.country_id.code == 'VN':
                # Use warehouse's default symbol, fallback to company symbol if not set
                picking.l10n_vn_edi_symbol_id = (
                    picking.picking_type_id.warehouse_id.l10n_vn_edi_sinvoice_symbol_id
                    or picking.company_id.l10n_vn_edi_default_sinvoice_symbol_id
                )
            else:
                picking.l10n_vn_edi_symbol_id = False

    def _l10n_vn_edi_compute_linked_attachment_id(self, attachment_id_fname, attachment_fname):
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self._ids),
            ('res_field', '=', attachment_fname),
        ])
        picking_vals = {att.res_id: att for att in attachments}
        for picking in self:
            picking[attachment_id_fname] = picking_vals.get(picking.id, False)

    def action_l10n_vn_send_to_sinvoice(self):
        self.ensure_one()
        return {
            'name': _('Send to SInvoice'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'l10n_vn_edi_viettel_stock.send_wizard',
            'target': 'new',
            'context': {'default_picking_id': self.id},
        }

    # =========================================================================
    # EDI LOGIC
    # =========================================================================

    def _l10n_vn_edi_check_configuration(self):
        """Return a list of error messages if the picking is not properly configured for SInvoice."""
        self.ensure_one()
        errors = []
        company = self.company_id
        if not company.l10n_vn_edi_username or not company.l10n_vn_edi_password:
            errors.append(_('SInvoice credentials are missing on company %s.', company.display_name))
        if not company.vat:
            errors.append(_('VAT number is missing on company %s.', company.display_name))
        company_phone = company.phone and SInvoiceService.format_phone_number(company.phone)
        if company_phone and not company_phone.isdecimal():
            errors.append(_('Phone number for company %s must only contain digits or +.', company.display_name))
        if self.partner_id:
            partner_phone = self.partner_id.phone and SInvoiceService.format_phone_number(self.partner_id.phone)
            if partner_phone and not partner_phone.isdecimal():
                errors.append(_('Phone number for partner %s must only contain digits or +.', self.partner_id.display_name))
        if not self.l10n_vn_edi_symbol_id:
            errors.append(_('The transfer note symbol must be provided. Set it on the warehouse or in the Inventory settings.'))
        if self.l10n_vn_edi_symbol_id and not self.l10n_vn_edi_symbol_id.invoice_template_code:
            errors.append(_("The symbol's template code must be provided."))
        if not company.street or not company.country_id:
            errors.append(_('The street and country of company %s must be provided.', company.display_name))
        return errors

    def _l10n_vn_edi_generate_transfer_note_json(self):
        """Return the dict of data that will be sent to the API to create the transfer note."""
        self.ensure_one()
        self.l10n_vn_edi_issue_date = fields.Datetime.now()
        json_values = {}
        self._l10n_vn_edi_add_general_info(json_values)
        self._l10n_vn_edi_add_buyer_info(json_values)
        self._l10n_vn_edi_add_seller_info(json_values)
        self._l10n_vn_edi_add_item_info(json_values)
        self._l10n_vn_edi_add_tax_breakdowns(json_values)
        self._l10n_vn_edi_add_payment_information(json_values)
        self._l10n_vn_edi_add_metadata(json_values)
        return json_values

    def _l10n_vn_edi_add_general_info(self, json_values):
        self.ensure_one()
        json_values['generalInvoiceInfo'] = {
            'transactionUuid': str(uuid.uuid4()),
            'templateCode': self.l10n_vn_edi_symbol_id.invoice_template_code,
            'invoiceSeries': self.l10n_vn_edi_symbol_id.name,
            'invoiceIssuedDate': SInvoiceService.format_date(self.l10n_vn_edi_issue_date),
            'currencyCode': self.company_id.currency_id.name or 'VND',
            'adjustmentType': '1',
            'paymentStatus': True,
            'cusGetInvoiceRight': True,
        }

    def _l10n_vn_edi_add_buyer_info(self, json_values):
        self.ensure_one()
        if partner := self.partner_id:
            phone = partner.phone and SInvoiceService.format_phone_number(partner.phone) or ''
            buyer_address = self.partner_id._display_address(without_name=True, separator=', ')
            json_values['buyerInfo'] = {
                'buyerName': partner.name or '',
                'buyerLegalName': partner.commercial_partner_id.name or '',
                'buyerTaxCode': partner.commercial_partner_id.vat or '',
                'buyerAddressLine': buyer_address or '',
                'buyerPhoneNumber': phone,
                'buyerEmail': partner.email or '',
                'buyerCityName': partner.city or partner.state_id.name or '',
                'buyerCountryCode': partner.country_id.code or '',
            }
        else:
            json_values['buyerInfo'] = {'buyerNotGetInvoice': 1}

    def _l10n_vn_edi_add_seller_info(self, json_values):
        self.ensure_one()
        company = self.company_id
        phone = company.phone and SInvoiceService.format_phone_number(company.phone) or ''
        seller_address = company.partner_id._display_address(without_name=True, separator=', ')
        json_values['sellerInfo'] = {
            'sellerLegalName': company.name,
            'sellerTaxCode': company.vat,
            'sellerAddressLine': seller_address or '',
            'sellerPhoneNumber': phone,
            'sellerEmail': company.email or '',
            'sellerDistrictName': company.state_id.name or '',
            'sellerCountryCode': company.country_id.code or '',
        }

    def _l10n_vn_edi_add_item_info(self, json_values):
        self.ensure_one()
        items = []
        for move in self.move_ids:
            qty = move.product_uom_qty if self.state == 'draft' else move.quantity
            if not qty:
                continue
            unit_price = move.l10n_vn_edi_unit_price
            items.append({
                'itemCode': move.product_id.default_code or '',
                'itemName': move.product_id.name,
                'unitName': move.product_id.uom_name or 'Unit',
                'unitPrice': unit_price,
                'quantity': qty,
                'itemTotalAmountWithoutTax': self.company_id.currency_id.round(unit_price * qty),
                'taxPercentage': -2,  # No tax for internal transfer notes
                'taxAmount': 0,
            })
        json_values['itemInfo'] = items

    def _l10n_vn_edi_add_tax_breakdowns(self, json_values):
        """Tax breakdown for transfer notes; no tax applies for stock picking."""
        self.ensure_one()
        total_amount = sum(item['itemTotalAmountWithoutTax'] for item in json_values.get('itemInfo', []))
        json_values['taxBreakdowns'] = [{
            'taxPercentage': -2,  # -2 means no tax
            'taxableAmount': total_amount,
            'taxAmount': 0,
            'taxableAmountPos': True,
            'taxAmountPos': True,
        }]

    def _l10n_vn_edi_add_payment_information(self, json_values):
        self.ensure_one()
        json_values['payments'] = [{
            # We need to provide a value but when we send the invoice, we may not have this information.
            # According to VN laws, if the payment method has not been determined, we can fill in TM/CK.
            # TM is for bank transfer, CK is for cash payment.
            'paymentMethodName': 'TM/CK',
        }]

    def _l10n_vn_edi_add_metadata(self, json_values):
        self.ensure_one()

        def _meta(key_tag, value, key_label, is_required=False, value_type='text'):
            return {
                'keyTag': key_tag,
                'stringValue': value or '',
                'valueType': value_type,
                'keyLabel': key_label,
                'isRequired': is_required,
                'isSeller': False,
            }

        metadata = []
        # Order/Contract
        metadata.append(_meta('economicContractNo', self.l10n_vn_edi_economic_contract_no, 'Lệnh điều động nội bộ', is_required=True))
        if self.l10n_vn_edi_date:
            metadata.append(_meta('Date', str(self.l10n_vn_edi_date), 'Ngày tháng năm lệnh điều động'))
        if self.l10n_vn_edi_command_of:
            metadata.append(_meta('commandOf', self.l10n_vn_edi_command_of, 'Của'))
        if self.l10n_vn_edi_command_des:
            metadata.append(_meta('commandDes', self.l10n_vn_edi_command_des, 'Về việc'))
        if self.l10n_vn_edi_for_organization:
            metadata.append(_meta('forOrganization', self.l10n_vn_edi_for_organization, 'Với'))
        if self.l10n_vn_edi_contract_no:
            metadata.append(_meta('contractNo', self.l10n_vn_edi_contract_no, 'Hợp đồng số'))
        if self.l10n_vn_edi_command_date:
            metadata.append(_meta('commandDate', str(self.l10n_vn_edi_command_date), 'Ngày điều động'))
        if self.l10n_vn_edi_invoice_note:
            metadata.append(_meta('invoiceNote', self.l10n_vn_edi_invoice_note, 'Ghi chú'))
        # Vehicle
        metadata.append(_meta('vehicle', self.l10n_vn_edi_vehicle, 'Phương tiện vận chuyển', is_required=True))
        if self.l10n_vn_edi_transformer:
            metadata.append(_meta('transformer', self.l10n_vn_edi_transformer, 'Tên người vận chuyển'))
        if self.l10n_vn_edi_vehicle_number:
            metadata.append(_meta('vehicleNumber', self.l10n_vn_edi_vehicle_number, 'Số xe', value_type='date'))
        if self.l10n_vn_edi_trip_number:
            metadata.append(_meta('tripNumber', self.l10n_vn_edi_trip_number, 'Chuyến số'))
        # Dispatch
        if self.l10n_vn_edi_export_at:
            metadata.append(_meta('exportAt', self.l10n_vn_edi_export_at, 'Xuất tại kho'))
        if self.l10n_vn_edi_export_at_no:
            metadata.append(_meta('exportAtNo', self.l10n_vn_edi_export_at_no, 'Mã kho xuất'))
        if self.l10n_vn_edi_bpx_kho:
            metadata.append(_meta('BPXKho', self.l10n_vn_edi_bpx_kho, 'Bộ phận xuất kho'))
        if self.l10n_vn_edi_exporter_name:
            metadata.append(_meta('HVTNXHang', self.l10n_vn_edi_exporter_name, 'Họ và tên người xuất hàng'))
        if self.l10n_vn_edi_export_date:
            metadata.append(_meta('exportDate', str(self.l10n_vn_edi_export_date), 'Ngày xuất kho'))
        # Receipt
        if self.l10n_vn_edi_import_at:
            metadata.append(_meta('importAt', self.l10n_vn_edi_import_at, 'Nhập tại kho'))
        if self.l10n_vn_edi_import_at_no:
            metadata.append(_meta('importAtNo', self.l10n_vn_edi_import_at_no, 'Mã kho nhập'))
        if self.l10n_vn_edi_import_date:
            metadata.append(_meta('importDate', str(self.l10n_vn_edi_import_date), 'Ngày nhập kho'))
        if self.l10n_vn_edi_tax_code_buyer:
            metadata.append(_meta('taxCodeBuyer', self.l10n_vn_edi_tax_code_buyer, 'MST'))
        # Goods
        if self.l10n_vn_edi_quantity_certification:
            metadata.append(_meta('quantityCertification', self.l10n_vn_edi_quantity_certification, 'Chứng nhận chất lượng'))
        if self.l10n_vn_edi_date_certification:
            metadata.append(_meta('dateCertification', str(self.l10n_vn_edi_date_certification), 'Ngày chứng nhận'))
        if self.l10n_vn_edi_data_of_seal:
            metadata.append(_meta('dataOfSeal', self.l10n_vn_edi_data_of_seal, 'Số liệu các niêm chỉ'))
        if self.l10n_vn_edi_number_of_seal:
            metadata.append(_meta('numberOfSeal', self.l10n_vn_edi_number_of_seal, 'Số lượng niêm chỉ'))
        # Others
        if self.l10n_vn_edi_object:
            metadata.append(_meta('Object', self.l10n_vn_edi_object, 'Đối tượng'))
        if self.l10n_vn_edi_cua:
            metadata.append(_meta('cua', self.l10n_vn_edi_cua, 'Cua'))
        if self.l10n_vn_edi_internal_no:
            metadata.append(_meta('InternalNo', self.l10n_vn_edi_internal_no, 'Số nội bộ'))
        if self.l10n_vn_edi_explain:
            metadata.append(_meta('Explain', self.l10n_vn_edi_explain, 'Diễn giải'))
        json_values['metadata'] = metadata

    def _l10n_vn_edi_send_transfer_note(self, json_data):
        """Send the transfer note to SInvoice. Returns a list of error messages."""
        self.ensure_one()
        self.env['res.company']._with_locked_records(self)

        access_token, error = self.company_id._l10n_vn_edi_get_access_token()
        if error:
            return [error]

        with SInvoiceService(access_token, self.company_id.vat) as sinvoice:
            invoice_data = {}
            if self.l10n_vn_edi_transaction_id:
                lookup, _err = sinvoice.lookup_invoice(self.l10n_vn_edi_transaction_id)
                if 'result' in lookup:
                    invoice_data = lookup['result'][0]
            else:
                self.l10n_vn_edi_transaction_id = json_data['generalInvoiceInfo']['transactionUuid']

            if not invoice_data:
                invoice_data, error_message = sinvoice.create_invoice(json_data)
                if error_message:
                    if 'BAD_REQUEST_STRING_VALUE_INFO_UPDATE_REQUIRED' in error_message:
                        return ["Please fill out the required template fields under the E-Transfer Note tab!"]
                    return [error_message]

        self.write({
            'l10n_vn_edi_reservation_code': invoice_data.get('reservationCode'),
            'l10n_vn_edi_invoice_number': invoice_data.get('invoiceNo'),
            'l10n_vn_edi_state': 'sent',
        })

        return []

    def _l10n_vn_edi_fetch_files(self):
        """Fetch XML and PDF files from SInvoice and attach them to this picking."""
        self.ensure_one()
        if self.l10n_vn_edi_state != 'sent':
            raise UserError(_("Please send the transfer note to SInvoice before fetching the files."))

        access_token, error = self.company_id._l10n_vn_edi_get_access_token()
        if error:
            return {'error_title': _('Cannot get access token.'), 'errors': [error]}

        template_code = self.l10n_vn_edi_symbol_id.invoice_template_code
        invoice_no = self.l10n_vn_edi_invoice_number
        xml_data = xml_error = pdf_data = pdf_error = None

        with SInvoiceService(access_token, self.company_id.vat) as sinvoice:
            zip_data, zip_error = sinvoice.get_invoice_file(template_code, invoice_no, 'ZIP')
            if zip_error:
                xml_error = zip_error
            else:
                xml_data, xml_error = sinvoice.extract_xml_from_zip(
                    base64.b64decode(zip_data['fileToBytes'])
                )
                if xml_data:
                    xml_data['res_field'] = 'l10n_vn_edi_sinvoice_xml_file'

            pdf_file_data, pdf_error = sinvoice.get_invoice_file(template_code, invoice_no, 'PDF')
            if not pdf_error and pdf_file_data.get('fileToBytes'):
                pdf_data = {
                    'name': pdf_file_data['fileName'],
                    'mimetype': 'application/pdf',
                    'raw': base64.b64decode(pdf_file_data['fileToBytes']),
                    'res_field': 'l10n_vn_edi_sinvoice_pdf_file',
                }

        attachments_data = []
        for file, err in [(xml_data, xml_error), (pdf_data, pdf_error)]:
            if err or not file:
                continue
            attachments_data.append({
                'name': file['name'],
                'raw': file['raw'],
                'mimetype': file['mimetype'],
                'res_model': self._name,
                'res_id': self.id,
                'res_field': file['res_field'],
            })

        if attachments_data:
            attachments = self.env['ir.attachment'].with_user(SUPERUSER_ID).create(attachments_data)
            self.invalidate_recordset(fnames=[
                'l10n_vn_edi_sinvoice_xml_file_id', 'l10n_vn_edi_sinvoice_xml_file',
                'l10n_vn_edi_sinvoice_pdf_file_id', 'l10n_vn_edi_sinvoice_pdf_file',
            ])
            self.message_post(
                body=_('Transfer note sent to SInvoice'),
                attachment_ids=attachments.ids + self.l10n_vn_edi_sinvoice_file_id.ids,
            )

        if xml_error or pdf_error:
            return {
                'error_title': _('Error when receiving SInvoice files.'),
                'errors': [e for e in [xml_error, pdf_error] if e],
            }
