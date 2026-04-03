# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.payment_custom.tests.common import PaymentCustomCommon


@tagged("-at_install", "post_install")
class TestPaymentTransaction(PaymentCustomCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wire_transfer_provider = cls._prepare_provider(
            code="custom", update_values={"custom_mode": "wire_transfer"}
        )

    def test_matching_statement_line_confirms_wire_transfer_transaction(self):
        """Test that wire transfer transactions are confirmed when a matching bank statement line
        is found."""
        tx = self._create_transaction(
            flow="direct", reference="S00099", state="pending", currency_id=self.currency_usd.id
        )
        tx.provider_id = self.wire_transfer_provider
        tx.payment_method_id.code = "wire_transfer"
        absl = self.env["account.bank.statement.line"].create({
            "payment_ref": tx.reference,
            "partner_id": self.partner.id,
            "amount": tx.amount,
        })
        absl._cron_confirm_wire_transfer_transactions()
        self.assertEqual(tx.state, "done")

    def test_non_matching_statement_line_does_not_confirm_wire_transfer_transaction(self):
        """Test that wire transfer transactions are not confirmed with a non-matching bank statement
        line."""
        tx = self._create_transaction(
            flow="direct", reference="S00099", state="pending", currency_id=self.currency_usd.id
        )
        tx.payment_method_id.code = "wire_transfer"
        absl = self.env["account.bank.statement.line"].create({
            "payment_ref": "S00098",  # non-matching reference
            "partner_id": self.partner.id,
            "amount": tx.amount,
        })
        absl._cron_confirm_wire_transfer_transactions()
        self.assertEqual(tx.state, "pending")
