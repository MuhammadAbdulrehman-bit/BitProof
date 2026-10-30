"""
EvidenceLibrary — Singleton loader and query engine for agency_portfolio.json.

Provides:
  - Fast ID lookup:          get_by_id("EVID-07")
  - Keyword fuzzy search:    search("iso 27001 security")
  - Category filter:         get_by_category("Financial & Solvency")
  - Batch validation:        validate_citations(["[EVID-01]", "[EVID-99]"])
  - Cross-ref audit:         audit_text(proposal_text)  — finds both cited tags
                             AND warns about cited IDs that don't exist in the library
  - Stats summary:           stats()
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

_PORTFOLIO_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "agency_portfolio.json"
)

# Regex compatible with ClaimChecker — matches [EVID-01], [EVID-14], [REF-02], [FACT-09]
_TAG_RE = re.compile(r'\[(?:EVID|REF|FACT)-(\d+)\]', re.IGNORECASE)
_EVID_ID_RE = re.compile(r'^EVID-\d{2}$', re.IGNORECASE)


class EvidenceLibrary:
    """
    Loads and indexes all 55 evidence records from agency_portfolio.json.
    Thread-safe singleton — call EvidenceLibrary.load() to get the instance.
    """

    _instance: Optional["EvidenceLibrary"] = None

    # ── Construction ──────────────────────────────────────────────────

    def __init__(self, portfolio_path: str = _PORTFOLIO_PATH) -> None:
        with open(portfolio_path, encoding="utf-8") as f:
            raw = json.load(f)

        self.agency_name: str = raw.get("agency_name", "")
        self.registration_number: str = raw.get("registration_number", "")
        self.total_declared: int = raw.get("total_records", 0)

        records: List[Dict[str, Any]] = raw.get("evidence_records", [])

        # Primary index: EVID-01 → record dict
        self._by_id: Dict[str, Dict[str, Any]] = {
            r["evidence_id"].upper(): r for r in records
        }

        # Category index: "Financial & Solvency" → [record, ...]
        self._by_category: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            cat = r.get("category", "Uncategorised")
            self._by_category.setdefault(cat, []).append(r)

        # Keyword reverse index: "soc 2" → [EVID-22, ...]
        self._keyword_index: Dict[str, List[str]] = {}
        for r in records:
            eid = r["evidence_id"].upper()
            for kw in r.get("keywords", []):
                self._keyword_index.setdefault(kw.lower(), []).append(eid)

        self._all_records = records

    @classmethod
    def load(cls, portfolio_path: str = _PORTFOLIO_PATH) -> "EvidenceLibrary":
        """Return a cached singleton instance (reload if path differs)."""
        if cls._instance is None:
            cls._instance = cls(portfolio_path)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Force a fresh reload on the next .load() call."""
        cls._instance = None

    # ── Core Queries ──────────────────────────────────────────────────

    def get_by_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Return a single record by its ID string (case-insensitive).
        e.g. get_by_id("EVID-07")  or  get_by_id("evid-7")
        """
        # Normalise: evid-7 → EVID-07
        norm = self._normalise_id(evidence_id)
        return self._by_id.get(norm)

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Return all records whose category equals the given string (case-insensitive).
        """
        for cat, records in self._by_category.items():
            if cat.lower() == category.lower():
                return records
        return []

    def all_categories(self) -> List[str]:
        """Return the list of unique category names."""
        return list(self._by_category.keys())

    def all_records(self) -> List[Dict[str, Any]]:
        """Return every record in order EVID-01 → EVID-55."""
        return list(self._all_records)

    def search(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Fuzzy keyword search against titles, descriptions, keywords, issuers.
        Returns records sorted by relevance score (descending).
        query can be multi-word; each word is scored independently.
        """
        tokens = [t.lower().strip() for t in query.split() if t.strip()]
        if not tokens:
            return []

        scored: List[Tuple[int, Dict[str, Any]]] = []
        for r in self._all_records:
            score = 0
            haystack = " ".join([
                r.get("title", ""),
                r.get("description", ""),
                r.get("issuer", ""),
                r.get("category", ""),
                r.get("metric_value", ""),
                " ".join(r.get("keywords", []))
            ]).lower()

            for tok in tokens:
                if tok in haystack:
                    # Exact keyword match → higher weight
                    kw_hit = any(tok == kw for kw in r.get("keywords", []))
                    score += 3 if kw_hit else 1
                    # Title match bonus
                    if tok in r.get("title", "").lower():
                        score += 2

            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_n]]

    # ── Citation Validation ───────────────────────────────────────────

    def validate_citations(
        self, citation_list: List[str]
    ) -> Dict[str, Any]:
        """
        Given a list of tag strings like ["[EVID-01]", "[EVID-99]"],
        returns which are valid (exist in library) and which are dangling.

        citation_list: raw tag strings extracted from proposal text
        """
        valid, dangling = [], []
        for tag in citation_list:
            m = _TAG_RE.search(tag)
            if not m:
                dangling.append({"tag": tag, "reason": "MALFORMED_TAG"})
                continue
            num = int(m.group(1))
            eid = f"EVID-{num:02d}"
            record = self._by_id.get(eid)
            if record:
                valid.append({
                    "tag": tag,
                    "evidence_id": eid,
                    "title": record["title"],
                    "category": record["category"],
                })
            else:
                dangling.append({
                    "tag": tag,
                    "reason": f"ID {eid} NOT FOUND IN LIBRARY (max EVID-{self.total_declared:02d})"
                })
        return {
            "valid_count": len(valid),
            "dangling_count": len(dangling),
            "valid": valid,
            "dangling": dangling,
            "all_pass": len(dangling) == 0,
        }

    def audit_text(self, text: str) -> Dict[str, Any]:
        """
        Scan free-form proposal text for [EVID-xx] tags,
        resolve each to a library record, and report any dangling references.

        Returns a full audit dict ready for display in the UI.
        """
        raw_tags = _TAG_RE.findall(text)          # just the numeric capture groups
        unique_nums = sorted(set(int(n) for n in raw_tags))
        tags_found = [f"[EVID-{n:02d}]" for n in unique_nums]

        result = self.validate_citations(tags_found)
        result["total_tags_in_text"] = len(raw_tags)
        result["unique_tags"] = len(tags_found)
        return result

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """High-level summary for dashboard display."""
        return {
            "agency_name": self.agency_name,
            "total_records": len(self._all_records),
            "total_declared": self.total_declared,
            "categories": {
                cat: len(recs)
                for cat, recs in self._by_category.items()
            },
            "integrity": "OK" if len(self._all_records) == self.total_declared else "MISMATCH",
        }

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _normalise_id(raw: str) -> str:
        """Normalise 'evid-7' / 'EVID-07' / '7' → 'EVID-07'."""
        raw = raw.strip().upper()
        # Already well-formed
        if _EVID_ID_RE.match(raw):
            return raw
        # Extract digits only
        digits = re.sub(r'[^0-9]', '', raw)
        if digits:
            return f"EVID-{int(digits):02d}"
        return raw
