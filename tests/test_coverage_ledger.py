import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ledger.coverage_ledger import CoverageLedger, CoverageGateError

class TestCoverageLedger(unittest.TestCase):

    def setUp(self):
        self.ledger = CoverageLedger(db_path=":memory:")

    def test_ledger_insert_and_retrieve(self):
        self.ledger.record_sentence(
            sentence_id="t03_p01_s001",
            tender_id="t03",
            page=1,
            section="GENERAL",
            text="Pakistan State Oil Tender.",
            classification="background"
        )
        rows = self.ledger.get_tender_ledger("t03")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sentence_id"], "t03_p01_s001")
        self.assertEqual(rows[0]["classification"], "background")

    def test_coverage_gate_failure_on_unclassified(self):
        items = [
            {"sentence_id": "t03_p01_s001", "tender_id": "t03", "text": "A", "classification": "requirement"},
            {"sentence_id": "t03_p01_s002", "tender_id": "t03", "text": "B", "classification": "unclassified"}
        ]
        self.ledger.record_batch(items)
        with self.assertRaises(CoverageGateError) as ctx:
            self.ledger.verify_coverage_gate("t03")
        self.assertIn("has 1 unclassified sentences", str(ctx.exception))

    def test_coverage_gate_success_100_percent(self):
        items = [
            {"sentence_id": "t03_p01_s001", "tender_id": "t03", "text": "A", "classification": "requirement"},
            {"sentence_id": "t03_p01_s002", "tender_id": "t03", "text": "B", "classification": "background"},
            {"sentence_id": "t03_p01_s003", "tender_id": "t03", "text": "C", "classification": "ignored"}
        ]
        self.ledger.record_batch(items)
        stats = self.ledger.verify_coverage_gate("t03")
        self.assertTrue(stats["gate_passed"])
        self.assertEqual(stats["coverage_percent"], 100.0)
        self.assertEqual(stats["requirements"], 1)
        self.assertEqual(stats["background"], 1)
        self.assertEqual(stats["ignored"], 1)

if __name__ == "__main__":
    unittest.main()
