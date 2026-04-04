# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields
from odoo.exceptions import ValidationError

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestPosAccounting(AccountTestInvoicingCommon):

    @classmethod
    def _get_main_company(self):
        return self.company_data['company']

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.main_company = self._get_main_company()
        self.env.user.group_ids += self.env.ref('point_of_sale.group_pos_manager')
        self.env['res.users'].create({
            'name': 'A simple PoS man!',
            'login': 'pos_user',
            'password': 'pos_user',
            'group_ids': [(4, self.env.ref('point_of_sale.group_pos_manager').id)],
            'tz': 'Europe/Brussels',
        })

        # Create journals
        self.bank_journal = self.env['account.journal'].create({
            'name': 'Bank Test',
            'type': 'bank',
            'company_id': self.main_company.id,
            'code': 'BNK',
            'sequence': 10,
        })
        self.cash_journal = self.env['account.journal'].create({
            'name': 'Cash Test',
            'type': 'cash',
            'company_id': self.main_company.id,
            'code': 'CSH',
            'sequence': 10,
        })
        self.config_sale_journal = self.env['account.journal'].create({
            'name': 'PoS Sale',
            'type': 'sale',
            'code': 'POSS',
            'company_id': self.company.id,
            'sequence': 12,
        })

        # Accounts
        self.bank_outstanding_account = self.copy_account(
            self.inbound_payment_method_line.payment_account_id, {'name': 'Outstanding Bank'},
        )

        # Create payment methods
        self.cash_pm = self.env['pos.payment.method'].create({
            'name': 'Cash',
            'is_cash_count': True,
            'journal_id': self.cash_journal.id,
        })
        self.customer_pm = self.env['pos.payment.method'].create({
            'name': 'Customer Account',
            'split_transactions': True,
        })
        self.bank_pm = self.env['pos.payment.method'].create({
            'name': 'Bank',
            'is_cash_count': False,
            'journal_id': self.bank_journal.id,
            'outstanding_account_id': self.bank_outstanding_account.id,
        })

        if not self.cash_pm.account_bank_statement_id:
            error = "The cash payment method should have a bank statement linked to it."
            raise ValidationError(error)

        # Create taxes with different rates
        self.tax_6 = self.env['account.tax'].create({
            'name': 'Tax 6%',
            'amount_type': 'percent',
            'amount': 6,
        })
        self.tax_12 = self.env['account.tax'].create({
            'name': 'Tax 12%',
            'amount_type': 'percent',
            'amount': 12,
        })
        self.tax_21 = self.env['account.tax'].create({
            'name': 'Tax 21%',
            'amount_type': 'percent',
            'amount': 21,
        })

        # Create products with different tax configurations
        self.product_6 = self.env['product.product'].create({
            'name': 'Product 6%',
            'type': 'consu',
            'list_price': 10,
            'taxes_id': [(6, 0, [self.tax_6.id])],
            'available_in_pos': True,
        })
        self.product_12 = self.env['product.product'].create({
            'name': 'Product 12%',
            'type': 'consu',
            'list_price': 10,
            'taxes_id': [(6, 0, [self.tax_12.id])],
            'available_in_pos': True,
        })
        self.product_21 = self.env['product.product'].create({
            'name': 'Product 21%',
            'type': 'consu',
            'list_price': 10,
            'taxes_id': [(6, 0, [self.tax_21.id])],
            'available_in_pos': True,
        })
        self.product_6_12 = self.env['product.product'].create({
            'name': 'Product 6% + 12%',
            'type': 'consu',
            'list_price': 10,
            'taxes_id': [(6, 0, [self.tax_6.id, self.tax_12.id])],
            'available_in_pos': True,
        })
        self.product_6_12_21 = self.env['product.product'].create({
            'name': 'Product 6% + 12% + 21%',
            'type': 'consu',
            'list_price': 10,
            'taxes_id': [(6, 0, [self.tax_6.id, self.tax_12.id, self.tax_21.id])],
            'available_in_pos': True,
        })

        # Create different partners to use customer account
        self.partner_1 = self.env['res.partner'].create({
            'name': 'Partner 1',
        })
        self.partner_2 = self.env['res.partner'].create({
            'name': 'Partner 2',
        })

        # Create the main PoS configuration used in the tests
        self.pos_config = self.env['pos.config'].create({
            'name': 'PoS Config',
            'journal_id': self.config_sale_journal.id,
            'payment_method_ids': [
                (4, self.cash_pm.id),
                (4, self.customer_pm.id),
                (4, self.bank_pm.id),
            ],
        })

    def get_pos_session(self):
        return self.pos_config.current_session_id

    def create_pos_order(self, partner=None, payment_method=[], products=[]):
        order = self.env['pos.order'].create({
            'amount_total': 0,
            'amount_paid': 0,
            'amount_tax': 0,
            'amount_return': 0,
            'partner_id': partner.id if partner else None,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'company_id': self.env.company.id,
            'session_id': self.pos_config.current_session_id.id,
            'lines': [
                Command.create({
                    'product_id': product.id,
                    'price_unit': product.lst_price,
                    'price_subtotal': product.lst_price,
                    'tax_ids': [(6, 0, product.taxes_id.ids)],
                    'price_subtotal_incl': 0,
                }) for product in products
            ],
        })

        # Re-trigger prices computation
        order.lines._onchange_amount_line_all()
        order._compute_prices()

        # Split total amount into the different payment methods
        total_amount = order.amount_total
        splitted = total_amount / len(payment_method)
        order.payment_ids = [
            Command.create({
                'amount': splitted,
                'payment_method_id': pm.id,
            }) for pm in payment_method
        ]
        order._process_saved_order(False)
        return order

    def test_classic_sale_order(self):
        self.pos_config.open_ui()
        session = self.get_pos_session()
        session.set_opening_control(0, "")

        customer_order = self.create_pos_order(
            partner=self.partner_1,
            payment_method=[self.customer_pm],
            products=[self.product_6],
        )

        self.create_pos_order(
            payment_method=[self.cash_pm],
            products=[self.product_6],
        )

        self.create_pos_order(
            payment_method=[self.bank_pm],
            products=[self.product_6],
        )

        closing_data = session.get_closing_control_data()
        cash_details = closing_data['default_cash_details']
        expected_cashbox_amount = cash_details['payment_amount']
        session.close_session_from_ui(expected_cashbox_amount)
        self.assertEqual(session.state, 'closed')

        sale_move = session.move_ids
        bank_statement = self.cash_pm.account_bank_statement_id
        self.assertEqual(len(sale_move.line_ids), 4)                    # 3 payment_term + 1 product + 1 tax
        self.assertEqual(sale_move.amount_total, 21.2)                  # 10 + 6% tax * 2 orders (customer account order is not taken into account)
        self.assertEqual(sale_move.amount_tax, 1.2)                     # 6% tax on 30
        self.assertEqual(bank_statement.line_ids[0].amount, 10.6)       # 10 + 6% tax from the cash order
        self.assertEqual(bank_statement.is_complete, True)

        # Customer account invoice
        invoice = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('partner_id', '=', self.partner_1.id),
        ])
        self.assertEqual(invoice.amount_total, 10.6)                    # 10 + 6% tax from the customer account order
        self.assertEqual(invoice.amount_tax, 0.6)                       # 6% tax on 10
        self.assertEqual(invoice.amount_residual, 10.6)                 # Not yet paid
        self.assertEqual(invoice.amount_paid, 0.0)                      # Not yet paid
        self.assertEqual(customer_order.to_invoice, True)               # Forced to True since the order is paid with a customer account

    def test_cash_statement_line(self):
        self.pos_config.open_ui()
        session = self.get_pos_session()
        session.set_opening_control(0, "")

        # Cash payment of 10.6 (10 + 6% tax)
        self.create_pos_order(
            payment_method=[self.cash_pm],
            products=[self.product_6],
        )

        # Cash payment of 11.2 (10 + 12% tax)
        self.create_pos_order(
            payment_method=[self.cash_pm],
            products=[self.product_12],
        )

        # Cash payment of 12.0 (10 + 21% tax)
        self.create_pos_order(
            payment_method=[self.cash_pm],
            products=[self.product_21],
        )

        closing_data = session.get_closing_control_data()
        cash_details = closing_data['default_cash_details']
        expected_cashbox_amount = cash_details['payment_amount']
        session.close_session_from_ui(expected_cashbox_amount)

        bank_statement = self.cash_pm.account_bank_statement_id
        statement_lines = bank_statement.line_ids
        self.assertEqual(statement_lines[0].amount, 33.9)               # 10 + 6% tax + 10 + 12% tax + 10 + 21% tax

    def test_closing_entry_by_product(self):
        self.pos_config.use_closing_entry_by_product = True
        self.pos_config.open_ui()
        session = self.get_pos_session()
        session.set_opening_control(0, "")

        # Create a PoS order with 2 products with different taxes
        self.create_pos_order(
            partner=self.partner_1,
            payment_method=[self.cash_pm],
            products=[self.product_6, self.product_12],
        )

        closing_data = session.get_closing_control_data()
        cash_details = closing_data['default_cash_details']
        expected_cashbox_amount = cash_details['payment_amount']
        session.close_session_from_ui(expected_cashbox_amount)

        sale_move = session.move_ids
        self.assertEqual(len(sale_move.line_ids), 5)                    # 1 payment_term + 2 product + 2 tax
        product_lines = sale_move.line_ids.filtered(
            lambda line: line.display_type == 'product',
        )
        tax_lines = sale_move.line_ids.filtered(
            lambda line: line.display_type == 'tax',
        )
        self.assertEqual(product_lines[0].product_id, self.product_6)   # First product line should be for product with 6% tax
        self.assertEqual(product_lines[1].product_id, self.product_12)  # Second product line should be for product with 12% tax
        self.assertEqual(tax_lines[0].tax_ids.ids, [self.tax_6.id])     # First tax line should be for 6% tax
        self.assertEqual(tax_lines[1].tax_ids.ids, [self.tax_12.id])    # Second tax line should be for 12% tax

    def test_separate_invoicing_pos_order(self):
        self.pos_config.open_ui()
        session = self.get_pos_session()
        session.set_opening_control(0, "")

        # Create a PoS order with 2 payment methods
        # (customer account + cash)
        pos_order = self.create_pos_order(
            partner=self.partner_1,
            payment_method=[self.customer_pm, self.cash_pm],
            products=[self.product_6],
        )

        closing_data = session.get_closing_control_data()
        cash_details = closing_data['default_cash_details']
        expected_cashbox_amount = cash_details['payment_amount']
        session.close_session_from_ui(expected_cashbox_amount)

        # Check that the invoice is correctly created with the customer
        # account payment method
        invoice = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('partner_id', '=', self.partner_1.id),
        ])
        self.assertEqual(pos_order.account_move, invoice)               # Invoice should be linked to the PoS order
        self.assertEqual(invoice.amount_total, 10.6)                    # 10 + 6% tax from the customer account order
        self.assertEqual(invoice.amount_tax, 0.6)                       # 6% tax on 10
        self.assertEqual(invoice.amount_residual, 5.3)                  # Customer account part isn't yet paid, but cash part is paid

        # Check each account.move.line of the invoice to ensure that the
        # cash payment line is reconciled with the correct invoice line
        # (in case of multiple tax lines for example)
        payment_terms = invoice.line_ids.filtered(
            lambda line: line.display_type == 'payment_term',
        )
        cash_payment = payment_terms[0]
        customer_payment = payment_terms[1]
        self.assertEqual(cash_payment.amount_currency, 5.3)             # Cash part of the payment
        self.assertEqual(customer_payment.amount_currency, 5.3)         # Customer account part of the payment
        self.assertEqual(cash_payment.reconciled, True)                 # Cash part
        self.assertEqual(customer_payment.reconciled, False)            # Customer account part

        product_line = invoice.line_ids.filtered(
            lambda line: line.product_id == self.product_6,
        )
        product_taxes = self.product_6.taxes_id.ids
        self.assertEqual(product_line.tax_ids.ids, product_taxes)       # Taxes should be correctly copied on the invoice line
        self.assertEqual(product_line.amount_currency, -10.0)           # Product line should be at 10 (without taxes)
        self.assertEqual(product_line.credit, 10.0)                     # Product line should be a credit of 10 (without taxes)

        tax_lines = invoice.line_ids.filtered(
            lambda line: line.display_type == 'tax',
        )
        self.assertEqual(tax_lines.amount_currency, -0.6)
