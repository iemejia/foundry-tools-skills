#!/usr/bin/env python3
"""Unit tests for skills/azure-doc-intelligence/scripts/analyze.py."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "azure-doc-intelligence",
    "scripts", "analyze.py",
)
_spec = importlib.util.spec_from_file_location("analyze", _SCRIPT)
analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyze)
sys.modules["analyze"] = analyze


class TestBuildAnalyzeUrl(unittest.TestCase):
    def test_basic(self):
        url = analyze.build_analyze_url(
            "https://x.cognitiveservices.azure.com",
            "prebuilt-layout",
            "2024-11-30",
        )
        self.assertIn("/documentintelligence/documentModels/prebuilt-layout:analyze", url)
        self.assertIn("api-version=2024-11-30", url)

    def test_output_format(self):
        url = analyze.build_analyze_url(
            "https://x.cognitiveservices.azure.com",
            "prebuilt-read",
            "2024-11-30",
            output_format="markdown",
        )
        self.assertIn("outputContentFormat=markdown", url)

    def test_pages(self):
        url = analyze.build_analyze_url(
            "https://x.cognitiveservices.azure.com",
            "prebuilt-layout",
            "2024-11-30",
            pages="1-3,5",
        )
        self.assertIn("pages=1-3", url)

    def test_trailing_slash(self):
        url = analyze.build_analyze_url(
            "https://x.cognitiveservices.azure.com/",
            "prebuilt-read",
            "2024-11-30",
        )
        self.assertNotIn("//documentintelligence", url)


class TestFormatTables(unittest.TestCase):
    def test_simple_table(self):
        tables = [{
            "cells": [
                {"rowIndex": 0, "columnIndex": 0, "content": "Name"},
                {"rowIndex": 0, "columnIndex": 1, "content": "Age"},
                {"rowIndex": 1, "columnIndex": 0, "content": "Alice"},
                {"rowIndex": 1, "columnIndex": 1, "content": "30"},
            ]
        }]
        result = analyze._format_tables(tables)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["rows"][0], ["Name", "Age"])
        self.assertEqual(result[0]["rows"][1], ["Alice", "30"])

    def test_empty_table(self):
        result = analyze._format_tables([{"cells": []}])
        self.assertEqual(result[0]["rows"], [])

    def test_empty_list(self):
        result = analyze._format_tables([])
        self.assertEqual(result, [])


class TestParseArgs(unittest.TestCase):
    def test_file_input(self):
        args = analyze.parse_args(["--file", "doc.pdf"])
        self.assertEqual(args.file_path, "doc.pdf")
        self.assertIsNone(args.source_url)
        self.assertEqual(args.model, "prebuilt-layout")

    def test_url_input(self):
        args = analyze.parse_args(["--url", "https://example.com/doc.pdf"])
        self.assertIsNone(args.file_path)
        self.assertEqual(args.source_url, "https://example.com/doc.pdf")

    def test_all_args(self):
        args = analyze.parse_args([
            "--file", "x.pdf",
            "--model", "prebuilt-invoice",
            "--output-format", "markdown",
            "--pages", "1-2",
            "--poll-interval", "5",
            "--max-wait", "60",
            "--raw",
        ])
        self.assertEqual(args.model, "prebuilt-invoice")
        self.assertEqual(args.output_format, "markdown")
        self.assertEqual(args.pages, "1-2")
        self.assertEqual(args.poll_interval, 5)
        self.assertTrue(args.raw)


class TestMainMissingEndpoint(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_no_endpoint(self):
        rc = analyze.main(["--file", "x.pdf"])
        self.assertEqual(rc, 1)


class TestMainMissingKey(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://x.cognitiveservices.azure.com"},
        clear=True,
    )
    def test_no_key(self):
        rc = analyze.main(["--file", "x.pdf"])
        self.assertEqual(rc, 1)


class TestMainFileNotFound(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_DOCUMENT_INTELLIGENCE_API_KEY": "k",
        },
        clear=True,
    )
    def test_missing_file(self):
        rc = analyze.main(["--file", "/nonexistent/doc.pdf"])
        self.assertEqual(rc, 1)


class TestMainSuccess(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_DOCUMENT_INTELLIGENCE_API_KEY": "k",
        },
        clear=True,
    )
    @patch("analyze._poll_result")
    @patch("analyze._submit_analysis")
    def test_analyze_file(self, mock_submit, mock_poll):
        mock_submit.return_value = "https://x.cognitiveservices.azure.com/op/123"
        mock_poll.return_value = {
            "status": "succeeded",
            "analyzeResult": {
                "content": "Hello World",
                "pages": [{"pageNumber": 1}],
                "tables": [],
            },
        }
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-fake")
            tmpfile = f.name
        try:
            rc = analyze.main(["--file", tmpfile])
            self.assertEqual(rc, 0)
            mock_submit.assert_called_once()
            mock_poll.assert_called_once()
        finally:
            os.unlink(tmpfile)

    @patch.dict(
        os.environ,
        {
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_DOCUMENT_INTELLIGENCE_API_KEY": "k",
        },
        clear=True,
    )
    @patch("analyze._poll_result")
    @patch("analyze._submit_analysis")
    def test_analyze_url(self, mock_submit, mock_poll):
        mock_submit.return_value = "https://x.cognitiveservices.azure.com/op/456"
        mock_poll.return_value = {
            "status": "succeeded",
            "analyzeResult": {
                "content": "Invoice content",
                "pages": [{"pageNumber": 1}],
                "documents": [
                    {
                        "docType": "invoice",
                        "confidence": 0.95,
                        "fields": {
                            "InvoiceId": {"content": "INV-001"},
                            "InvoiceTotal": {"content": "$100.00"},
                        },
                    }
                ],
            },
        }
        rc = analyze.main([
            "--url", "https://example.com/invoice.pdf",
            "--model", "prebuilt-invoice",
        ])
        self.assertEqual(rc, 0)

    @patch.dict(
        os.environ,
        {
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://x.cognitiveservices.azure.com",
            "AZURE_DOCUMENT_INTELLIGENCE_API_KEY": "k",
        },
        clear=True,
    )
    @patch("analyze._poll_result")
    @patch("analyze._submit_analysis")
    def test_raw_output(self, mock_submit, mock_poll):
        mock_submit.return_value = "https://x.cognitiveservices.azure.com/op/789"
        mock_poll.return_value = {
            "status": "succeeded",
            "analyzeResult": {"content": "raw"},
        }
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-fake")
            tmpfile = f.name
        try:
            rc = analyze.main(["--file", tmpfile, "--raw"])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(tmpfile)


class TestHintForHttpError(unittest.TestCase):
    def test_401(self):
        hint = analyze._hint_for_http_error(401, "")
        self.assertIn("AZURE_DOCUMENT_INTELLIGENCE_API_KEY", hint)

    def test_404_model(self):
        hint = analyze._hint_for_http_error(404, "model not found")
        self.assertIn("prebuilt-read", hint)

    def test_413(self):
        hint = analyze._hint_for_http_error(413, "")
        self.assertIn("too large", hint)


if __name__ == "__main__":
    unittest.main()
