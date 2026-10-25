import os
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class SignoffGateBlockedError(Exception):
    """Raised when PDF export or proposal generation is attempted without a valid human sign-off."""
    pass

class ComplianceMatrixManager:
    """
    Manages the Bidder Compliance Matrix and enforces the Named-Approver Human Sign-Off Gate.
    
    Hard Rules:
    1. Every requirement from the Coverage Ledger must be evaluated (Compliant, Partial, Non-Compliant).
    2. Any knockout clause with Non-Compliant status triggers a HIGH risk warning.
    3. The compliance matrix generates a cryptographic SHA-256 fingerprint.
    4. Proposal PDF Export is strictly locked until a named human approver signs off on the exact fingerprint.
    5. Any subsequent modification to the matrix invalidates the signature and re-locks export.
    """

    def __init__(self, db_path: str = "data/compliance_matrix.db"):
        self.is_memory = (db_path == ":memory:")
        if self.is_memory:
            self.db_path = ":memory:"
            self._mem_conn = sqlite3.connect(":memory:")
        else:
            self.db_path = os.path.abspath(db_path)
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._mem_conn = None
        self._init_db()

    def _get_connection(self):
        if self.is_memory:
            return self._mem_conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS compliance_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tender_id TEXT NOT NULL,
                    req_id TEXT NOT NULL,
                    sentence_id TEXT NOT NULL,
                    clause_text TEXT NOT NULL,
                    section TEXT NOT NULL,
                    req_type TEXT NOT NULL,
                    mandatory TEXT NOT NULL,
                    knockout TEXT NOT NULL,
                    compliance_status TEXT NOT NULL, -- 'COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'CLARIFICATION_NEEDED'
                    vendor_response TEXT,
                    evidence_tags TEXT,             -- JSON list of tags e.g. ["EVID-01", "EVID-04"]
                    risk_level TEXT NOT NULL,        -- 'HIGH', 'MEDIUM', 'LOW'
                    updated_at TEXT NOT NULL,
                    UNIQUE(tender_id, req_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signoff_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tender_id TEXT UNIQUE NOT NULL,
                    matrix_hash TEXT NOT NULL,
                    approver_name TEXT NOT NULL,
                    approver_role TEXT NOT NULL,
                    approver_email TEXT,
                    signed_at TEXT NOT NULL,
                    status TEXT NOT NULL,            -- 'APPROVED', 'REJECTED', 'PENDING'
                    comments TEXT
                )
            """)
            conn.commit()

    def calculate_matrix_hash(self, tender_id: str) -> str:
        """Computes deterministic SHA-256 hash of all compliance items for a tender."""
        items = self.get_matrix(tender_id)
        if not items:
            return ""
        # Canonical representation for hashing
        canonical_rows = [
            f"{it['req_id']}|{it['sentence_id']}|{it['compliance_status']}|{it['risk_level']}|{it.get('vendor_response', '')}"
            for it in sorted(items, key=lambda x: x["req_id"])
        ]
        digest = hashlib.sha256("\n".join(canonical_rows).encode("utf-8")).hexdigest()
        return digest

    def save_item(
        self,
        tender_id: str,
        req_id: str,
        sentence_id: str,
        clause_text: str,
        section: str = "GENERAL",
        req_type: str = "technical",
        mandatory: str = "yes",
        knockout: str = "no",
        compliance_status: str = "COMPLIANT",
        vendor_response: str = "",
        evidence_tags: Optional[List[str]] = None,
        risk_level: Optional[str] = None
    ):
        """Save or update an individual compliance matrix row."""
        if evidence_tags is None:
            evidence_tags = []
        
        # Calculate risk automatically if not explicitly given
        if not risk_level:
            if knockout.lower() == "yes" and compliance_status.upper() != "COMPLIANT":
                risk_level = "HIGH"
            elif compliance_status.upper() == "NON_COMPLIANT":
                risk_level = "HIGH"
            elif compliance_status.upper() in ("PARTIAL", "CLARIFICATION_NEEDED"):
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(evidence_tags)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO compliance_items (
                    tender_id, req_id, sentence_id, clause_text, section,
                    req_type, mandatory, knockout, compliance_status,
                    vendor_response, evidence_tags, risk_level, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tender_id, req_id) DO UPDATE SET
                    sentence_id=excluded.sentence_id,
                    clause_text=excluded.clause_text,
                    section=excluded.section,
                    req_type=excluded.req_type,
                    mandatory=excluded.mandatory,
                    knockout=excluded.knockout,
                    compliance_status=excluded.compliance_status,
                    vendor_response=excluded.vendor_response,
                    evidence_tags=excluded.evidence_tags,
                    risk_level=excluded.risk_level,
                    updated_at=excluded.updated_at
            """, (
                tender_id, req_id, sentence_id, clause_text, section,
                req_type, mandatory, knockout, compliance_status.upper(),
                vendor_response, tags_json, risk_level.upper(), now
            ))
            conn.commit()

    def get_matrix(self, tender_id: str) -> List[Dict[str, Any]]:
        """Fetch full compliance matrix for a tender."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM compliance_items WHERE tender_id = ? ORDER BY id ASC",
                (tender_id,)
            )
            rows = [dict(r) for r in cursor.fetchall()]
            for r in rows:
                if isinstance(r.get("evidence_tags"), str):
                    try:
                        r["evidence_tags"] = json.loads(r["evidence_tags"])
                    except Exception:
                        r["evidence_tags"] = []
            return rows

    def record_signoff(
        self,
        tender_id: str,
        approver_name: str,
        approver_role: str,
        approver_email: str = "",
        comments: str = "",
        status: str = "APPROVED"
    ) -> Dict[str, Any]:
        """
        Records human sign-off bound to the current SHA-256 fingerprint of the matrix.
        """
        matrix_hash = self.calculate_matrix_hash(tender_id)
        if not matrix_hash:
            raise ValueError(f"Cannot sign off: No compliance matrix items exist for tender '{tender_id}'.")

        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signoff_records (
                    tender_id, matrix_hash, approver_name, approver_role,
                    approver_email, signed_at, status, comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tender_id) DO UPDATE SET
                    matrix_hash=excluded.matrix_hash,
                    approver_name=excluded.approver_name,
                    approver_role=excluded.approver_role,
                    approver_email=excluded.approver_email,
                    signed_at=excluded.signed_at,
                    status=excluded.status,
                    comments=excluded.comments
            """, (
                tender_id, matrix_hash, approver_name, approver_role,
                approver_email, now, status.upper(), comments
            ))
            conn.commit()

        return {
            "tender_id": tender_id,
            "matrix_hash": matrix_hash,
            "approver_name": approver_name,
            "approver_role": approver_role,
            "signed_at": now,
            "status": status.upper()
        }

    def get_signoff(self, tender_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve existing sign-off record for tender."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM signoff_records WHERE tender_id = ?", (tender_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def verify_export_authorized(self, tender_id: str) -> Dict[str, Any]:
        """
        THE HUMAN SIGN-OFF GATE:
        Guarantees that no proposal PDF can be exported unless:
        1. A named approver has explicitly approved the matrix.
        2. The matrix has not been modified since the signature was placed.
        
        Raises SignoffGateBlockedError if unauthorized.
        """
        signoff = self.get_signoff(tender_id)
        if not signoff:
            raise SignoffGateBlockedError(
                f"[GATE BLOCKED] Proposal export locked for '{tender_id}'. No sign-off recorded. "
                f"A named approver (e.g. Bid Director) must review and approve the compliance matrix first."
            )

        if signoff.get("status") != "APPROVED":
            raise SignoffGateBlockedError(
                f"[GATE BLOCKED] Sign-off status for '{tender_id}' is '{signoff.get('status')}'. Proposal export is not approved."
            )

        current_hash = self.calculate_matrix_hash(tender_id)
        if current_hash != signoff.get("matrix_hash"):
            raise SignoffGateBlockedError(
                f"[GATE BLOCKED] Compliance Matrix was modified after approval! "
                f"Previous Hash: {signoff.get('matrix_hash')[:10]}... | Current Hash: {current_hash[:10]}... "
                f"Re-approval by named approver is required before export."
            )

        return {
            "authorized": True,
            "approver_name": signoff["approver_name"],
            "approver_role": signoff["approver_role"],
            "signed_at": signoff["signed_at"],
            "matrix_hash": current_hash
        }
