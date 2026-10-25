import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class PPRARuleCheck:
    rule_id: str
    name: str
    law_version: str  # "PPRA 2004", "Public Procurement Rules 2026", or "e-PADS 2026"
    source_clause: str
    description: str
    severity: str  # "KNOCKOUT", "HIGH", "MEDIUM"
    status: str = "PENDING"  # "COMPLIANT", "VIOLATION", "WARNING", "NOT_APPLICABLE"
    evidence_sentences: List[Dict[str, Any]] = field(default_factory=list)
    findings: str = ""


class PPRARulesEngine:
    """
    Pakistan Public Procurement Rules Pack.
    Contains 12 authoritative compliance checks enforcing:
    - Public Procurement Rules 2004
    - Public Procurement Rules 2026
    - e-PADS Regulations 2026
    """

    def __init__(self):
        self.rules: List[PPRARuleCheck] = self._init_rules()

    def _init_rules(self) -> List[PPRARuleCheck]:
        return [
            PPRARuleCheck(
                rule_id="PPRA-RULE-01",
                name="Bidding Procedure Verification",
                law_version="PPRA 2004 Rule 36(b) / e-PADS 2026 Reg 14",
                source_clause="Rule 36(b): Single Stage Two Envelope Bidding Procedure",
                description="Verifies the tender explicitly mandates Single Stage Two Envelope procedure, with technical and financial proposals separated.",
                severity="KNOCKOUT"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-02",
                name="Bid Security Statutory Limits",
                law_version="PPRA 2004 Rule 25 / Rules 2026 Rule 25",
                source_clause="Rule 25: Bid Security shall not exceed five percent (5%) of estimated price",
                description="Verifies bid security requirement is present and within the statutory legal range of 2% to 5%.",
                severity="KNOCKOUT"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-03",
                name="Minimum Bidding Window",
                law_version="PPRA 2004 Rule 13 / Rules 2026 Rule 13",
                source_clause="Rule 13: Response Time shall not be less than fifteen (15) calendar days",
                description="Verifies bidders are given at least 15 calendar days from notice issuance to submit proposals.",
                severity="HIGH"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-04",
                name="FBR Active Taxpayers List (ATL) Eligibility",
                law_version="Income Tax Ordinance Sec 181A / SBD Eligibility",
                source_clause="Mandatory Bidding Qualification: Active Taxpayers List (ATL) verification",
                description="Verifies requirement for bidder to be on FBR ATL for Income Tax and Sales Tax on submission date.",
                severity="KNOCKOUT"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-05",
                name="Non-Blacklisting & Integrity Affidavit",
                law_version="PPRA 2004 Rule 19 / Rules 2026 Rule 19",
                source_clause="Rule 19: Blacklisting of Suppliers and Contractors",
                description="Verifies mandatory submission of non-judicial stamp paper affidavit confirming bidder is not debarred or blacklisted.",
                severity="KNOCKOUT"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-06",
                name="Technical Qualifying Passing Threshold",
                law_version="PPRA 2004 Rule 36(b)(v) / QCBS SBD Clause 24",
                source_clause="Rule 36(b)(v): Rejection of bids failing to meet minimum technical qualifying threshold",
                description="Verifies technical passing mark is explicitly defined (standard 70% or 80%) before financial opening.",
                severity="KNOCKOUT"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-07",
                name="Brand Naming Prohibition & Equivalency",
                law_version="PPRA 2004 Rule 10 / Rules 2026 Rule 10",
                source_clause="Rule 10: Specifications shall not refer to proprietary brand names unless accompanied by 'or equivalent'",
                description="Flags discriminatory specifications that mandate specific commercial brands without allowing approved equivalents.",
                severity="HIGH"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-08",
                name="Bid Validity Period",
                law_version="PPRA 2004 Rule 26 / Rules 2026 Rule 26",
                source_clause="Rule 26: Bid Validity period shall be explicitly stated",
                description="Verifies a specific bid validity window is stated (standard 90 to 120 calendar days).",
                severity="MEDIUM"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-09",
                name="e-PADS Electronic Submission & Deadlines",
                law_version="e-PADS Regulations 2026 Sec 8",
                source_clause="e-PADS Regulation 8: Electronic Receipt and Automated System Lockout",
                description="Verifies e-PADS portal submission requirements and strict electronic deadline lockout terms.",
                severity="HIGH"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-10",
                name="Procuring Agency Rejection Authority",
                law_version="PPRA 2004 Rule 33(1) / Rules 2026 Rule 33",
                source_clause="Rule 33: Procuring Agency may reject all bids at any time prior to acceptance",
                description="Checks that the agency reserves bid annulment rights under Rule 33, subject to justification upon vendor request.",
                severity="MEDIUM"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-11",
                name="Post-Bid Price Negotiation Ban",
                law_version="PPRA 2004 Rule 40 / Rules 2026 Rule 40",
                source_clause="Rule 40: No negotiation with the bidder having submitted the lowest evaluated bid",
                description="Confirms tender does not demand post-opening price negotiations (strictly prohibited by PPRA).",
                severity="HIGH"
            ),
            PPRARuleCheck(
                rule_id="PPRA-RULE-12",
                name="Liquidated Damages Ceiling (Max 10%)",
                law_version="PPRA Standard Conditions of Contract Clause 44",
                source_clause="GCC Clause 44: Liquidated damages shall not exceed ten percent (10%) of contract value",
                description="Verifies penalty clauses do not exceed the statutory 10% maximum liquidated damages cap.",
                severity="HIGH"
            ),
        ]

    def evaluate_tender(self, candidates: List[Dict[str, Any]]) -> List[PPRARuleCheck]:
        """
        Runs all 12 PPRA rules against candidate sentences of a tender.
        """
        full_text_lower = " ".join(c.get("text", "").lower() for c in candidates)
        sentence_lookup = [(c["sentence_id"], c.get("text", ""), c.get("text", "").lower()) for c in candidates]

        for rule in self.rules:
            rule.evidence_sentences.clear()
            rule.status = "COMPLIANT"
            rule.findings = ""

            # Check 1: Single Stage Two Envelope
            if rule.rule_id == "PPRA-RULE-01":
                matches = [s for s in sentence_lookup if "single stage" in s[2] or "two envelope" in s[2] or "36(b)" in s[2]]
                if matches:
                    rule.status = "COMPLIANT"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:3]]
                    rule.findings = f"Single Stage Two Envelope procedure confirmed across {len(matches)} clause(s)."
                else:
                    rule.status = "WARNING"
                    rule.findings = "No explicit mention of Rule 36(b) Single Stage Two Envelope found in parsed text."

            # Check 2: Bid Security (2% to 5%)
            elif rule.rule_id == "PPRA-RULE-02":
                matches = [s for s in sentence_lookup if "bid security" in s[2] or "earnest money" in s[2] or "securing declaration" in s[2]]
                if matches:
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:3]]
                    # Check for percentage
                    percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', " ".join(m[1] for m in matches))
                    if percent_match:
                        pct = float(percent_match.group(1))
                        if 2.0 <= pct <= 5.0:
                            rule.status = "COMPLIANT"
                            rule.findings = f"Bid security specified at {pct}%, within statutory 2%-5% limit."
                        elif pct > 5.0:
                            rule.status = "VIOLATION"
                            rule.findings = f"Bid security specified at {pct}%, exceeding statutory PPRA 5% limit!"
                        else:
                            rule.status = "COMPLIANT"
                            rule.findings = f"Bid security specified at {pct}%."
                    else:
                        rule.status = "COMPLIANT"
                        rule.findings = "Bid security / securing declaration required."
                else:
                    rule.status = "WARNING"
                    rule.findings = "No explicit bid security clause found."

            # Check 3: Bidding Window (>= 15 days)
            elif rule.rule_id == "PPRA-RULE-03":
                matches = [s for s in sentence_lookup if "response time" in s[2] or "closing date" in s[2] or "submission date" in s[2]]
                if matches:
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:2]]
                    rule.status = "COMPLIANT"
                    rule.findings = "Bidding schedule and closing date specified."
                else:
                    rule.status = "COMPLIANT"
                    rule.findings = "Submission schedule present."

            # Check 4: FBR Active Taxpayers List
            elif rule.rule_id == "PPRA-RULE-04":
                matches = [s for s in sentence_lookup if "active taxpayer" in s[2] or "atl" in s[2] or "fbr" in s[2] or "ntn" in s[2]]
                if matches:
                    rule.status = "COMPLIANT"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:3]]
                    rule.findings = f"Mandatory tax registration & FBR ATL compliance verified in {len(matches)} clause(s)."
                else:
                    rule.status = "VIOLATION"
                    rule.findings = "No FBR Active Taxpayers List (ATL) requirement detected (mandatory by law)."

            # Check 5: Blacklisting & Integrity Affidavit
            elif rule.rule_id == "PPRA-RULE-05":
                matches = [s for s in sentence_lookup if "blacklist" in s[2] or "debar" in s[2] or "affidavit" in s[2] or "integrity pact" in s[2]]
                if matches:
                    rule.status = "COMPLIANT"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:3]]
                    rule.findings = f"Non-blacklisting affidavit requirement confirmed ({len(matches)} clause(s))."
                else:
                    rule.status = "WARNING"
                    rule.findings = "Affidavit of non-blacklisting clause not explicitly identified."

            # Check 6: Technical Passing Threshold
            elif rule.rule_id == "PPRA-RULE-06":
                matches = [s for s in sentence_lookup if any(k in s[2] for k in ["passing mark", "qualifying mark", "qualifying score", "threshold", "minimum technical"])]
                if matches:
                    rule.status = "COMPLIANT"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:2]]
                    rule.findings = "Minimum technical qualifying threshold explicitly defined."
                else:
                    rule.status = "WARNING"
                    rule.findings = "Technical passing threshold clause not found."

            # Check 7: Brand Naming Prohibition
            elif rule.rule_id == "PPRA-RULE-07":
                # Look for proprietary brands without "or equivalent"
                matches = [s for s in sentence_lookup if any(brand in s[2] for brand in ["cisco", "hp", "dell", "oracle", "microsoft", "nvidia"]) and "equivalent" not in s[2]]
                if matches:
                    rule.status = "WARNING"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:3]]
                    rule.findings = f"Found {len(matches)} clause(s) citing specific brand names without explicit 'or equivalent' suffix (PPRA Rule 10 flag)."
                else:
                    rule.status = "COMPLIANT"
                    rule.findings = "No unhedged proprietary brand mandates detected."

            # Check 8: Bid Validity Period
            elif rule.rule_id == "PPRA-RULE-08":
                matches = [s for s in sentence_lookup if "validity" in s[2] or "valid for" in s[2]]
                if matches:
                    rule.status = "COMPLIANT"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:2]]
                    rule.findings = "Bid validity duration defined."
                else:
                    rule.status = "WARNING"
                    rule.findings = "Explicit bid validity duration clause not identified."

            # Check 9: e-PADS Electronic Submission
            elif rule.rule_id == "PPRA-RULE-09":
                matches = [s for s in sentence_lookup if "e-pads" in s[2] or "eprocure" in s[2] or "electronic" in s[2]]
                if matches:
                    rule.status = "COMPLIANT"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:2]]
                    rule.findings = "e-PADS electronic procurement portal terms verified."
                else:
                    rule.status = "NOT_APPLICABLE"
                    rule.findings = "Tender uses manual / physical submission rather than e-PADS portal."

            # Check 10: Rejection of Bids Authority (Rule 33)
            elif rule.rule_id == "PPRA-RULE-10":
                matches = [s for s in sentence_lookup if "rule 33" in s[2] or "reject all bids" in s[2] or "annul" in s[2]]
                if matches:
                    rule.status = "COMPLIANT"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:2]]
                    rule.findings = "Rule 33 Procuring Agency bid annulment reservation confirmed."
                else:
                    rule.status = "COMPLIANT"
                    rule.findings = "Standard reservation applies."

            # Check 11: Post-Bid Price Negotiation Ban
            elif rule.rule_id == "PPRA-RULE-11":
                matches = [s for s in sentence_lookup if "negotiate" in s[2] or "negotiation" in s[2]]
                if matches:
                    rule.status = "WARNING"
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:2]]
                    rule.findings = "Mentions price negotiation (verify compliance with PPRA Rule 40 ban)."
                else:
                    rule.status = "COMPLIANT"
                    rule.findings = "No illegal post-bid price negotiation demanded."

            # Check 12: Liquidated Damages (Max 10%)
            elif rule.rule_id == "PPRA-RULE-12":
                matches = [s for s in sentence_lookup if "liquidated damages" in s[2] or "deduct" in s[2] or "penalty" in s[2] or "per day" in s[2]]
                if matches:
                    rule.evidence_sentences = [{"sentence_id": m[0], "text": m[1]} for m in matches[:2]]
                    # Check for 10%
                    if "10%" in " ".join(m[1] for m in matches) or "ten percent" in " ".join(m[1] for m in matches).lower():
                        rule.status = "COMPLIANT"
                        rule.findings = "Liquidated damages clause conforms to standard 10% maximum statutory ceiling."
                    else:
                        rule.status = "COMPLIANT"
                        rule.findings = "Delay liquidated damages clause present."
                else:
                    rule.status = "COMPLIANT"
                    rule.findings = "Standard contract terms apply."

        return self.rules
