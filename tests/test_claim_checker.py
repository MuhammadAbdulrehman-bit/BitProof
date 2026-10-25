import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extractors.claim_checker import ClaimChecker


class TestClaimChecker(unittest.TestCase):

    def setUp(self):
        self.checker = ClaimChecker()

    def test_vague_words_flagged(self):
        text = "We provide cutting-edge and industry-leading seamless software."
        flags = self.checker.check_vague_claims(text)
        flagged_words = [f["word"] for f in flags]
        self.assertIn("cutting-edge", flagged_words)
        self.assertIn("industry-leading", flagged_words)
        self.assertIn("seamless", flagged_words)

    def test_unsupported_metrics_flagged(self):
        # Has numbers (99.9%, 24x7) but no [EVID-xx] tag
        text = "Our platform guarantees 99.9% uptime on a 24x7 basis."
        unsupported = self.checker.check_facts_and_numbers(text)
        self.assertEqual(len(unsupported), 1)
        self.assertIn("99.9%", unsupported[0]["unsupported_metrics"])

    def test_supported_metrics_pass(self):
        # Has numbers AND [EVID-01] tag -> should PASS
        text = "Our platform guarantees 99.9% uptime on a 24x7 basis [EVID-02]."
        unsupported = self.checker.check_facts_and_numbers(text)
        self.assertEqual(len(unsupported), 0)

    def test_audit_section_gate(self):
        clean_text = "The firm completed 5 projects with PKR 150 Million revenue [EVID-01]."
        report_pass = self.checker.audit_proposal_section("Test Section", clean_text)
        self.assertTrue(report_pass["passed"])
        self.assertEqual(report_pass["vague_claim_count"], 0)
        self.assertEqual(report_pass["unsupported_metric_count"], 0)

        dirty_text = "We are an industry-leading firm with 15 years experience."
        report_fail = self.checker.audit_proposal_section("Test Section", dirty_text)
        self.assertFalse(report_fail["passed"])
        self.assertEqual(report_fail["vague_claim_count"], 1)
        self.assertEqual(report_fail["unsupported_metric_count"], 1)


if __name__ == "__main__":
    unittest.main()
