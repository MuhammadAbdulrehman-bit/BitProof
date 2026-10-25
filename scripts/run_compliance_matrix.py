"""
CLI: Build and display the Compliance Matrix for a tender,
then request (or record) a named-approver sign-off.

Usage:
  python scripts/run_compliance_matrix.py --tender t03 --labels data/t03_labels.csv
  python scripts/run_compliance_matrix.py --tender t03 --labels data/t03_labels.csv --signoff
"""
import os
import sys
import csv
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.workflow.signoff_gate import ComplianceMatrixManager, SignoffGateBlockedError

STATUS_SYMBOLS = {
    "COMPLIANT":             "[PASS]",
    "PARTIAL":               "[PART]",
    "NON_COMPLIANT":         "[FAIL]",
    "CLARIFICATION_NEEDED":  "[?]  ",
}
RISK_SYMBOLS = {"HIGH": "[HIGH]", "MEDIUM": "[MED] ", "LOW": "[LOW] "}


def load_labels(labels_path: str):
    rows = []
    with open(labels_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def seed_matrix_from_labels(mgr: ComplianceMatrixManager, tender_id: str, labels):
    """Populate the compliance matrix from ground-truth labels.
    All items default to COMPLIANT (vendor fills in real responses later)."""
    for row in labels:
        c_ids = [c.strip() for c in row["candidate_ids"].split(";") if c.strip() and c.strip() != "PARSER_MISS"]
        if not c_ids:
            continue
        mgr.save_item(
            tender_id=tender_id,
            req_id=row["label_id"],
            sentence_id=c_ids[0],
            clause_text=row.get("exact_quote", "")[:300],
            section=row.get("section", "GENERAL"),
            req_type=row.get("type", "technical"),
            mandatory=row.get("mandatory", "yes"),
            knockout=row.get("knockout", "no"),
            compliance_status="COMPLIANT",     # default — UI/vendor can update
            vendor_response="",
            evidence_tags=[]
        )


def print_matrix(rows):
    print(f"\n{'ID':<20} {'TYPE':<12} {'KO':<4} {'RISK':<6} {'STATUS':<22} CLAUSE (truncated)")
    print("-" * 105)
    for r in rows:
        sym = STATUS_SYMBOLS.get(r["compliance_status"], "?")
        risk = RISK_SYMBOLS.get(r["risk_level"], "?")
        ko = "YES" if r["knockout"].lower() == "yes" else "no"
        clause = r["clause_text"][:60].replace("\n", " ")
        print(f"{r['req_id']:<20} {r['req_type']:<12} {ko:<4} {risk:<6} {sym} {r['compliance_status']:<19} {clause}")


def summarize(rows, tender_id: str):
    total = len(rows)
    compliant = sum(1 for r in rows if r["compliance_status"] == "COMPLIANT")
    partial = sum(1 for r in rows if r["compliance_status"] == "PARTIAL")
    non_comp = sum(1 for r in rows if r["compliance_status"] == "NON_COMPLIANT")
    high_risk = sum(1 for r in rows if r["risk_level"] == "HIGH")
    knockouts = sum(1 for r in rows if r["knockout"].lower() == "yes")
    ko_non_comp = sum(1 for r in rows if r["knockout"].lower() == "yes" and r["compliance_status"] != "COMPLIANT")

    print(f"\n{'='*55}")
    print(f"  COMPLIANCE MATRIX SUMMARY -- {tender_id.upper()}")
    print(f"{'='*55}")
    print(f"  Total Requirements : {total}")
    print(f"  [PASS] Compliant   : {compliant}")
    print(f"  [PART] Partial     : {partial}")
    print(f"  [FAIL] Non-Comply  : {non_comp}")
    print(f"  [HIGH] Risk Items  : {high_risk}")
    print(f"  Knockout Clauses   : {knockouts} ({ko_non_comp} non-compliant -- DISQUALIFYING)")
    print(f"{'='*55}\n")


def main():
    parser = argparse.ArgumentParser(description="BitProof Compliance Matrix & Sign-Off Gate")
    parser.add_argument("--tender", default="t03", help="Tender ID")
    parser.add_argument("--labels", default="data/t03_labels.csv", help="Labels CSV path")
    parser.add_argument("--db", default="data/compliance_matrix.db", help="SQLite DB path")
    parser.add_argument("--signoff", action="store_true", help="Interactively record a human sign-off")
    parser.add_argument("--verify", action="store_true", help="Check if export is authorized (gate check)")
    parser.add_argument("--reseed", action="store_true", help="Re-seed matrix from labels (clears existing)")
    args = parser.parse_args()

    mgr = ComplianceMatrixManager(db_path=args.db)

    # Seed if no items yet, or if --reseed
    existing = mgr.get_matrix(args.tender)
    if not existing or args.reseed:
        print(f"[*] Seeding compliance matrix from {args.labels} ...")
        labels = load_labels(args.labels)
        seed_matrix_from_labels(mgr, args.tender, labels)

    rows = mgr.get_matrix(args.tender)
    matrix_hash = mgr.calculate_matrix_hash(args.tender)

    print_matrix(rows)
    summarize(rows, args.tender)
    print(f"  Matrix SHA-256 fingerprint: {matrix_hash[:16]}...{matrix_hash[-8:]}")

    # Sign-off flow
    if args.signoff:
        print("\n[HUMAN SIGN-OFF REQUIRED]")
        current = mgr.get_signoff(args.tender)
        if current and current.get("status") == "APPROVED":
            current_hash = mgr.calculate_matrix_hash(args.tender)
            if current_hash == current["matrix_hash"]:
                print(f"  ✅ Already approved by {current['approver_name']} ({current['approver_role']}) at {current['signed_at']}")
                return
            else:
                print("  ⚠️  Previous approval is stale (matrix changed). Re-approval required.")

        name = input("  Approver full name  : ").strip()
        role = input("  Approver role/title : ").strip()
        email = input("  Approver email      : ").strip()
        comments = input("  Comments (optional) : ").strip()
        confirm = input(f"\n  Approve compliance matrix for '{args.tender}'? [yes/no]: ").strip().lower()

        if confirm == "yes":
            result = mgr.record_signoff(
                tender_id=args.tender,
                approver_name=name,
                approver_role=role,
                approver_email=email,
                comments=comments,
                status="APPROVED"
            )
            print(f"\n  ✅ SIGNED OFF by {result['approver_name']} at {result['signed_at']}")
            print(f"     Hash locked: {result['matrix_hash'][:16]}...")
        else:
            print("  ❌ Sign-off declined. Export remains locked.")

    # Gate verification
    if args.verify:
        print("\n[EXPORT AUTHORIZATION CHECK]")
        try:
            auth = mgr.verify_export_authorized(args.tender)
            print(f"  ✅ EXPORT AUTHORIZED")
            print(f"     Approver : {auth['approver_name']} ({auth['approver_role']})")
            print(f"     Signed   : {auth['signed_at']}")
            print(f"     Hash     : {auth['matrix_hash'][:16]}...")
        except SignoffGateBlockedError as e:
            print(f"  {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
