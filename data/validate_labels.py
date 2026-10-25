#!/usr/bin/env python3
"""
validate_labels.py - sanity-check data/<id>_labels.csv against data/<id>_candidates.csv.

Usage (from the repo root):
    python validate_labels.py t01 t02 t03 t04
    python validate_labels.py t03 --data-dir data --id-col sentence_id --text-col text

Assumed label columns (rename with the constants below if yours differ):
    label_id, tender_id, candidate_ids, exact_quote, type, mandatory, knockout,
    knockout_type, scored_criterion, marks, notes
Assumed candidate columns: sentence_id (or candidate_id), text.

Exit code 1 if any ERROR is found. WARNINGs never fail the run.
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

TYPES = {"technical", "eligibility", "compliance", "commercial", "submission", "evaluation"}
MANDATORY = {"yes", "no", "conditional"}
YESNO = {"yes", "no"}
KO_TYPES = {"missing_document", "eligibility", "threshold", "process"}

# Column names in the labels file
C_ID, C_CANDS, C_QUOTE = "label_id", "candidate_ids", "exact_quote"
C_TYPE, C_MAND, C_KO, C_KOT = "type", "mandatory", "knockout", "knockout_type"
C_SCORED, C_MARKS, C_NOTES = "scored_criterion", "marks", "notes"


def squash(s):
    """Lowercase and drop ALL whitespace, so spacing differences can't hide a match."""
    return re.sub(r"\s+", "", (s or "").lower())


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def validate(tid, data_dir, id_col, text_col):
    errors, warnings = [], []
    cand_path = data_dir / f"{tid}_candidates.csv"
    lab_path = data_dir / f"{tid}_labels.csv"
    for p in (cand_path, lab_path):
        if not p.exists():
            return [f"missing file {p}"], [], {}

    cands = read_csv(cand_path)
    if cands and id_col not in cands[0]:
        alt = "candidate_id" if "candidate_id" in cands[0] else None
        if not alt:
            return [f"{cand_path.name}: no '{id_col}' column (found {list(cands[0])})"], [], {}
        id_col = alt
    cand_text = {c[id_col]: c.get(text_col, "") for c in cands}
    labels = read_csv(lab_path)

    seen_ids, used = set(), Counter()
    for i, r in enumerate(labels, start=2):  # row 1 is the header
        where = f"{lab_path.name} row {i} ({r.get(C_ID, '?')})"
        lid = (r.get(C_ID) or "").strip()
        if not lid:
            errors.append(f"{where}: empty label_id")
        elif lid in seen_ids:
            errors.append(f"{where}: duplicate label_id")
        seen_ids.add(lid)

        ids = [x for x in re.split(r"[;,|\s]+", r.get(C_CANDS) or "") if x]
        if not ids:
            warnings.append(f"{where}: no candidate_ids (counts as a parser miss)")
        for cid in ids:
            used[cid] += 1
            if cid not in cand_text:
                errors.append(f"{where}: unknown candidate id {cid}")

        quote = squash(r.get(C_QUOTE))
        joined = squash(" ".join(cand_text.get(c, "") for c in ids))
        if not quote:
            warnings.append(f"{where}: empty exact_quote")
        elif ids and quote not in joined:
            warnings.append(f"{where}: quote not found in its candidate text")

        t, m, ko = (r.get(C_TYPE) or "").strip().lower(), (r.get(C_MAND) or "").strip().lower(), (r.get(C_KO) or "").strip().lower()
        kot, sc = (r.get(C_KOT) or "").strip().lower(), (r.get(C_SCORED) or "").strip().lower()
        if t not in TYPES:
            errors.append(f"{where}: bad type {t!r}")
        if m not in MANDATORY:
            errors.append(f"{where}: bad mandatory {m!r}")
        if ko not in YESNO:
            errors.append(f"{where}: bad knockout {ko!r}")
        if ko == "yes" and kot not in KO_TYPES:
            errors.append(f"{where}: knockout=yes needs knockout_type in {sorted(KO_TYPES)}")
        if ko == "no" and kot:
            warnings.append(f"{where}: knockout_type set but knockout=no")
        if sc not in YESNO:
            errors.append(f"{where}: bad scored_criterion {sc!r}")
        marks = (r.get(C_MARKS) or "").strip()
        if sc == "yes" and not re.fullmatch(r"\d+(\.\d+)?", marks):
            errors.append(f"{where}: scored_criterion=yes needs numeric marks")
        if sc == "no" and marks:
            warnings.append(f"{where}: marks set but scored_criterion=no")

    overlap = [c for c, n in used.items() if n > 1]
    if overlap:
        warnings.append(f"{len(overlap)} candidate ids are used by more than one label, e.g. {overlap[:3]}")

    stats = {
        "labels": len(labels),
        "candidates": len(cands),
        "candidates_labeled": sum(1 for c in used if c in cand_text),
        "knockouts": sum(1 for r in labels if (r.get(C_KO) or "").strip().lower() == "yes"),
        "scored": sum(1 for r in labels if (r.get(C_SCORED) or "").strip().lower() == "yes"),
        "unsure": sum(1 for r in labels if "unsure" in (r.get(C_NOTES) or "").lower()),
        "pending_review": sum(1 for r in labels if "pending" in (r.get(C_NOTES) or "").lower()),
        "types": dict(Counter((r.get(C_TYPE) or "").strip().lower() for r in labels)),
    }
    return errors, warnings, stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("tenders", nargs="+")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--id-col", default="sentence_id")
    ap.add_argument("--text-col", default="text")
    a = ap.parse_args(argv)

    bad = False
    for tid in a.tenders:
        errs, warns, st = validate(tid, Path(a.data_dir), a.id_col, a.text_col)
        print(f"\n=== {tid} ===")
        if st:
            print(f"  {st['labels']} labels over {st['candidates_labeled']}/{st['candidates']} candidates | "
                  f"knockouts={st['knockouts']} scored={st['scored']} unsure={st['unsure']} pending={st['pending_review']}")
            print(f"  types: {st['types']}")
        for e in errs[:25]:
            print("  ERROR  ", e)
        for w in warns[:25]:
            print("  warning", w)
        extra = len(errs) - 25
        if extra > 0:
            print(f"  ... {extra} more errors")
        print(f"  -> {len(errs)} errors, {len(warns)} warnings")
        bad = bad or bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
