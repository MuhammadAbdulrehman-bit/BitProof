import os
import sys
import csv
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extractors.regex_scanner import RegexScanner


def run_benchmark(candidates_path: str, labels_path: str):
    print("=" * 60)
    print(f"--> Running Regex Benchmark")
    print(f"--> Candidates: {candidates_path}")
    print(f"--> Labels:     {labels_path}")
    print("=" * 60)

    # 1. Load ground truth labels
    ground_truth_ids = set()         # Candidate IDs mapped to any requirement
    knockout_ids = set()             # IDs specifically labeled knockout=yes
    consequence_ids = set()          # IDs where knockout is triggered by consequence sentence
    all_label_rows = []
    parser_miss_count = 0

    with open(labels_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_label_rows.append(row)
            c_ids = [cid.strip() for cid in row["candidate_ids"].split(";") if cid.strip()]
            for cid in c_ids:
                if cid == "PARSER_MISS":
                    parser_miss_count += 1
                    continue
                ground_truth_ids.add(cid)
                if row.get("knockout", "").lower() == "yes":
                    knockout_ids.add(cid)
                    notes = row.get("notes", "").lower()
                    # A "consequence" row is one that states the penalty/rejection,
                    # not the positive requirement. Heuristic: notes mention consequence or
                    # the intro line carries "shall be rejected / non-responsive"
                    exact_quote = row.get("exact_quote", "").lower()
                    if any(w in exact_quote for w in ["declared non-responsive", "shall be rejected",
                                                       "disqualified", "without bid security"]):
                        consequence_ids.add(cid)

    requirement_ids_only = knockout_ids - consequence_ids  # The positive obligation rows

    # 2. Load candidates
    candidates = []
    with open(candidates_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candidates.append(row)

    all_candidate_ids = {row["sentence_id"] for row in candidates}
    N = len(all_candidate_ids)
    G = len(ground_truth_ids)

    # 3. Baseline: label every sentence a requirement
    baseline_tp = G
    baseline_fp = N - G
    baseline_precision = baseline_tp / N if N > 0 else 0.0
    baseline_recall = 1.0

    # 4. Run Regex Scanner
    scanner = RegexScanner()
    regex_flagged_ids = set()
    regex_knockout_ids = set()

    for row in candidates:
        cid = row["sentence_id"]
        res = scanner.scan_sentence(row["text"], element_type=row.get("element_type", "sentence"))
        if res["is_requirement"]:
            regex_flagged_ids.add(cid)
            if res.get("knockout") == "yes":
                regex_knockout_ids.add(cid)

    # 5. Regex metrics
    tp = len(regex_flagged_ids & ground_truth_ids)
    fp = len(regex_flagged_ids - ground_truth_ids)
    fn = len(ground_truth_ids - regex_flagged_ids)
    tn = len((all_candidate_ids - regex_flagged_ids) - ground_truth_ids)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Knockout recall split
    ko_total       = len(knockout_ids)
    ko_caught      = len(regex_knockout_ids & knockout_ids)
    ko_recall      = ko_caught / ko_total if ko_total > 0 else 0.0

    consequence_caught = len(regex_knockout_ids & consequence_ids)
    req_caught         = len(regex_knockout_ids & requirement_ids_only)

    print(f"\n[RESULTS SUMMARY]")
    print(f"Total Candidates Evaluated:  {N}")
    print(f"Ground Truth Requirements:   {G}  (Parser misses: {parser_miss_count})")
    print(f"Regex Predicted Reqs:        {len(regex_flagged_ids)}")
    print(f"--------------------------------------------------")
    print(f"True Positives  (TP): {tp}")
    print(f"False Positives (FP): {fp}")
    print(f"False Negatives (FN): {fn}")
    print(f"True Negatives  (TN): {tn}")
    print(f"--------------------------------------------------")
    print(f"                      BASELINE   REGEX")
    print(f"PRECISION:            {baseline_precision:.1%}      {precision:.1%}")
    print(f"RECALL:               {baseline_recall:.1%}     {recall:.1%}")
    print(f"F1 SCORE:              ---        {f1:.1%}")
    print(f"--------------------------------------------------")
    print(f"KNOCKOUT LABELS TOTAL:    {ko_total}")
    print(f"  consequence rows:       {len(consequence_ids)}")
    print(f"  requirement rows:       {len(requirement_ids_only)}")
    print(f"KNOCKOUT RECALL (total):  {ko_recall:.1%}  ({ko_caught}/{ko_total})")
    print(f"  consequence rows caught:{consequence_caught}/{len(consequence_ids)}")
    print(f"  requirement rows caught:{req_caught}/{len(requirement_ids_only)}")
    print(f"  NOTE: regex finds consequence text ('rejected'), not linked requirement.")
    print("=" * 60)
    print("CAVEAT: t03 is a 6-page RFQ where most sentences are requirements.")
    print("Baseline precision and regex precision will diverge significantly on")
    print("100-page tenders where boilerplate dominates. Run on t01, t02, t04.")

    if fn > 0:
        print(f"\n[MISSED REQUIREMENTS (False Negatives)]")
        missed_ids = list(ground_truth_ids - regex_flagged_ids)
        for mid in missed_ids[:5]:
            matched_row = next((r for r in candidates if r["sentence_id"] == mid), None)
            text_snippet = matched_row["text"][:80] if matched_row else ""
            print(f" - {mid}: {text_snippet}...")
        if len(missed_ids) > 5:
            print(f"   ... and {len(missed_ids) - 5} more.")

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "baseline_precision": baseline_precision,
        "knockout_recall": ko_recall,
        "knockout_total": ko_total,
        "consequence_caught": consequence_caught,
        "req_rows_caught": req_caught,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark Regex Scanner against ground truth labels.")
    parser.add_argument("--candidates", default="data/t03_candidates.csv", help="Path to candidates CSV.")
    parser.add_argument("--labels", default="data/t03_labels.csv", help="Path to labels CSV.")
    args = parser.parse_args()

    run_benchmark(args.candidates, args.labels)
