import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rules.ppra_rules import PPRARulesEngine


class TestPPRARulesEngine(unittest.TestCase):

    def setUp(self):
        self.engine = PPRARulesEngine()

    def test_total_rules_count(self):
        self.assertEqual(len(self.engine.rules), 12)

    def test_bid_security_limits(self):
        # 2% is compliant
        candidates = [{"sentence_id": "s1", "text": "The bidder must furnish a Bid Security equal to 2% of the bid price."}]
        results = self.engine.evaluate_tender(candidates)
        rule2 = next(r for r in results if r.rule_id == "PPRA-RULE-02")
        self.assertEqual(rule2.status, "COMPLIANT")
        self.assertIn("2.0%", rule2.findings)

        # 8% is a legal violation under PPRA
        candidates_bad = [{"sentence_id": "s2", "text": "The bidder must submit Bid Security of 8% in cash."}]
        results_bad = self.engine.evaluate_tender(candidates_bad)
        rule2_bad = next(r for r in results_bad if r.rule_id == "PPRA-RULE-02")
        self.assertEqual(rule2_bad.status, "VIOLATION")

    def test_fbr_atl_compliance(self):
        candidates = [{"sentence_id": "s1", "text": "Bidder must be active taxpayer listed on FBR Active Taxpayers List."}]
        results = self.engine.evaluate_tender(candidates)
        rule4 = next(r for r in results if r.rule_id == "PPRA-RULE-04")
        self.assertEqual(rule4.status, "COMPLIANT")

    def test_single_stage_two_envelope(self):
        candidates = [{"sentence_id": "s1", "text": "Procurement shall follow PPRA Rule 36(b) Single Stage Two Envelope Procedure."}]
        results = self.engine.evaluate_tender(candidates)
        rule1 = next(r for r in results if r.rule_id == "PPRA-RULE-01")
        self.assertEqual(rule1.status, "COMPLIANT")

    def test_liquidated_damages_cap(self):
        candidates = [{"sentence_id": "s1", "text": "Penalty of 0.1% per day up to maximum 10% of the contract value."}]
        results = self.engine.evaluate_tender(candidates)
        rule12 = next(r for r in results if r.rule_id == "PPRA-RULE-12")
        self.assertEqual(rule12.status, "COMPLIANT")
        self.assertIn("10%", rule12.findings)


if __name__ == "__main__":
    unittest.main()
