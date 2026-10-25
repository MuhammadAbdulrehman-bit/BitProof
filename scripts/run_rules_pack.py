import os
import sys
import csv
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rules.ppra_rules import PPRARulesEngine


def main():
    parser = argparse.ArgumentParser(description="Run Pakistan PPRA / e-PADS Rules Pack compliance audit.")
    parser.add_argument("--tender", required=True, help="Tender ID (e.g. sample_rfp, t03, t02, t04).")
    parser.add_argument("--data-dir", default="data", help="Directory containing candidates CSV.")
    args = parser.parse_args()

    candidates_path = os.path.join(args.data_dir, f"{args.tender}_candidates.csv")
    if not os.path.exists(candidates_path):
        print(f"Error: {candidates_path} not found!")
        sys.exit(1)

    candidates = []
    with open(candidates_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            candidates.append(row)

    print("=" * 80)
    print(f"  PAKISTAN PPRA & e-PADS COMPLIANCE AUDIT: {args.tender.upper()}")
    print(f"  Tender Candidates Analyzed: {len(candidates)}")
    print("=" * 80)

    engine = PPRARulesEngine()
    results = engine.evaluate_tender(candidates)

    status_icons = {
        "COMPLIANT": "[PASS]",
        "WARNING": "[WARN]",
        "VIOLATION": "[FAIL]",
        "NOT_APPLICABLE": "[N/A ]"
    }

    pass_count = sum(1 for r in results if r.status == "COMPLIANT")
    warn_count = sum(1 for r in results if r.status == "WARNING")
    fail_count = sum(1 for r in results if r.status == "VIOLATION")

    for r in results:
        icon = status_icons.get(r.status, "[ ? ]")
        print(f"\n{icon} {r.rule_id}: {r.name}")
        print(f"       Law:      {r.law_version}")
        print(f"       Clause:   {r.source_clause}")
        print(f"       Severity: {r.severity}")
        print(f"       Finding:  {r.findings}")
        if r.evidence_sentences:
            print(f"       Evidence ({len(r.evidence_sentences)} cited):")
            for ev in r.evidence_sentences:
                print(f"         • [{ev['sentence_id']}]: {ev['text'][:85]}...")

    print("\n" + "=" * 80)
    print(f"AUDIT SUMMARY: {pass_count} Passed | {warn_count} Warnings | {fail_count} Violations (Total 12 checks)")
    print("=" * 80)


if __name__ == "__main__":
    main()
