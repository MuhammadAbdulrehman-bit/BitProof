import unittest
from src.extractors.compound_splitter import verify_compound_split


class TestCompoundSplitter(unittest.TestCase):
    def setUp(self):
        self.parent_id = "sample_rfp_p02_s007"
        self.parent_text = (
            "3.8 The vendor will provide three (03) years of comprehensive on-site warranty, "
            "including all software updates, security patches, and 24x7 technical support."
        )

    def test_valid_split_passes_and_creates_deterministic_ids(self):
        """Valid split where all children are exact substrings."""
        splits = [
            {
                "type": "COMMERCIAL OBLIGATION",
                "text": "3.8 The vendor will provide three (03) years of comprehensive on-site warranty,"
            },
            {
                "type": "TECHNICAL SLA",
                "text": "including all software updates, security patches, and 24x7 technical support."
            }
        ]
        clauses, passed = verify_compound_split(self.parent_id, self.parent_text, splits)
        
        self.assertTrue(passed)
        self.assertEqual(len(clauses), 2)
        self.assertEqual(clauses[0]["id"], "sample_rfp_p02_s007a")
        self.assertEqual(clauses[1]["id"], "sample_rfp_p02_s007b")
        self.assertEqual(clauses[0]["status"], "VERIFIED_SUBSTRING")
        self.assertEqual(clauses[1]["status"], "VERIFIED_SUBSTRING")

    def test_hallucinated_child_rejects_and_falls_back_to_parent(self):
        """When an extractor hallucinates words not in the parent, the split MUST be rejected."""
        bad_splits = [
            {
                "type": "COMMERCIAL OBLIGATION",
                "text": "3.8 The vendor will provide three (03) years of comprehensive on-site warranty,"
            },
            {
                "type": "HALLUCINATED_REQUIREMENT",
                "text": "The vendor must also pay a penalty of PKR 500,000 for any SLA breach."  # NOT in parent!
            }
        ]
        clauses, passed = verify_compound_split(self.parent_id, self.parent_text, bad_splits)
        
        # Must fail and revert to unsplit parent
        self.assertFalse(passed)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0]["id"], self.parent_id)
        self.assertEqual(clauses[0]["text"], self.parent_text)
        self.assertEqual(clauses[0]["status"], "REVERTED_SUBSTRING_MISMATCH")
        self.assertFalse(clauses[0]["is_child"])

    def test_empty_split_falls_back_to_parent(self):
        """Empty candidates list safely returns unsplit parent."""
        clauses, passed = verify_compound_split(self.parent_id, self.parent_text, [])
        self.assertFalse(passed)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0]["id"], self.parent_id)


if __name__ == "__main__":
    unittest.main()
