import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.workflow.signoff_gate import ComplianceMatrixManager, SignoffGateBlockedError


class TestSignoffGate(unittest.TestCase):

    def setUp(self):
        self.mgr = ComplianceMatrixManager(db_path=":memory:")
        # Seed one requirement into the matrix
        self.mgr.save_item(
            tender_id="t03",
            req_id="t03_req_01",
            sentence_id="t03_p01_s003",
            clause_text="Vendor shall install Modbus Repeaters for 13 tanks.",
            section="GENERAL",
            req_type="technical",
            mandatory="yes",
            knockout="no",
            compliance_status="COMPLIANT",
            vendor_response="We have installed Modbus Repeaters per spec.",
            evidence_tags=["EVID-01"]
        )

    def test_risk_auto_set_low_when_compliant(self):
        rows = self.mgr.get_matrix("t03")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["risk_level"], "LOW")
        self.assertEqual(rows[0]["compliance_status"], "COMPLIANT")

    def test_risk_auto_set_high_on_knockout_non_compliant(self):
        self.mgr.save_item(
            tender_id="t03",
            req_id="t03_req_ko",
            sentence_id="t03_p06_s001",
            clause_text="Bid security must be submitted with the tender.",
            req_type="eligibility",
            mandatory="yes",
            knockout="yes",
            compliance_status="NON_COMPLIANT",
        )
        rows = {r["req_id"]: r for r in self.mgr.get_matrix("t03")}
        self.assertEqual(rows["t03_req_ko"]["risk_level"], "HIGH")

    def test_signoff_blocked_with_no_record(self):
        with self.assertRaises(SignoffGateBlockedError) as ctx:
            self.mgr.verify_export_authorized("t03")
        self.assertIn("GATE BLOCKED", str(ctx.exception))
        self.assertIn("No sign-off recorded", str(ctx.exception))

    def test_signoff_approved_unlocks_export(self):
        result = self.mgr.record_signoff(
            tender_id="t03",
            approver_name="Ahmed Raza",
            approver_role="Bid Director",
            approver_email="ahmed@vendorco.pk",
            comments="All requirements reviewed and compliant."
        )
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["approver_name"], "Ahmed Raza")
        # Export should now be authorized
        auth = self.mgr.verify_export_authorized("t03")
        self.assertTrue(auth["authorized"])
        self.assertEqual(auth["approver_name"], "Ahmed Raza")

    def test_signoff_invalidated_after_matrix_change(self):
        # Sign off
        self.mgr.record_signoff(
            tender_id="t03",
            approver_name="Ahmed Raza",
            approver_role="Bid Director"
        )
        # Now modify the matrix — this should break the hash
        self.mgr.save_item(
            tender_id="t03",
            req_id="t03_req_01",
            sentence_id="t03_p01_s003",
            clause_text="Vendor shall install Modbus Repeaters for 13 tanks.",
            compliance_status="PARTIAL",  # Changed!
            vendor_response="Partial delivery only."
        )
        with self.assertRaises(SignoffGateBlockedError) as ctx:
            self.mgr.verify_export_authorized("t03")
        self.assertIn("modified after approval", str(ctx.exception))

    def test_matrix_hash_deterministic(self):
        h1 = self.mgr.calculate_matrix_hash("t03")
        h2 = self.mgr.calculate_matrix_hash("t03")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex

    def test_no_export_without_approver_even_with_items(self):
        """Compliance items exist but no human signed off — export must be blocked."""
        with self.assertRaises(SignoffGateBlockedError):
            self.mgr.verify_export_authorized("t03")


if __name__ == "__main__":
    unittest.main()
