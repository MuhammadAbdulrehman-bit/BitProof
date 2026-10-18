import unittest
import os
import sys
import json

# Ensure src is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingest.pdf_parser import PDFSentenceParser


class TestPDFSentenceParser(unittest.TestCase):

    def setUp(self):
        self.parser = PDFSentenceParser()

    def test_decimal_and_currency_no_split(self):
        text = "The contractor shall pay Rs. 1.5 million within 30 days."
        splits = self.parser._split_segment_carefully(text)
        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0], text)

    def test_percentage_no_split(self):
        text = "Late submission penalty is 0.5% per week of delay."
        splits = self.parser._split_segment_carefully(text)
        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0], text)

    def test_cross_reference_no_split(self):
        text = "Evaluation shall be conducted as per clause 14.2 of the ITB 12.11 guidelines."
        splits = self.parser._split_segment_carefully(text)
        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0], text)

    def test_spec_code_with_colon_no_split(self):
        text = "All equipment must be fully compliant with spec DS-01:2026 standards."
        parts = self.parser._split_on_colon_clause(text)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0], text)

    def test_colon_followed_by_numbered_clause_splits(self):
        line = "Bidders must meet all of the following preliminary mandatory qualification criteria: 2.1 The bidder must be an active taxpayer."
        parts = self.parser._split_on_colon_clause(line)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "Bidders must meet all of the following preliminary mandatory qualification criteria:")
        self.assertEqual(parts[1], "2.1 The bidder must be an active taxpayer.")

    def test_colon_followed_by_bullet_and_clause_splits(self):
        line = "Proposals failing to satisfy any criterion shall be rejected: (cid:127) 2.1 The bidder must be active."
        parts = self.parser._split_on_colon_clause(line)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "Proposals failing to satisfy any criterion shall be rejected:")
        self.assertEqual(parts[1], "2.1 The bidder must be active.")

    def test_known_cid_replacement(self):
        text = "(cid:127) 2.1 The bidder must have valid NTN."
        cleaned = self.parser._clean_known_cids_and_track_unknown(text)
        self.assertIn("•", cleaned)
        self.assertNotIn("(cid:127)", cleaned)
        self.assertEqual(self.parser.unknown_cid_count, 0)

    def test_unknown_cid_tracking(self):
        self.parser.unknown_cid_count = 0
        self.parser.unknown_cids_found.clear()
        text = "Special character here (cid:999) inside text."
        cleaned = self.parser._clean_known_cids_and_track_unknown(text)
        self.assertIn("(cid:999)", cleaned)
        self.assertEqual(self.parser.unknown_cid_count, 1)
        self.assertIn("(cid:999)", self.parser.unknown_cids_found)

    def test_two_sentences_split_cleanly(self):
        text = "The vendor shall provide 3 years warranty. The system will maintain 99.9% uptime SLA."
        splits = self.parser._split_segment_carefully(text)
        self.assertEqual(len(splits), 2)
        self.assertEqual(splits[0], "The vendor shall provide 3 years warranty.")
        self.assertEqual(splits[1], "The system will maintain 99.9% uptime SLA.")

    def test_parser_version_and_sha256(self):
        self.assertEqual(self.parser.PARSER_VERSION, "v1.0")
        manifest_path = "data/tenders_manifest.csv"
        if os.path.exists(manifest_path):
            sha = self.parser.compute_sha256(manifest_path)
            self.assertEqual(len(sha), 64)

    def test_line_grouping_and_bbox(self):
        words = [
            {"text": "Hello", "x0": 54.0, "top": 100.0, "x1": 80.0, "bottom": 112.0},
            {"text": "World", "x0": 85.0, "top": 100.5, "x1": 120.0, "bottom": 112.5},
        ]
        lines = self.parser._group_words_into_lines(words, page_height=792.0, page_width=612.0)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["text"], "Hello World")
        self.assertEqual(lines[0]["bbox"], [54.0, 100.0, 120.0, 112.5])


if __name__ == "__main__":
    unittest.main()
