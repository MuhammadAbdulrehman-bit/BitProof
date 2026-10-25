import os
import sys
import csv
import argparse
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extractors.llm_extractor import LLMExtractor


def main():
    parser = argparse.ArgumentParser(description="Auto-label tender candidates using LLM (Groq / Nemotron).")
    parser.add_argument("--tender", required=True, help="Tender ID (e.g. t04, t01, t02, sample_rfp).")
    parser.add_argument("--data-dir", default="data", help="Directory with candidate CSVs.")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of sentences per API call.")
    parser.add_argument("--start-idx", type=int, default=0, help="Start candidate index.")
    parser.add_argument("--max-candidates", type=int, default=None, help="Limit number of candidates to process (for testing).")
    parser.add_argument("--provider", default="auto", choices=["auto", "groq", "nebius"], help="LLM provider.")
    parser.add_argument("--model", default=None, help="Model ID override.")

    args = parser.parse_args()

    candidates_file = os.path.join(args.data_dir, f"{args.tender}_candidates.csv")
    labels_file = os.path.join(args.data_dir, f"{args.tender}_labels.csv")

    if not os.path.exists(candidates_file):
        print(f"Error: {candidates_file} does not exist! Please run parse_tender.py first.")
        sys.exit(1)

    print("=" * 60)
    print(f"--> Auto-labeling Tender: {args.tender}")
    print(f"--> Input candidates:     {candidates_file}")
    print(f"--> Output labels:        {labels_file}")
    print("=" * 60)

    # Read candidates
    candidates = []
    with open(candidates_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candidates.append(row)

    if args.max_candidates:
        candidates = candidates[args.start_idx : args.start_idx + args.max_candidates]
    elif args.start_idx > 0:
        candidates = candidates[args.start_idx :]

    print(f"Loaded {len(candidates)} candidates.")

    # Initialize Extractor
    extractor = LLMExtractor(provider=args.provider, model=args.model)
    print(f"Initialized LLM Extractor using: {extractor.provider} ({extractor.model})")

    labeled_requirements = []
    req_counter = 1

    total_batches = (len(candidates) + args.batch_size - 1) // args.batch_size

    for b_idx in range(total_batches):
        batch = candidates[b_idx * args.batch_size : (b_idx + 1) * args.batch_size]
        print(f"--> Processing batch {b_idx + 1}/{total_batches} ({len(batch)} items)...", end="", flush=True)

        results = extractor.extract_requirements_batch(batch)

        # Map results back to candidate text
        cand_map = {c["sentence_id"]: c for c in batch}

        for res in results:
            sid = res.get("sentence_id")
            if not sid or sid not in cand_map:
                continue

            if res.get("is_requirement") is True:
                cand_info = cand_map[sid]
                label_id = f"{args.tender}_req_{req_counter:03d}"
                req_counter += 1

                t = (res.get("type") or "technical").lower()
                m = (res.get("mandatory") or "yes").lower()
                ko = (res.get("knockout") or "no").lower()
                kot = (res.get("knockout_type") or "").lower() if ko == "yes" else ""
                sc = (res.get("scored_criterion") or "no").lower()
                marks = str(res.get("marks") or "").strip()
                import re
                if sc == "yes" and not re.fullmatch(r"\d+(\.\d+)?", marks):
                    sc = "no"
                    marks = ""

                notes = res.get("notes") or f"Extracted by {extractor.model}"

                labeled_requirements.append({
                    "label_id": label_id,
                    "tender_id": args.tender,
                    "candidate_ids": sid,
                    "exact_quote": cand_info["text"],
                    "type": t,
                    "mandatory": m,
                    "knockout": ko,
                    "knockout_type": kot,
                    "scored_criterion": sc,
                    "marks": marks,
                    "notes": notes
                })

        print(f" Done. (Cumulative requirements found: {len(labeled_requirements)})")
        time.sleep(2.0)  # Rate limit cushion for free tier

    # Write output labels CSV
    fieldnames = [
        "label_id", "tender_id", "candidate_ids", "exact_quote",
        "type", "mandatory", "knockout", "knockout_type",
        "scored_criterion", "marks", "notes"
    ]

    with open(labels_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in labeled_requirements:
            writer.writerow(row)

    print("=" * 60)
    print(f"SUCCESS: Wrote {len(labeled_requirements)} requirements to {labels_file}")
    print("=" * 60)

    # Automatically validate against validate_labels.py
    print("\n--> Running validation checks...")
    val_script = os.path.join(args.data_dir, "validate_labels.py")
    if os.path.exists(val_script):
        import subprocess
        subprocess.run([sys.executable, val_script, args.tender], check=False)


if __name__ == "__main__":
    main()
