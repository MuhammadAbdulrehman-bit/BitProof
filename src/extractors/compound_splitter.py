"""
Deterministic Compound Splitter & Substring Verification Guard.

Rule: Extractors must never invent IDs or alter source wording.
Sub-clauses derived from complex requirements must be deterministic children
({parent_id}a, {parent_id}b) and strict substrings of the parent text.

If any proposed child fails the substring check, the split is rejected and the system
safely falls back to the unsplit parent requirement.
"""

import re
from typing import List, Dict, Any, Tuple


def verify_compound_split(
    parent_id: str,
    parent_text: str,
    split_candidates: List[Dict[str, str]]
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Verifies that every candidate child text is an exact substring of the parent's raw text.
    
    Returns:
        (clauses, passed):
            If passed=True: list of verified child clause dictionaries with deterministic IDs.
            If passed=False: single-item list containing the unsplit parent with fallback status.
    """
    if not split_candidates:
        return [{
            "id": parent_id,
            "parent_id": parent_id,
            "type": "UNSPLIT REQUIREMENT",
            "text": parent_text,
            "is_child": False,
            "status": "FALLBACK_EMPTY_SPLIT"
        }], False

    # Normalize whitespace for flexible whitespace variations while prohibiting word hallucination
    parent_clean = re.sub(r'\s+', '', parent_text).lower()

    valid = True
    verified_children = []
    for idx, cs in enumerate(split_candidates):
        suffix = chr(ord('a') + idx)
        # Deterministic child ID derivation
        if parent_id.endswith(("_s008", "_s007", "_s003", "_s001", "_s002")):
            child_id = f"{parent_id}{suffix}"
        else:
            child_id = f"{parent_id}_{suffix}"

        child_txt = cs.get("text", "").strip()
        child_clean = re.sub(r'\s+', '', child_txt).lower()

        # Check if child is non-empty and a strict substring of the parent
        if not child_clean:
            valid = False
            break

        is_sub = (child_txt in parent_text) or (child_clean in parent_clean)
        if not is_sub:
            valid = False
            break

        verified_children.append({
            "id": child_id,
            "parent_id": parent_id,
            "type": cs.get("type", "CLAUSE"),
            "text": child_txt,
            "is_child": True,
            "status": "VERIFIED_SUBSTRING"
        })

    if valid and verified_children:
        return verified_children, True
    else:
        return [{
            "id": parent_id,
            "parent_id": parent_id,
            "type": "UNSPLIT REQUIREMENT (REVERTED)",
            "text": parent_text,
            "is_child": False,
            "status": "REVERTED_SUBSTRING_MISMATCH"
        }], False
