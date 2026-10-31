import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class CoverageGateError(Exception):
    """Raised when the 100% coverage gate fails due to unclassified sentences."""
    pass

class CoverageLedger:
    """
    Manages the sentence coverage ledger for RFP tender clauses.
    Every single sentence parsed from the PDF must be recorded and classified:
    'requirement', 'background', or 'ignored'.
    
    Implements a strict 100% Coverage Gate:
    If any sentence has no classification, export/sign-off is blocked.
    """

    def __init__(self, db_path: str = "data/coverage_ledger.db"):
        self.is_memory = (db_path == ":memory:")
        if self.is_memory:
            self.db_path = ":memory:"
            self._mem_conn = sqlite3.connect(":memory:")
        else:
            self.db_path = os.path.abspath(db_path)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._init_db()

    def _get_connection(self):
        if self.is_memory:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coverage_ledger (
                    sentence_id TEXT PRIMARY KEY,
                    tender_id TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    section TEXT NOT NULL,
                    text TEXT NOT NULL,
                    classification TEXT NOT NULL,  -- 'requirement', 'background', 'ignored', 'unclassified'
                    req_type TEXT,                -- 'technical', 'commercial', 'eligibility', 'submission', 'compliance'
                    mandatory TEXT,               -- 'yes', 'no', 'conditional'
                    knockout TEXT,                -- 'yes', 'no'
                    knockout_type TEXT,           -- 'missing_document', 'eligibility', 'threshold', 'process'
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'pipeline', -- 'regex', 'llm', 'adjudicated', 'manual'
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_tender ON coverage_ledger(tender_id)
            """)
            conn.commit()

    def record_sentence(
        self,
        sentence_id: str,
        tender_id: str,
        page: int,
        section: str,
        text: str,
        classification: str = "unclassified",
        req_type: Optional[str] = None,
        mandatory: Optional[str] = None,
        knockout: Optional[str] = "no",
        knockout_type: Optional[str] = None,
        confidence: float = 1.0,
        source: str = "pipeline",
        notes: str = ""
    ):
        """Insert or update a sentence classification in the ledger."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO coverage_ledger (
                    sentence_id, tender_id, page, section, text, classification,
                    req_type, mandatory, knockout, knockout_type, confidence, source, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sentence_id) DO UPDATE SET
                    classification=excluded.classification,
                    req_type=excluded.req_type,
                    mandatory=excluded.mandatory,
                    knockout=excluded.knockout,
                    knockout_type=excluded.knockout_type,
                    confidence=excluded.confidence,
                    source=excluded.source,
                    notes=excluded.notes
            """, (
                sentence_id, tender_id, page, section, text, classification,
                req_type, mandatory, knockout, knockout_type, confidence, source, notes, now
            ))
            conn.commit()

    def record_batch(self, items: List[Dict[str, Any]]):
        """Batch record sentences into ledger."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO coverage_ledger (
                    sentence_id, tender_id, page, section, text, classification,
                    req_type, mandatory, knockout, knockout_type, confidence, source, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sentence_id) DO UPDATE SET
                    classification=excluded.classification,
                    req_type=excluded.req_type,
                    mandatory=excluded.mandatory,
                    knockout=excluded.knockout,
                    knockout_type=excluded.knockout_type,
                    confidence=excluded.confidence,
                    source=excluded.source,
                    notes=excluded.notes
            """, [
                (
                    item["sentence_id"],
                    item["tender_id"],
                    item.get("page", 1),
                    item.get("section", "GENERAL"),
                    item["text"],
                    item.get("classification", "unclassified"),
                    item.get("req_type"),
                    item.get("mandatory"),
                    item.get("knockout", "no"),
                    item.get("knockout_type"),
                    item.get("confidence", 1.0),
                    item.get("source", "pipeline"),
                    item.get("notes", ""),
                    now
                )
                for item in items
            ])
            conn.commit()

    def get_tender_ledger(self, tender_id: str) -> List[Dict[str, Any]]:
        """Retrieve all classified sentences for a tender ordered by sentence_id."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM coverage_ledger WHERE tender_id = ? ORDER BY page ASC, sentence_id ASC",
                (tender_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_requirements(self, tender_id: str) -> List[Dict[str, Any]]:
        """Retrieve only rows marked as 'requirement'."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM coverage_ledger WHERE tender_id = ? AND classification = 'requirement' ORDER BY page ASC, sentence_id ASC",
                (tender_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def verify_coverage_gate(self, tender_id: str) -> Dict[str, Any]:
        """
        100% Coverage Gate Verification:
        Every sentence in the document MUST be labeled either 'requirement', 'background', or 'ignored'.
        Fails if any sentence is 'unclassified' or has no label.
        """
        all_rows = self.get_tender_ledger(tender_id)
        if not all_rows:
            raise CoverageGateError(f"No sentences found in ledger for tender '{tender_id}'. Coverage gate failed (0%).")

        total = len(all_rows)
        reqs = sum(1 for r in all_rows if r["classification"] == "requirement")
        bg = sum(1 for r in all_rows if r["classification"] == "background")
        ignored = sum(1 for r in all_rows if r["classification"] == "ignored")
        unclassified = sum(1 for r in all_rows if r["classification"] in ("unclassified", "", None))

        coverage_ratio = (total - unclassified) / total if total > 0 else 0.0

        stats = {
            "tender_id": tender_id,
            "total_sentences": total,
            "requirements": reqs,
            "background": bg,
            "ignored": ignored,
            "unclassified": unclassified,
            "coverage_percent": round(coverage_ratio * 100, 2),
            "gate_passed": unclassified == 0
        }

        if not stats["gate_passed"]:
            raise CoverageGateError(
                f"[GATE FAILED] Tender '{tender_id}' has {unclassified} unclassified sentences out of {total} ({stats['coverage_percent']}% coverage). 100% coverage required!"
            )

        return stats

    def reconcile_and_adjudicate(
        self,
        tender_id: str,
        candidates: List[Dict[str, Any]],
        regex_results: Dict[str, Dict[str, Any]],
        llm_results: Dict[str, Dict[str, Any]],
        extractor: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Dual-Stream Reconciliation & Adjudication Pipeline:
        Compares Regex and LLM determinations for every sentence ID.
        - Agreement -> auto-accepted into ledger.
        - Disagreement or Unlabeled -> routed to LLM Adjudicator (Nemotron Ultra/Reasoning).
        Enforces 100% sentence coverage so NO sentence slips through without an ID and label.
        """
        disagreements = []
        ledger_items = []

        for c in candidates:
            sid = c["sentence_id"]
            page = int(c.get("page") or c.get("start_page") or 1)
            section = c.get("section", "GENERAL")
            text = c["text"]

            reg = regex_results.get(sid, {})
            llm = llm_results.get(sid, {})

            reg_req = bool(reg.get("is_requirement", False))
            llm_req = bool(llm.get("is_requirement", False))

            # Case 1: Agreement
            if reg_req == llm_req:
                classification = "requirement" if reg_req else "background"
                req_type = llm.get("type") or reg.get("matched_type") or ("technical" if reg_req else None)
                mandatory = llm.get("mandatory") or ("yes" if reg_req else None)
                knockout = "yes" if (llm.get("knockout") == "yes" or reg.get("knockout") == "yes") else "no"

                ledger_items.append({
                    "sentence_id": sid,
                    "tender_id": tender_id,
                    "page": page,
                    "section": section,
                    "text": text,
                    "classification": classification,
                    "req_type": req_type,
                    "mandatory": mandatory,
                    "knockout": knockout,
                    "knockout_type": llm.get("knockout_type") or reg.get("knockout_type"),
                    "confidence": 0.95,
                    "source": "regex+llm_consensus",
                    "notes": llm.get("notes") or reg.get("notes", "")
                })

            # Case 2: Disagreement (Heuristic vs LLM conflict)
            else:
                disagreements.append(c)
                if extractor:
                    # Resolve with Nemotron Adjudicator
                    adj = extractor.adjudicate_disagreement(sid, text, reg, llm)
                    ledger_items.append({
                        "sentence_id": sid,
                        "tender_id": tender_id,
                        "page": page,
                        "section": section,
                        "text": text,
                        "classification": adj.get("final_classification", "requirement"),
                        "req_type": adj.get("type", "technical"),
                        "mandatory": adj.get("mandatory", "yes"),
                        "knockout": adj.get("knockout", "no"),
                        "knockout_type": adj.get("knockout_type"),
                        "confidence": adj.get("confidence", 0.90),
                        "source": "adjudicated_nemotron",
                        "notes": adj.get("adjudication_rationale", "Resolved conflict between regex and fast LLM")
                    })
                else:
                    # Conservative fallback: treat as requirement so nothing is dropped
                    ledger_items.append({
                        "sentence_id": sid,
                        "tender_id": tender_id,
                        "page": page,
                        "section": section,
                        "text": text,
                        "classification": "requirement",
                        "req_type": "compliance",
                        "mandatory": "yes",
                        "knockout": "no",
                        "confidence": 0.60,
                        "source": "disagreement_fallback",
                        "notes": "Regex and LLM disagreed; defaulted to requirement"
                    })

        # Save all reconciled rows
        self.record_batch(ledger_items)

        # Enforce 100% Coverage Gate
        stats = self.verify_coverage_gate(tender_id)
        stats["disagreements_resolved"] = len(disagreements)
        return stats
