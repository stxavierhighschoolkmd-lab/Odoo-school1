# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_redsys.tests.common import RedsysCommon


@tagged("post_install", "-at_install")
class TestPaymentTransaction(RedsysCommon):
    def test_reference_uses_only_alphanumeric_chars(self):
        """The computed reference must be made of alphanumeric characters."""
        reference = self.env["payment.transaction"]._compute_reference(provider_code="redsys")
        self.assertTrue(reference.isalnum())

    def test_reference_length_is_between_9_and_12_chars(self):
        """The computed reference must be between 9 and 12 characters."""
        reference = self.env["payment.transaction"]._compute_reference(provider_code="redsys")
        self.assertTrue(9 <= len(reference) <= 12)

    def test_no_item_missing_from_merchant_parameters(self):
        """Test that all important items are present in the merchant parameters."""
        tx = self._create_transaction(flow="redirect")
        merchant_parameters = tx._redsys_prepare_merchant_parameters()
        converted_amount = payment_utils.to_minor_currency_units(tx.amount, tx.currency_id)
        self.assertEqual(merchant_parameters["DS_MERCHANT_AMOUNT"], str(converted_amount))
        self.assertEqual(merchant_parameters["DS_MERCHANT_CURRENCY"], tx.currency_id.iso_numeric)
        self.assertEqual(merchant_parameters["DS_MERCHANT_ORDER"], tx.reference)
        self.assertEqual(merchant_parameters["DS_MERCHANT_PAYMETHODS"], "C")  # credit card
        self.assertTrue("DS_MERCHANT_EMV3DS" in merchant_parameters)

    def test_payload_preparation_in_payment_with_tokenize(self):
        """Test that the payload is prepared correctly when the transaction is done with tokenize
        option enabled."""
        tx = self._create_transaction(flow="redirect", tokenize=True)

        payload = tx._redsys_prepare_merchant_parameters()
        expected_payload = {
            "DS_MERCHANT_COF_INI": "S",
            "DS_MERCHANT_COF_TYPE": "R",
            "DS_MERCHANT_IDENTIFIER": "REQUIRED",
        }
        self.assertDictEqual({k: payload[k] for k in expected_payload}, expected_payload)

    def test_payload_preparation_in_payment_with_token(self):
        """Test that the payload is prepared correctly when the transaction is done with token."""
        token = self._create_token()
        token.provider_ref = self.provider_ref
        tx = self._create_transaction(flow="redirect", token_id=token.id)

        payload = tx._redsys_prepare_merchant_parameters()
        expected_payload = {
            "DS_MERCHANT_COF_TYPE": "R",
            "DS_MERCHANT_DIRECTPAYMENT": "true",
            "DS_MERCHANT_EXCEP_SCA": "MIT",
            "DS_MERCHANT_IDENTIFIER": tx.token_id.provider_ref,
        }
        self.assertDictEqual({k: payload[k] for k in expected_payload}, expected_payload)

    def test_search_by_reference_returns_tx(self):
        """Test that the transaction is returned from the payment data."""
        tx = self._create_transaction("redirect")
        self.assertEqual(
            tx,
            self.env["payment.transaction"]._search_by_reference(
                "redsys", self.merchant_parameters
            ),
        )

    def test_extract_amount_data_returns_amount_and_currency(self):
        """Test that the amount and currency are returned from the payment data."""
        tx = self._create_transaction("redirect")
        amount_data = tx._extract_amount_data(self.merchant_parameters)
        self.assertDictEqual(
            amount_data, {"amount": self.amount, "currency_code": self.currency_euro.name}
        )

    def test_apply_updates_sets_payment_method(self):
        """Test that the payment method is updated according to the brand."""
        tx = self._create_transaction("redirect")
        tx._apply_updates(self.merchant_parameters)
        self.assertEqual(tx.payment_method_id, self.env.ref("payment.payment_method_visa"))

    def test_apply_updates_confirms_transaction(self):
        """Test that the transaction state is set to 'done' when the payment data indicate a
        successful payment."""
        tx = self._create_transaction("redirect")
        tx._apply_updates(self.merchant_parameters)
        self.assertEqual(tx.state, "done")

    @mute_logger("odoo.addons.payment_redsys.controllers.main")
    def test_process_tokenizes_transaction(self):
        """Ensure `_process` tokenizes the transaction when using tokenize option."""
        tx = self._create_transaction("redirect", tokenize=True)

        with (
            patch(
                "odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request",
                return_value=self.token_merchant_data,
            ),
            patch(
                "odoo.addons.payment.models.payment_transaction.PaymentTransaction._tokenize"
            ) as tokenize_mock,
        ):
            tx._process("redsys", self.token_merchant_data)

        self.assertEqual(tokenize_mock.call_count, 1)

    @mute_logger("odoo.addons.payment_redsys.controllers.main")
    def test_process_sets_transaction_done_with_existing_token(self):
        """Ensure `_process` sets the transaction to done when using an existing token."""
        token = self._create_token()
        token.provider_ref = self.provider_ref
        tx = self._create_transaction("redirect", token_id=token.id)

        with patch(
            "odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request",
            return_value=self.token_merchant_data,
        ):
            tx._process("redsys", self.token_merchant_data)

        self.assertEqual(tx.state, "done")
