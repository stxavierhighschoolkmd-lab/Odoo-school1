from datetime import datetime
import json
import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.urls import urljoin


class PlNipError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class L10nPlAccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # partners for whose we cannot find link between vat and bank account calling gov api
    l10n_pl_bank_verification_invalid_bank_account_ids = fields.Many2many(comodel_name='res.partner.bank', compute='_compute_l10n_pl_bank_verification')
    # partners whose vat cannot be found in gov api
    l10n_pl_not_found_partner_ids = fields.Many2many(comodel_name='res.partner', compute='_compute_l10n_pl_bank_verification')
    # partners who do not have a VAT number or bank account (-> internal, no api call)
    l10n_pl_incomplete_data_partner_ids = fields.Many2many(comodel_name='res.partner', compute='_compute_l10n_pl_bank_verification')

    @api.depends('line_ids', 'partner_bank_id')
    def _compute_l10n_pl_bank_verification(self):
        for wizard in self:
            # Early skip if company not PL
            if wizard.company_id.country_code != 'PL':
                wizard.l10n_pl_bank_verification_invalid_bank_account_ids = False
                wizard.l10n_pl_not_found_partner_ids = False
                wizard.l10n_pl_incomplete_data_partner_ids = False
                continue

            to_check = []
            for batch in wizard.batches:
                if self._batch_need_check(batch):
                    to_check.append(batch)

            # write verification status of the relevant bank accounts in batches to check
            results = self._check_partners(to_check)
            wizard.l10n_pl_incomplete_data_partner_ids = self.env['res.partner'].browse(results['incomplete_partner_ids'])

            # Gather datas from res.partner.bank to display invalid bank accounts and not found partners
            invalid_bank_accounts = []
            not_found_partners = []
            for batch in to_check:
                partner_bank = self._get_partner_bank_from_batch(batch)
                if partner_bank.l10n_pl_bank_verification_status == 'invalid':
                    invalid_bank_accounts.append(partner_bank.id)
                elif partner_bank.l10n_pl_bank_verification_status == 'failed' and partner_bank.l10n_pl_bank_verification_fail_reason == 'not_found_partner':
                    not_found_partners.append(batch['payment_values']['partner_id'])

            wizard.l10n_pl_bank_verification_invalid_bank_account_ids = self.env['res.partner.bank'].browse(invalid_bank_accounts)
            wizard.l10n_pl_not_found_partner_ids = self.env['res.partner'].browse(not_found_partners)

    @api.model
    def _batch_need_check(self, batch):
        """
        Does batch need a government API call to check if the partner vat is linked to its account number
        """
        partner = self.env['res.partner'].browse(batch['payment_values']['partner_id'])
        if isinstance(batch['lines'], models.Model):
            moves = batch['lines'].move_id
        else:
            moves = self.env['account.move.line'].browse(batch['lines']).move_id

        return self._payment_need_check(
            partner,
            batch['payment_values']['payment_type'],
            moves.mapped('amount_total'),
            moves.currency_id,
        )

    @api.model
    def _payment_need_check(self, partner, payment_type, amounts, currency):
        """
        :param amounts: list of amounts in case values are coming from a batch
        """
        if partner.country_code != 'PL':
            return False

        if payment_type != 'outbound':
            return False

        pln = self.env.ref('base.PLN', raise_if_not_found=False)
        if currency != pln:
            return False

        return any(pln.compare_amounts(amount, 15000.0) >= 0 for amount in amounts)

    @api.model
    def _check_partners(self, batches, date=None):
        results = {
            'incomplete_partner_ids': [],  # missing data in odoo
        }

        if not batches:
            return results

        date = date or datetime.now().date()
        partners_to_check = self.env['res.partner']
        for batch in batches:
            partner = self.env['res.partner'].browse(batch['payment_values']['partner_id'])
            # Check partner has VAT and bank account (in odoo)
            if partner._is_vat_void(partner.vat) or not partner.bank_ids:
                if partner.bank_ids:
                    self._write_status_on_partner_banks(partner.bank_ids, 'failed', reason='incomplete_partner')
                # we need to collect this information in case the partner has no bank account we can register status on
                results['incomplete_partner_ids'].append(partner.id)
                continue

            # Check if partner bank account have already been checked for date
            if not self._bank_account_already_checked(partner, batch, date):
                partners_to_check |= partner

        self._build_endpoints_and_update_bank_accounts(partners_to_check, date)
        return results

    @api.model
    def _make_request(self, endpoint, params=None):
        """
        Send request to the government API
        :param endpoint: The endpoint to call in the API
        :param params: Params to include in request
        :return: response
        """
        params = params or {}
        url = urljoin('https://wl-api.mf.gov.pl/api', endpoint)
        response = requests.request(
            'GET',
            url,
            headers={'Content-Type': 'application/json'},
            params=params,
            timeout=5,
        )
        return response

    @api.model
    def _handle_response(self, response):
        """
        Handle response given by the API
        :param response: The response received by the API
        :return: Response content or raise an error
        """
        if response.status_code == 200:
            return response.content.decode()
        elif response.status_code == 400:
            content = json.loads(response.content.decode())
            if content['code'] in ['WL-113', 'WL-115']:  # 113: incorrect format, 115: vat not found
                raise PlNipError(self.env._("The partner has an invalid nip"))
            else:
                raise ValidationError(self.env._("An unknown error occurred while calling the government API. Please contact support with the following information:\n"
                                        "Status code: %(status_code)s\n"
                                        "Error message: %(msg)s", status_code=response.status_code, msg=response.content.decode()))
        elif 500 <= response.status_code < 600:
            raise ValidationError(self.env._("An error occurred during call to government API. Please try again later"))
        else:
            raise ValidationError(self.env._("An unknown error occurred while calling the government API. Please contact support with the following information:\n"
                                    "Status code: %(status_code)s\n"
                                    "Error message: %(msg)s", status_code=response.status_code, msg=response.content.decode()))

    @api.model
    def _update_bank_accounts(self, datas):
        request_id = datas['requestId']
        timestamp = datetime.strptime(datas['requestDateTime'], "%d-%m-%Y %H:%M:%S")

        for entry in datas.get('entries', [datas]):
            identifier = entry.get('identifier')
            if entry.get('error'):
                partner = self._get_partner_from_identifier(identifier)
                self._write_status_on_partner_banks(partner.bank_ids, 'failed', reason='not_found_partner')
                continue

            subject = entry.get('subjects', [entry.get('subject')])[0]
            if not subject:  # subject = [] or subject = None
                raise PlNipError(self.env._("The call returned empty subject"))
            partner = self._get_partner_from_identifier(identifier or subject['nip'])
            for bank_account in partner.bank_ids:
                bank_account_number = bank_account.account_number.removeprefix('PL').removeprefix('pl').replace(' ', '')
                status = 'valid' if bank_account_number in subject.get('accountNumbers', []) else 'invalid'
                self._write_status_on_partner_banks(bank_account, status, timestamp=timestamp, request_id=request_id)

    def _create_payment_vals_from_wizard(self, batch_result):
        # EXTENDS account
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        return self._update_payment_vals(payment_vals, batch_result)

    def _create_payment_vals_from_batch(self, batch_result):
        # EXTENDS account
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        return self._update_payment_vals(payment_vals, batch_result)

    # ===================================
    # HELPERS
    # ===================================

    @api.model
    def _update_payment_vals(self, payment_vals, batch_result):
        if not self._batch_need_check(batch_result):
            return payment_vals

        partner_bank = self._get_partner_bank_from_batch(batch_result)
        payment_vals.update({
            'l10n_pl_bank_verification_status': partner_bank.l10n_pl_bank_verification_status,
            'l10n_pl_bank_verification_timestamp': partner_bank.l10n_pl_bank_verification_timestamp,
            'l10n_pl_bank_verification_request_id': partner_bank.l10n_pl_bank_verification_request_id,
            'l10n_pl_bank_verification_fail_reason': partner_bank.l10n_pl_bank_verification_fail_reason,
        })

        return payment_vals

    @api.model
    def _build_endpoints_and_update_bank_accounts(self, partners_to_update, date):
        # create endpoints to call, API support 30 vat numbers per request
        endpoints = {}  # {endpoint: recordset(partners)}
        if not partners_to_update:
            return
        if len(partners_to_update) == 1:
            sanitized_vat = partners_to_update.vat.removeprefix('pl').removeprefix('PL')
            endpoints[f'/search/nip/{sanitized_vat}'] = partners_to_update
        else:
            for i in range(int(len(partners_to_update) / 30) + 1):
                partners = partners_to_update[i * 30:i * 30 + 30]
                sanitized_vats = ",".join(partners.mapped(lambda partner: partner.vat.removeprefix('pl').removeprefix('PL')))
                endpoints[f'/search/nips/{sanitized_vats}'] = partners

        # Call api for every endpoint
        for endpoint, partners in endpoints.items():
            try:
                response = self._make_request(endpoint, params={'date': date})
                response_content = self._handle_response(response)
            except PlNipError:
                # Handle error case where vat is not found (single vat request)
                self._write_status_on_partner_banks(partners.bank_ids, 'failed', reason='not_found_partner')
                continue
            except ValidationError:
                self._write_status_on_partner_banks(partners.bank_ids, 'failed', reason='unknown')
                continue

            try:
                # we encapsulate these in a try to limit the tracebacks, as we're reading datas fetched from API
                # and maybe we didn't anticipate some corner cases
                datas = json.loads(response_content)['result']
                self._update_bank_accounts(datas)
            except (KeyError, json.decoder.JSONDecodeError, PlNipError):  # Do we need to add TypeError for NoneType not suscriptable ?
                self._write_status_on_partner_banks(partners.bank_ids, 'failed', reason='unknown')
                continue

    @api.model
    def _bank_account_already_checked(self, partner, batch, date):
        partner_bank = self._get_partner_bank_from_batch(batch)
        return partner_bank._l10n_pl_status_at_date(date) not in ('unverified', 'failed')

    @api.model
    def _get_partner_from_identifier(self, identifier):
        identifiers = [identifier, 'pl' + identifier, 'PL' + identifier]
        return self.env['res.partner'].search([('vat', 'in', identifiers)], limit=1)

    @api.model
    def _get_partner_bank_from_batch(self, batch):
        if partner_bank_id := batch['payment_values']['partner_bank_id']:
            return self.env['res.partner.bank'].browse(partner_bank_id)
        partner = self.env['res.partner'].browse(batch['payment_values']['partner_id'])
        return partner.bank_ids[0] if len(partner.bank_ids) > 1 else partner.bank_ids

    @api.model
    def _write_status_on_partner_banks(self, bank_ids, status, timestamp=False, request_id=False, reason=False):
        vals = {
            'l10n_pl_bank_verification_status': status,
            'l10n_pl_bank_verification_timestamp': timestamp or datetime.now(),
        }
        if request_id:
            vals['l10n_pl_bank_verification_request_id'] = request_id
        if reason:
            vals['l10n_pl_bank_verification_fail_reason'] = reason
        bank_ids.write(vals)
