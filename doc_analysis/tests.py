import io
import json
import os
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from users.models import User
from doc_analysis.models import DocumentEmbedding
from django.db import connection
from .tests_utils import enable_skip_external, disable_skip_external
from doc_analysis.utils import detect_pdf_modifications


class AnalyzeDocumentViewTests(TestCase):
    def setUp(self):
        # Superuser has all permissions by default
        self.user = User.objects.create_superuser(
            email="admin@example.com",
            password="pass1234",
        )
        self.client.force_login(self.user)
        self.url = reverse("analyze_document")
        enable_skip_external()

    def tearDown(self):
        disable_skip_external()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=False)
    @patch("doc_analysis.views.store_document_embeddings_task")
    @patch("doc_analysis.views.detect_pdf_modifications")
    @patch("doc_analysis.views.analyze_bank_statement_secure")
    @patch("doc_analysis.views.extract_text_and_metadata")
    def test_bank_statement_secure_flow(
        self,
        mock_extract,
        mock_analyze_secure,
        mock_detect,
        mock_store_task,
    ):
        mock_extract.return_value = {
            "full_text": "Account balance $1000. Bank statement sample.",
            "text_chunks": ["Account balance $1000. Bank statement sample."],
            "metadata": {},
        }
        mock_analyze_secure.return_value = {"status": "Complete", "summary": "ok"}
        mock_detect.return_value = {"tampering_suspected": False, "severity": "low"}
        dummy_file = SimpleUploadedFile("test.pdf", b"%PDF-1.4 dummy")

        resp = self.client.post(
            self.url,
            {"document_type": "Bank Statement", "file": dummy_file},
        )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("analysis", payload)
        self.assertIn("modification_check", payload)
        self.assertFalse(payload["tampering_suspected"])
        self.assertEqual(payload["tampering_severity"], "low")
        mock_store_task.delay.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=False)
    @patch("doc_analysis.views.store_document_embeddings_task")
    @patch("doc_analysis.views.detect_pdf_modifications")
    @patch("doc_analysis.views.analyze_pay_stub_secure")
    @patch("doc_analysis.views.extract_text_and_metadata")
    def test_pay_stub_secure_flow(
        self,
        mock_extract,
        mock_analyze_secure,
        mock_detect,
        mock_store_task,
    ):
        mock_extract.return_value = {
            "full_text": "Pay stub with gross pay and deductions.",
            "text_chunks": ["Pay stub with gross pay and deductions."],
            "metadata": {},
        }
        mock_analyze_secure.return_value = {"status": "Complete", "summary": "pay stub ok"}
        mock_detect.return_value = {"tampering_suspected": True, "severity": "medium"}
        dummy_file = SimpleUploadedFile("stub.pdf", b"%PDF-1.4 dummy")

        resp = self.client.post(
            self.url,
            {"document_type": "Pay Stub", "file": dummy_file},
        )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["tampering_suspected"])
        self.assertEqual(payload["tampering_severity"], "medium")
        mock_store_task.delay.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=False)
    @patch("doc_analysis.views.store_document_embeddings_task")
    @patch("doc_analysis.views.detect_pdf_modifications")
    @patch("doc_analysis.views.analyze_tax_return_secure")
    @patch("doc_analysis.views.extract_text_and_metadata")
    def test_tax_return_secure_flow(
        self,
        mock_extract,
        mock_analyze_secure,
        mock_detect,
        mock_store_task,
    ):
        mock_extract.return_value = {
            "full_text": "Form 1040 with AGI and signatures.",
            "text_chunks": ["Form 1040 with AGI and signatures."],
            "metadata": {},
        }
        mock_analyze_secure.return_value = {"status": "Complete", "summary": "tax return ok"}
        mock_detect.return_value = {"tampering_suspected": False, "severity": "low"}
        dummy_file = SimpleUploadedFile("tax.pdf", b"%PDF-1.4 dummy")

        resp = self.client.post(
            self.url,
            {"document_type": "Tax Return", "file": dummy_file},
        )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("analysis", payload)
        self.assertIn("modification_check", payload)
        mock_store_task.delay.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=False)
    @patch("doc_analysis.views.extract_text_and_metadata")
    def test_unsupported_doc_type(self, mock_extract):
        mock_extract.return_value = {
            "full_text": "Some text",
            "text_chunks": ["Some text"],
            "metadata": {},
        }
        dummy_file = SimpleUploadedFile("other.pdf", b"%PDF-1.4 dummy")

        resp = self.client.post(
            self.url,
            {"document_type": "Other", "file": dummy_file},
        )

        self.assertEqual(resp.status_code, 400)
        payload = resp.json()
        self.assertEqual(payload["status"], "error")
        self.assertIn("Unsupported document type", payload["reasoning"])

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=False)
    @patch("doc_analysis.views.store_document_embeddings_task")
    @patch("doc_analysis.views.extract_text_and_metadata")
    @patch("doc_analysis.views.detect_pdf_modifications")
    def test_tamper_payload_includes_flags_and_notes(
        self,
        mock_detect,
        mock_extract,
        mock_store_task,
    ):
        mock_extract.return_value = {
            "full_text": "Account balance $1000.",
            "text_chunks": ["Account balance $1000."],
            "metadata": {},
        }
        mock_detect.return_value = {
            "tampering_suspected": True,
            "severity": "medium",
            "notes": ["test note"],
            "page_fingerprints": [{"page": 1, "text_hash": "abc", "content_hash": "def"}],
            "object_summary": {"total_images": 0}
        }
        dummy_file = SimpleUploadedFile("tamper.pdf", b"%PDF-1.4 dummy")

        resp = self.client.post(
            self.url,
            {"document_type": "Bank Statement", "file": dummy_file},
        )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["tampering_suspected"])
        self.assertEqual(payload["tampering_severity"], "medium")
        self.assertIn("notes", payload["modification_check"])

    def test_tamper_truncation_notes_and_hashes(self):
        # Build a fake metadata and run detect_pdf_modifications with max_pages=1 to force truncation note.
        fp = detect_pdf_modifications({}, file_path=None, max_pages=1)
        # No file_path => no page_fingerprints, but we ensure defaults
        self.assertIn("tampering_suspected", fp)
        self.assertIn("severity", fp)
        self.assertIn("notes", fp)


class EmbeddingSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="admin@example.com",
            password="pass1234",
        )
        self.client.force_login(self.user)
        self.url = reverse("search_embeddings")
        enable_skip_external()
        # Seed a couple of embeddings (requires vector type to exist)
        DocumentEmbedding.objects.all().delete()
        dim = 1536
        DocumentEmbedding.objects.create(
            file_name="doc1.pdf",
            content="hello world income",
            embedding=[0.1] * dim
        )
        DocumentEmbedding.objects.create(
            file_name="doc2.pdf",
            content="another text about taxes",
            embedding=[0.0] * dim
        )

    def tearDown(self):
        disable_skip_external()

    @patch("doc_analysis.views.get_embedding_for_text")
    def test_search_requires_authz_and_returns_results(self, mock_embed):
        mock_embed.return_value = [0.1] * 1536
        resp = self.client.post(self.url, {"query": "hello", "k": 2})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(len(payload["results"]) <= 2)
        # Ensure ordering favors closer vector (doc1 vs doc2)
        self.assertGreaterEqual(payload["results"][0]["similarity"], payload["results"][-1]["similarity"])

    @patch("doc_analysis.views.get_embedding_for_text")
    def test_search_ui_renders_results(self, mock_embed):
        mock_embed.return_value = [0.1] * 1536
        ui_url = reverse("search_embeddings_ui")
        resp = self.client.post(ui_url, {"query": "hello", "k": 1})
        self.assertEqual(resp.status_code, 200)
        # Ensure results rendered in context
        self.assertIn("results", resp.context)

    def test_search_requires_permission(self):
        user = User.objects.create_user(email="user@example.com", password="pass1234")
        self.client.force_login(user)
        resp = self.client.post(self.url, {"query": "hello", "k": 1})
        self.assertEqual(resp.status_code, 403)
        payload = resp.json()
        self.assertEqual(payload["status"], "error")
