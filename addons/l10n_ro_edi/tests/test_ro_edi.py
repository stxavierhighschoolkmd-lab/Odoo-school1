from unittest.mock import patch

from odoo.addons.l10n_ro_edi.tests.common import TestROEdiCommon
from odoo.tests import tagged


@tagged("post_install_l10n", "-at_install", "post_install")
class TestEdiSPV(TestROEdiCommon):
    """Tests for invoice re-send behavior and index management."""

    def test_resend_without_index_clears_edi_index(self):
        """
        1. Send invoice → SPV returns error WITH key_loading 'ABC123'
        2. Re-send invoice → SPV returns error WITHOUT key_loading
        3. Assert l10n_ro_edi_index is False
        """
        invoice = self.create_invoice()

        # Step 1: first send fails but SPV returns an index
        self.send_invoice_with_mock(
            invoice,
            {
                "error": "XML validation failed",
                "key_loading": "ABC123",
            },
        )

        self.assertEqual(invoice.l10n_ro_edi_index, "ABC123")
        self.assertEqual(invoice.l10n_ro_edi_document_ids.sorted()[:1].state, "invoice_sending_failed")
        first_doc = invoice.l10n_ro_edi_document_ids.sorted()[:1]

        # Step 2: re-send fails and SPV does NOT return an index
        self.send_invoice_with_mock(
            invoice,
            {
                "error": "SPV internal server error",
            },
        )

        self.assertFalse(invoice.l10n_ro_edi_index)
        # The failed document was updated, not a new one created
        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 1)
        self.assertEqual(invoice.l10n_ro_edi_document_ids.sorted()[:1], first_doc)
        self.assertIn("SPV internal server error", first_doc.message)

    def test_resend_with_new_index_updates_edi_index(self):
        """
        1. Send invoice → SPV returns error WITH key_loading 'ABC123'
        2. Re-send invoice → SPV returns error WITH key_loading 'XYZ789'
        3. Assert l10n_ro_edi_index is 'XYZ789'
        """
        invoice = self.create_invoice()

        self.send_invoice_with_mock(
            invoice,
            {
                "error": "XML validation failed",
                "key_loading": "ABC123",
            },
        )

        self.assertEqual(invoice.l10n_ro_edi_index, "ABC123")

        self.send_invoice_with_mock(
            invoice,
            {
                "error": "XML schema error",
                "key_loading": "XYZ789",
            },
        )

        self.assertEqual(invoice.l10n_ro_edi_index, "XYZ789")
        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 1)

    def test_resend_success_after_failure(self):
        """
        1. Send invoice → SPV returns error without index
        2. Re-send invoice → SPV returns success with key_loading 'NEW_INDEX'
        3. Assert l10n_ro_edi_index is 'NEW_INDEX' and state is 'invoice_sent'
        """
        invoice = self.create_invoice()

        self.send_invoice_with_mock(
            invoice,
            {
                "error": "SPV unavailable",
            },
        )

        self.assertFalse(invoice.l10n_ro_edi_index)
        self.assertEqual(invoice.l10n_ro_edi_document_ids.sorted()[:1].state, "invoice_sending_failed")

        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "NEW_INDEX",
            },
        )

        self.assertEqual(invoice.l10n_ro_edi_index, "NEW_INDEX")
        self.assertEqual(invoice.l10n_ro_edi_state, "invoice_sent")
        # 2 documents: the old failed (history) + the new sent
        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 2)
        self.assertEqual(invoice.l10n_ro_edi_document_ids.sorted()[:1].state, "invoice_sent")

    def test_resend_precheck_clears_index(self):
        """
        1. Send invoice → SPV returns success with key_loading 'ABC123'
        2. Simulate fetch failure → document becomes failed
        3. Remove access token → pre-check fails on re-send
        4. Assert l10n_ro_edi_index is False
        """
        invoice = self.create_invoice()

        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "ABC123",
            },
        )

        self.assertEqual(invoice.l10n_ro_edi_index, "ABC123")

        # Simulate fetch failure
        invoice.l10n_ro_edi_document_ids.sorted()[:1].write({"state": "invoice_sending_failed"})

        # Remove token to trigger pre-check failure
        self.company_data["company"].l10n_ro_edi_access_token = False
        invoice._l10n_ro_edi_send_invoice(xml_data=b"<xml>test</xml>")

        self.assertFalse(invoice.l10n_ro_edi_index)
        self.assertIn("access token", invoice.l10n_ro_edi_document_ids.sorted()[:1].message)

    def test_fetch_error_updates_document(self):
        """
        1. Send invoice → success
        2. Fetch status → error
        3. Assert document is updated to sending_failed (not a new one created)
        """
        invoice = self.create_invoice()

        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "ABC123",
            },
        )

        sent_doc = invoice.l10n_ro_edi_document_ids.sorted()[:1]
        self.assertEqual(sent_doc.state, "invoice_sent")

        self.fetch_status_with_mock(
            invoice,
            {
                "error": "XML validation failed by SPV",
                "state_status": "nok",
            },
        )

        self.assertEqual(sent_doc.state, "invoice_sending_failed")
        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 1)

    def test_fetch_still_processing_does_nothing(self):
        """
        1. Send invoice → success
        2. Fetch status → {} (still processing)
        3. Assert nothing changed
        """
        invoice = self.create_invoice()

        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "ABC123",
            },
        )

        self.fetch_status_with_mock(invoice, {})

        self.assertEqual(invoice.l10n_ro_edi_index, "ABC123")
        self.assertEqual(invoice.l10n_ro_edi_state, "invoice_sent")
        self.assertEqual(invoice.l10n_ro_edi_document_ids.sorted()[:1].state, "invoice_sent")

    def test_fetch_validated_updates_document(self):
        """
        1. Send invoice → success
        2. Fetch status → success with key_download
        3. Download → success with signature
        4. Assert document is updated to validated
        """
        invoice = self.create_invoice()

        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "ABC123",
            },
        )

        sent_doc = invoice.l10n_ro_edi_document_ids.sorted()[:1]

        with (
            patch.object(
                self.env.registry.get("l10n_ro_edi.document"),
                "_request_ciusro_fetch_status",
                return_value={
                    "key_download": "DL_KEY_1",
                    "state_status": "ok",
                },
            ),
            patch.object(
                self.env.registry.get("l10n_ro_edi.document"),
                "_request_ciusro_download_answer",
                return_value={
                    "key_signature": "sig_123",
                    "key_certificate": "cert_123",
                    "attachment_raw": b"<xml>signature</xml>",
                },
            ),
        ):
            invoice._l10n_ro_edi_fetch_invoice_sent_documents()

        self.assertEqual(sent_doc.state, "invoice_validated")
        self.assertEqual(invoice.l10n_ro_edi_state, "invoice_validated")
        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 1)

    def test_fetch_after_resend_preserves_history(self):
        """
        1. Send invoice → error (creates failed doc)
        2. Re-send → success (creates sent doc, failed stays as history)
        3. Fetch status → validated
        4. Assert 2 documents: old failed (history) + updated validated
        """
        invoice = self.create_invoice()

        # Step 1: first send fails
        self.send_invoice_with_mock(
            invoice,
            {
                "error": "SPV unavailable",
            },
        )

        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 1)

        # Step 2: re-send succeeds
        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "NEW_INDEX",
            },
        )

        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 2)
        sent_doc = invoice.l10n_ro_edi_document_ids.filtered(lambda d: d.state == "invoice_sent")[:1]

        # Step 3: fetch → validated
        with (
            patch.object(
                self.env.registry.get("l10n_ro_edi.document"),
                "_request_ciusro_fetch_status",
                return_value={
                    "key_download": "DL_KEY_1",
                    "state_status": "ok",
                },
            ),
            patch.object(
                self.env.registry.get("l10n_ro_edi.document"),
                "_request_ciusro_download_answer",
                return_value={
                    "key_signature": "sig_new",
                    "key_certificate": "cert_new",
                    "attachment_raw": b"<xml>signature</xml>",
                },
            ),
        ):
            invoice._l10n_ro_edi_fetch_invoice_sent_documents()

        # 2 documents: old failed (history) + validated
        self.assertEqual(len(invoice.l10n_ro_edi_document_ids), 2)
        self.assertEqual(sent_doc.state, "invoice_validated")
        self.assertEqual(invoice.l10n_ro_edi_state, "invoice_validated")

    def test_synchronize_filters_already_processed_refusal(self):
        invoice = self.create_invoice()

        # Step 1: send with index
        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "ABC123",
            },
        )
        self.assertEqual(invoice.l10n_ro_edi_index, "ABC123")
        self.assertEqual(invoice.l10n_ro_edi_state, "invoice_sent")

        # Step 2: fetch → refused
        self.fetch_status_with_mock(
            invoice,
            {
                "error": "XML validation failed by SPV",
                "state_status": "nok",
            },
        )
        self.assertEqual(invoice.l10n_ro_edi_document_ids.sorted()[:1].state, "invoice_sending_failed")

        # Step 3: reset to draft and re-send
        invoice.button_draft()
        invoice.action_post()

        self.send_invoice_with_mock(
            invoice,
            {
                "key_loading": "DEF456",
            },
        )
        self.assertEqual(invoice.l10n_ro_edi_state, "invoice_sent")

        # Simulate index was lost (server timeout before saving)
        invoice.l10n_ro_edi_index = False

        # Step 4: synchronize brings 2 messages
        self.synchronize_with_mock(
            {
                "sent_invoices_accepted_messages": [
                    {
                        "id_solicitare": "DEF456",
                        "id": "002",
                        "answer": {
                            "invoice": {"name": invoice.name},
                            "signature": {
                                "key_signature": "sig_def",
                                "key_certificate": "cert_def",
                                "attachment_raw": b"<xml>def</xml>",
                            },
                        },
                    },
                ],
                "sent_invoices_refused_messages": [
                    {
                        "id_solicitare": "ABC123",
                        "id": "001",
                        "answer": {
                            "invoice": {
                                "error": "Invalid XML structure",
                            },
                        },
                    },
                ],
                "received_bills_messages": [],
            }
        )

        invoice.invalidate_recordset()
        self.assertEqual(invoice.l10n_ro_edi_index, "DEF456")
        self.assertEqual(invoice.l10n_ro_edi_state, "invoice_validated")
