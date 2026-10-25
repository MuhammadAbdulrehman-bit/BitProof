import os
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extractors.claim_checker import ClaimChecker


def main():
    parser = argparse.ArgumentParser(description="Audit proposal text for vague claims and unsupported numbers.")
    parser.add_argument("--file", help="Path to a text/markdown proposal file.")
    parser.add_argument("--text", help="Raw string text to audit directly.")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        title = os.path.basename(args.file)
    elif args.text:
        content = args.text
        title = "Direct Input Text"
    else:
        # Default demo text showing both passed and failed claims
        title = "Sample Proposal Draft Section"
        content = """
        Our team provides industry-leading solutions with cutting-edge technology for public infrastructure.
        We have completed 12 enterprise cloud deployments across Pakistan [EVID-04].
        Our platform guarantees 99.9% uptime SLA 24x7 with seamless integration into citizen portals.
        The firm demonstrated an annual turnover of PKR 150 Million over the last 3 years [EVID-01].
        We have 5 years of verifiable experience in identity access management.
        """

    checker = ClaimChecker()
    report = checker.audit_proposal_section(title, content)

    print("=" * 70)
    print(f"  VAGUE CLAIM & FACT AUDIT REPORT: {report['section_title']}")
    print("=" * 70)
    print(f"Overall Gate Status:       {'[PASSED]' if report['passed'] else '[FAILED - REWRITE REQUIRED]'}")
    print(f"Evidence Tags Cited:       {report['total_evidence_citations']} {report['evidence_tags_cited']}")
    print(f"Vague Claims Detected:     {report['vague_claim_count']}")
    print(f"Unsupported Fact/Numbers:  {report['unsupported_metric_count']}")
    print("-" * 70)

    if report["vague_claims"]:
        print("\n[FLAGGED VAGUE BUZZWORDS]:")
        for v in report["vague_claims"]:
            print(f"  • Found '{v['word']}': {v['snippet']}")

    if report["unsupported_metrics"]:
        print("\n[UNSUPPORTED METRICS (Missing [EVID-xx] Tag)]:")
        for m in report["unsupported_metrics"]:
            print(f"  • Metrics {m['unsupported_metrics']} in sentence:")
            print(f"    \"{m['sentence']}\"")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
