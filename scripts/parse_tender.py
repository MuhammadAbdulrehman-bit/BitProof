import argparse
import os
import sys

# Ensure src is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingest.pdf_parser import PDFSentenceParser


def main():
    parser = argparse.ArgumentParser(description="Parse an RFP PDF into section-tagged sentences with deterministic IDs, bboxes, and element types.")
    parser.add_argument("--pdf", required=True, help="Path to the PDF file.")
    parser.add_argument("--id", required=True, help="Tender ID (e.g. sample_rfp, t03).")
    parser.add_argument("--out", default=None, help="Path to output CSV (default: data/<id>_candidates.csv).")
    parser.add_argument("--top-margin", type=float, default=40.0, help="Points to trim from top of page for headers.")
    parser.add_argument("--bottom-margin", type=float, default=40.0, help="Points to trim from bottom for footers.")

    args = parser.parse_args()

    output_path = args.out or os.path.join("data", f"{args.id}_candidates.csv")

    print(f"==================================================")
    print(f"--> Parsing PDF:        {args.pdf}")
    print(f"--> Tender ID:          {args.id}")
    print(f"--> Output:             {output_path}")

    ingestor = PDFSentenceParser(top_margin=args.top_margin, bottom_margin=args.bottom_margin)
    sentences, meta = ingestor.parse_pdf(pdf_path=args.pdf, tender_id=args.id)

    print(f"--> Parser Version:     {meta['parser_version']}")
    print(f"--> PDF SHA-256:        {meta['pdf_sha256']}")
    print(f"--> Pages Processed:    {meta['pages']}")
    print(f"--> Total Candidates:   {meta['total_candidates']}")
    print(f"--> Element Breakdown:  {meta['element_counts']}")
    if meta['unknown_cid_count'] > 0:
        print(f"--> [WARNING] Unknown CIDs found: {meta['unknown_cid_count']} occurrences: {meta['unknown_cids']}")
    else:
        print(f"--> CID Status:         Clean (0 unknown CIDs)")
    print(f"==================================================")

    ingestor.save_to_csv(sentences, output_path)
    print("Done!")


if __name__ == "__main__":
    main()
