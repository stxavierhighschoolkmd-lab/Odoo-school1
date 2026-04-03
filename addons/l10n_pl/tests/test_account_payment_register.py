from datetime import datetime
from freezegun import freeze_time
from unittest.mock import patch

from odoo import Command

from odoo.tests import Form, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_pl.tests.utils.utils import FakeResponse


def _make_request_patched(self, endpoint, params=None):
    return FakeResponse(endpoint)


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestL10nPlAccountPaymentRegister(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pl')
    def setUpClass(cls):
        super().setUpClass()

        cls.pl_supplier = cls.env['res.partner'].create({
            'name': 'PL SUPPLIER',
            'street': 'Church street, 42',
            'city': 'Warszawa',
            'zip': '1234',
            'country_id': cls.env.ref('base.pl').id,
            'vat': '1111111111',
        })
        cls.pl_supplier_bank_account = cls.env['res.partner.bank'].create({
            'account_number': 'PL61109010140000071219812874',
            'partner_id': cls.pl_supplier.id,
        })
        cls.pl_supplier_move = cls.env['account.move'].create({
            'partner_id': cls.pl_supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': cls.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': cls.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 15000,
            })]
        })
        cls.pl_supplier_move.action_post()

        cls.startClassPatcher(freeze_time('2026-01-31 10:00:00'))

    def _create_payments(self, moves):
        action_register_payment = moves.action_register_payment()
        self.assertTrue(action_register_payment)
        wizard = self.env[action_register_payment['res_model']].with_context(action_register_payment['context']).create({})

        action_create_payment = wizard.action_create_payments()
        if action_create_payment.get('res_id'):
            return self.env[action_create_payment['res_model']].browse(action_create_payment['res_id'])
        return self.env[action_create_payment['res_model']].search(action_create_payment['domain'])

    def _check_form_fields(self, moves, invalid_bank_accounts=False, not_found_partners=False, incomplete_partners=False):
        """
        invalid_bank_accounts: bank account number is not linked to partner vat in gov files
        not_found_partners: partners with a vat not found in gov files
        incomplete_partners: no api call, partner missing a vat or a bank account
        """
        with Form.from_action(self.env, moves.action_register_payment()) as wiz_form:
            (self.assertEqual if invalid_bank_accounts else self.assertFalse)(
                wiz_form.l10n_pl_bank_verification_invalid_bank_account_ids.ids,
                invalid_bank_accounts or 'Wizard should show invalid bank accounts',
            )
            (self.assertEqual if not_found_partners else self.assertFalse)(
                wiz_form.l10n_pl_not_found_partner_ids.ids,
                not_found_partners or 'Wizard should show not found partners',
            )
            (self.assertEqual if incomplete_partners else self.assertFalse)(
                wiz_form.l10n_pl_incomplete_data_partner_ids.ids,
                incomplete_partners or 'Wizard should show incomplete data partners',
            )

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request', _make_request_patched)
    def test_register_single_payment_with_valid_bank_account_check(self):
        self._check_form_fields(self.pl_supplier_move)

        self.assertRecordValues(self.pl_supplier_bank_account, [{
            'l10n_pl_bank_verification_status': 'valid',
            'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-01',
            'l10n_pl_bank_verification_timestamp': datetime(2026, 1, 31, 10, 0, 0),
        }])

        payment = self._create_payments(self.pl_supplier_move)

        self.assertEqual(payment.l10n_pl_bank_verification_status, 'valid')
        self.assertEqual(payment.l10n_pl_bank_verification_request_id, 'AZERTYUIOP-01')
        self.assertEqual(payment.l10n_pl_bank_verification_timestamp, datetime(2026, 1, 31, 10, 0, 0))

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request', _make_request_patched)
    def test_register_single_payment_with_invalid_or_missing_vat(self):
        # partner has no vat
        supplier = self.env['res.partner'].create({
            'name': 'Invalid PL supplier',
            'street': 'Church street, 43',
            'city': 'Warszawa',
            'zip': '1234',
            'country_id': self.env.ref('base.pl').id,
        })
        move = self.env['account.move'].create({
            'partner_id': supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 15000,
            })]
        })
        move.action_post()

        self._check_form_fields(move, incomplete_partners=supplier.ids)

        # assign a vat number but still no bank account
        supplier.vat = '0000000000'
        self._check_form_fields(move, incomplete_partners=supplier.ids)

        # assign a bank account number
        self.pl_supplier_bank_account = self.env['res.partner.bank'].create({
            'account_number': '61109010140000071219812870',
            'partner_id': supplier.id,
        })
        self._check_form_fields(move, not_found_partners=supplier.ids)

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request', _make_request_patched)
    def test_register_multiple_payments_with_an_invalid_vat(self):
        supplier = self.env['res.partner'].create({
            'name': 'Invalid PL supplier',
            'street': 'Church street, 44',
            'city': 'Warszawa',
            'zip': '1234',
            'country_id': self.env.ref('base.pl').id,
            'vat': '0000000000',
        })
        self.env['res.partner.bank'].create({
            'account_number': '61109010140000071219812870',
            'partner_id': supplier.id,
        })
        move = self.env['account.move'].create({
            'partner_id': supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 15000,
            })]
        })
        move.action_post()
        moves = move + self.pl_supplier_move
        self._check_form_fields(moves, not_found_partners=supplier.ids)

        date = datetime(2026, 1, 31, 10, 0, 0)

        self.assertRecordValues(self.pl_supplier_bank_account, [{
            'l10n_pl_bank_verification_status': 'valid',
            'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-02',
            'l10n_pl_bank_verification_timestamp': date,
        }])

        payments = self._create_payments(moves)
        self.assertRecordValues(payments, [
            {
                'l10n_pl_bank_verification_status': 'failed',
                'l10n_pl_bank_verification_timestamp': date,
                'l10n_pl_bank_verification_request_id': False,
                'l10n_pl_bank_verification_fail_reason': 'not_found_partner',
            },
            {
                'l10n_pl_bank_verification_status': 'valid',
                'l10n_pl_bank_verification_timestamp': date,
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-02',
                'l10n_pl_bank_verification_fail_reason': False,
            },
        ])

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request', _make_request_patched)
    def test_register_multiple_payments_with_valid_bank_account_check(self):
        supplier = self.env['res.partner'].create({
            'name': 'Valid PL supplier',
            'street': 'Church street, 45',
            'city': 'Warszawa',
            'zip': '1234',
            'country_id': self.env.ref('base.pl').id,
            'vat': '2222222222',
        })
        supplier_bank = self.env['res.partner.bank'].create({
            'account_number': '61109010140000071219812875',
            'partner_id': supplier.id,
        })
        move = self.env['account.move'].create({
            'partner_id': supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 15000,
            })]
        })
        move.action_post()
        moves = move + self.pl_supplier_move
        self._check_form_fields(moves)

        date = datetime(2026, 1, 31, 10, 0, 0)

        self.assertRecordValues(self.pl_supplier_bank_account + supplier_bank, [
            {
                'l10n_pl_bank_verification_status': 'valid',
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-03',
                'l10n_pl_bank_verification_timestamp': date,
            },
            {
                'l10n_pl_bank_verification_status': 'valid',
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-03',
                'l10n_pl_bank_verification_timestamp': date,
            },
        ])

        payments = self._create_payments(moves)
        self.assertRecordValues(payments, [
            {
                'l10n_pl_bank_verification_status': 'valid',
                'l10n_pl_bank_verification_timestamp': date,
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-03',
            },
            {
                'l10n_pl_bank_verification_status': 'valid',
                'l10n_pl_bank_verification_timestamp': date,
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-03',
            },
        ])

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request', _make_request_patched)
    def test_register_multiple_payments_with_one_bank_account_not_found(self):
        supplier = self.env['res.partner'].create({
            'name': 'Invalid PL supplier',
            'street': 'Church street, 45',
            'city': 'Warszawa',
            'zip': '1234',
            'country_id': self.env.ref('base.pl').id,
            'vat': 'PL2222222222',
        })
        bank_account = self.env['res.partner.bank'].create({
            'account_number': '61109010140000071219812800',
            'partner_id': supplier.id,
        })
        move = self.env['account.move'].create({
            'partner_id': supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 15000,
            })]
        })
        move.action_post()
        moves = move + self.pl_supplier_move
        self._check_form_fields(moves, invalid_bank_accounts=bank_account.ids)

        date = datetime(2026, 1, 31, 10, 0, 0)

        self.assertRecordValues(self.pl_supplier_bank_account + bank_account, [
            {
                'l10n_pl_bank_verification_status': 'valid',
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-03',
                'l10n_pl_bank_verification_timestamp': date,
            },
            {
                'l10n_pl_bank_verification_status': 'invalid',
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-03',
                'l10n_pl_bank_verification_timestamp': date,
            },
        ])

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request')
    def test_register_payments_of_accounts_already_checked_dont_call_api(self, _make_request_not_called_patched):
        # At date, if the bank account was already checked, we shouldn't call the API
        self.pl_supplier_bank_account.write({
            'l10n_pl_bank_verification_status': 'valid',
            'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-99',
            'l10n_pl_bank_verification_timestamp': datetime(2026, 1, 31, 10, 0, 0),
        })
        self._check_form_fields(self.pl_supplier_move)
        _make_request_not_called_patched.assert_not_called()

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request', _make_request_patched)
    def test_register_payment_under_verification_limit(self):
        move = self.env['account.move'].create({
            'partner_id': self.pl_supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 500,
            })]
        })
        move.action_post()
        self._check_form_fields(move)

        supplier = self.env['res.partner'].create({
            'name': 'Invalid PL supplier',
            'street': 'Church street, 45',
            'city': 'Warszawa',
            'zip': '1234',
            'country_id': self.env.ref('base.pl').id,
            'vat': 'PL2222222222',
        })
        self.env['res.partner.bank'].create({
            'account_number': '61109010140000071219812800',
            'partner_id': supplier.id,
        })
        move_other_partner = self.env['account.move'].create({
            'partner_id': supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 500,
            })]
        })
        move_other_partner.action_post()

        moves = self.pl_supplier_move + move + move_other_partner
        self._check_form_fields(moves)
        self._create_payments(moves)
        self.assertRecordValues(self.pl_supplier_move.reconciled_payment_ids + move.reconciled_payment_ids + move_other_partner.reconciled_payment_ids, [
            {
                'l10n_pl_bank_verification_status': 'valid',
                'l10n_pl_bank_verification_timestamp': datetime(2026, 1, 31, 10, 0, 0),
                'l10n_pl_bank_verification_request_id': 'AZERTYUIOP-01',
            },
            {
                'l10n_pl_bank_verification_status': 'not_required',
                'l10n_pl_bank_verification_timestamp': False,
                'l10n_pl_bank_verification_request_id': False,
            },
            {
                'l10n_pl_bank_verification_status': 'not_required',
                'l10n_pl_bank_verification_timestamp': False,
                'l10n_pl_bank_verification_request_id': False,
            },
        ])

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request')
    def test_register_payment_for_non_pl_supplier(self, _make_request_not_called_patched):
        supplier = self.env['res.partner'].create({
            'name': 'ODOO',
            'vat': 'BE0477472701',
            'country_id': self.env.ref('base.be').id,
        })
        move = self.env['account.move'].create({
            'partner_id': supplier.id,
            'move_type': 'in_invoice',
            'invoice_date': '2026-02-16',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id,
                'quantity': 1.0,
                'name': 'product test sale',
                'price_unit': 500,
            })]
        })
        move.action_post()
        self._check_form_fields(move)
        _make_request_not_called_patched.assert_not_called()

    @patch('odoo.addons.l10n_pl.wizard.account_payment_register.L10nPlAccountPaymentRegister._make_request')
    def test_register_payment_for_non_pl_company(self, _make_request_not_called_patched):
        self.company_data['company'].country_id = self.env.ref('base.be')
        self._check_form_fields(self.pl_supplier_move)
        _make_request_not_called_patched.assert_not_called()
