"""
matcher_adapter.py — Lexical evidence matcher that wraps EvidenceLibrary.

Uses token-overlap scoring (no LLM, no hard-coded mapping).
Includes numeric comparison for turnover, uptime, experience years, warranty.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from src.evidence.evidence_library import EvidenceLibrary


# ── Numeric extraction patterns ──────────────────────────────────────
_NUM_PATTERNS = [
    # PKR amounts: "PKR 150 Million", "PKR 241.8M"
    (re.compile(r'PKR\s+([\d,.]+)\s*[Mm](?:illion)?', re.IGNORECASE), "PKR", 1_000_000),
    # Uptime: "99.9%", "99.95%" — allow words between % and uptime/SLA, or uptime SLA of 99.9%
    (re.compile(r'(\d{2,3}(?:\.\d+)?)\s*%\s*(?:\w+\s+)*?(?:uptime|availability|SLA)', re.IGNORECASE), "%", 1),
    (re.compile(r'(?:uptime|availability|SLA)\s+(?:\w+\s+)*?(\d{2,3}(?:\.\d+)?)\s*%', re.IGNORECASE), "%", 1),
    # Years: "five (05) years", "3 years", "three (03) years"
    (re.compile(r'(?:(\d+)\s*\)?\s*years|(\d+)\s*years)', re.IGNORECASE), "years", 1),
    # Warranty: "three (03) years" or "3 years warranty/maintenance"
    (re.compile(r'(\d+)\s*\)?\s*years?\s*(?:of\s+)?(?:comprehensive|warranty|maintenance|support)', re.IGNORECASE), "warranty_years", 1),
    # RPO/RTO: "RPO under 5 minutes", "RTO under 15 minutes"
    (re.compile(r'(RPO|RTO)\s+(?:under|<|less than)\s+(\d+)\s*min', re.IGNORECASE), "minutes", 1),
    # Staff count: "twelve (12) IT staff", "85 engineers"
    (re.compile(r'(\d+)\s*\)?\s*(?:IT\s+staff|engineers|personnel|employees)', re.IGNORECASE), "people", 1),
]


def _extract_numbers(text: str) -> List[Dict[str, Any]]:
    """Pull numeric requirements from clause text."""
    results = []
    for pattern, unit, multiplier in _NUM_PATTERNS:
        for m in pattern.finditer(text):
            # Get the first non-None group
            val_str = next((g for g in m.groups() if g and g.replace('.', '').replace(',', '').isdigit()), None)
            if val_str:
                val = float(val_str.replace(',', '')) * multiplier
                results.append({
                    "value": val,
                    "unit": unit,
                    "raw": m.group(0),
                    "label": m.group(0).strip(),
                })
    return results


def _extract_evidence_number(text: str) -> Optional[float]:
    """Pull a numeric value from evidence metric_value field."""
    # PKR amounts
    m = re.search(r'PKR\s+([\d,.]+)\s*[Mm](?:illion)?', text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(',', '')) * 1_000_000

    # Percentage
    m = re.search(r'(\d{2,3}(?:\.\d+)?)\s*%', text)
    if m:
        return float(m.group(1))

    # Years
    m = re.search(r'(\d+)\s*[Yy]ears?', text)
    if m:
        return float(m.group(1))

    # Months -> years
    m = re.search(r'(\d+)\s*[Mm]onths?', text)
    if m:
        return float(m.group(1)) / 12.0

    # Minutes (RPO/RTO)
    m = re.search(r'(\d+(?:\.\d+)?)\s*[Mm]in', text)
    if m:
        return float(m.group(1))

    # Plain number
    m = re.search(r'(\d+(?:\.\d+)?)', text)
    if m:
        return float(m.group(1))

    return None


def _tokenize(text: str) -> set:
    """Lowercase token set for overlap scoring."""
    return set(re.findall(r'[a-z0-9]+(?:[.\-/][a-z0-9]+)*', text.lower()))


def lexical_match(
    clause_text: str,
    library: EvidenceLibrary,
    top_n: int = 1,
) -> List[Dict[str, Any]]:
    """
    Match a clause to evidence records using token overlap.
    Returns list of matches with score, evidence_id, comparison detail.
    """
    clause_tokens = _tokenize(clause_text)
    if not clause_tokens:
        return []

    scored = []
    for rec in library.all_records():
        haystack = " ".join([
            rec.get("title", ""),
            rec.get("description", ""),
            rec.get("metric_value", ""),
            " ".join(rec.get("keywords", [])),
        ])
        rec_tokens = _tokenize(haystack)

        overlap = clause_tokens & rec_tokens
        if not overlap:
            continue

        # Score: |overlap| / |clause_tokens|
        score = len(overlap) / len(clause_tokens)

        scored.append({
            "evidence_id": rec["evidence_id"],
            "title": rec["title"],
            "score": round(score, 3),
            "metric_value": rec.get("metric_value", ""),
            "overlap_tokens": len(overlap),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


def match_clause(
    clause_text: str,
    library: EvidenceLibrary,
) -> Dict[str, Any]:
    """
    Full match result for a single clause.
    Returns: {
        evidence_id, score, suggestion (SUPPORTED/GAP/NO_EVIDENCE),
        method, comparison (if numeric), title
    }
    """
    matches = lexical_match(clause_text, library, top_n=1)

    if not matches or matches[0]["score"] < 0.08:
        return {
            "evidence_id": "—",
            "score": 0.0,
            "suggestion": "NO_EVIDENCE",
            "method": "lexical_overlap",
            "comparison": "",
            "title": "",
        }

    best = matches[0]
    result = {
        "evidence_id": best["evidence_id"],
        "score": best["score"],
        "method": "lexical_overlap",
        "title": best["title"],
        "comparison": "",
    }

    # Numeric comparison
    clause_nums = _extract_numbers(clause_text)
    if clause_nums and best["metric_value"]:
        ev_num = _extract_evidence_number(best["metric_value"])
        if ev_num is not None:
            req_num = clause_nums[0]
            req_val = req_num["value"]
            unit = req_num["unit"]

            # For RPO/RTO: lower is better (evidence must be <= required)
            if unit == "minutes":
                met = ev_num <= req_val
                result["comparison"] = f"evidence {ev_num:.1f} min {'<=' if met else '>'} required {req_val:.0f} min"
            # For uptime %: higher is better
            elif unit == "%":
                met = ev_num >= req_val
                result["comparison"] = f"evidence {ev_num}% {'>=' if met else '<'} required {req_val}%"
            # For PKR amounts: higher is better
            elif unit == "PKR":
                ev_m = ev_num / 1_000_000
                req_m = req_val / 1_000_000
                met = ev_num >= req_val
                result["comparison"] = f"evidence {ev_m:.1f}M >= required {req_m:.0f}M" if met else f"evidence {ev_m:.1f}M < required {req_m:.0f}M"
            # For years/warranty: higher is better
            elif unit in ("years", "warranty_years"):
                met = ev_num >= req_val
                result["comparison"] = f"evidence {ev_num:.0f} yrs >= required {req_val:.0f} yrs" if met else f"evidence {ev_num:.0f} yrs < required {req_val:.0f} yrs"
            else:
                met = ev_num >= req_val
                result["comparison"] = f"evidence {ev_num:.0f} >= required {req_val:.0f}" if met else f"evidence {ev_num:.0f} < required {req_val:.0f}"

            if not met:
                result["suggestion"] = "GAP"
                return result

    # If score is decent → SUPPORTED, otherwise GAP
    if best["score"] >= 0.12:
        result["suggestion"] = "SUPPORTED"
    else:
        result["suggestion"] = "GAP"

    return result


def match_all_clauses(
    clauses: List[Dict[str, str]],
    library: EvidenceLibrary,
) -> List[Dict[str, Any]]:
    """
    Match a list of clauses (each with 'sentence_id' and 'text' keys).
    Returns a list of match results in the same order.
    """
    return [
        {**match_clause(c.get("text", ""), library), "sentence_id": c.get("sentence_id", "")}
        for c in clauses
    ]
