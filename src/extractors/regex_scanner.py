import re
from typing import Dict, Any, List, Optional


class RegexScanner:
    """
    Plain code regex extractor that identifies binding requirements,
    knockout risks, and requirement categories based on procurement rules.
    """

    # Modal and imperative verbs indicating obligations
    BINDING_TRIGGERS = [
        re.compile(r'\bshall\b', re.IGNORECASE),
        re.compile(r'\bmust\b', re.IGNORECASE),
        re.compile(r'\brequired\b', re.IGNORECASE),
        re.compile(r'\bmandatory\b', re.IGNORECASE),
        re.compile(r'\bis\s+to\b', re.IGNORECASE),
        re.compile(r'\bare\s+to\b', re.IGNORECASE),
        re.compile(r'\bwill\b', re.IGNORECASE),
        re.compile(r'\bshould\b', re.IGNORECASE),
        re.compile(r'\bobligat(?:ed|ory)\b', re.IGNORECASE),
    ]

    # Technical bill of quantities / supply verbs in tenders
    SUPPLY_SPEC_TRIGGERS = [
        re.compile(r'^\s*(?:supply|installation|commissioning|laying|fabrication|provision|erection)\s+of\b', re.IGNORECASE),
        re.compile(r'\b(?:supply\s+and\s+installation|laying\s+and\s+commissioning)\b', re.IGNORECASE),
    ]

    # Knockout / Disqualification indicators
    KNOCKOUT_TRIGGERS = [
        re.compile(r'\b(?:disqualif|non-responsive|reject(?:ed|ion)?|ineligible|blacklisted|debarred)\b', re.IGNORECASE),
        re.compile(r'\b(?:bid\s+security|securing\s+declaration|earnest\s+money)\b', re.IGNORECASE),
        re.compile(r'\b(?:failing\s+to|failure\s+to|without\s+which)\b', re.IGNORECASE),
    ]

    # Type detection patterns
    TYPE_PATTERNS = {
        "eligibility": [
            re.compile(r'\b(?:active\s+taxpayer|fbr|ntn|strn|blacklisted|experience\s+of\s+at\s+least|years\s+of\s+(?:verifiable\s+)?experience|turnover|authorized\s+(?:partner|agent|distributor|dealer)|authorization\s+letter)\b', re.IGNORECASE)
        ],
        "compliance": [
            re.compile(r'\b(?:ppra|law|integrity\s+pact|iso\s*\d+|code|standard|regulations|inspection|satisfaction\s+of\s+engineer)\b', re.IGNORECASE)
        ],
        "commercial": [
            re.compile(r'\b(?:warranty|guarantee|validity|liquidated\s+damages|penalty|payment\s+terms|milestone|rates?|pricing|inclusiv(?:e|ing)\s+of\s+all\s+taxes|gst|sst|pkr|rupees)\b', re.IGNORECASE)
        ],
        "submission": [
            re.compile(r'\b(?:e-pads|eprocure|portal|sealed\s+envelope|tech-\d+|fin-\d+|deadline|original\s+affidavit|organogram)\b', re.IGNORECASE)
        ],
        "evaluation": [
            re.compile(r'\b(?:marks?|qcbs|score|scoring|threshold|criteria|evaluated|weight)\b', re.IGNORECASE)
        ],
        "technical": [
            re.compile(r'\b(?:specification|protocol|oidc|saml|oauth|uptime|sla|dr|rpo|rto|api|cable|voltage|booster|hardware|software|support|training)\b', re.IGNORECASE)
        ]
    }

    # Procuring agency duties (to be excluded from bidder requirements)
    AGENCY_DUTY_PATTERNS = [
        re.compile(r'\b(?:procuring\s+agency|agency|employer|department|client|pso|moitt)\s+(?:will\s+provide|shall\s+provide|reserves\s+the\s+right)\b', re.IGNORECASE)
    ]

    def scan_sentence(self, text: str, element_type: str = "sentence") -> Dict[str, Any]:
        """
        Analyzes a single sentence/line item and returns regex classification results.
        """
        text_clean = text.strip()
        matched_triggers = []

        # Check if this is exclusively an agency duty
        for pat in self.AGENCY_DUTY_PATTERNS:
            if pat.search(text_clean):
                return {
                    "is_requirement": False,
                    "classification": "ignored",
                    "reason": "agency_duty",
                    "matched_triggers": [],
                    "type": None,
                    "mandatory": None,
                    "knockout": None,
                    "knockout_type": None
                }

        # Check binding verbs
        for pat in self.BINDING_TRIGGERS:
            found = pat.findall(text_clean)
            if found:
                matched_triggers.extend([f.lower() for f in found])

        # Check supply/specification triggers
        for pat in self.SUPPLY_SPEC_TRIGGERS:
            if pat.search(text_clean):
                matched_triggers.append("supply_specification")

        # Table rows with specs are considered requirements by default
        if element_type == "table_row" and any(word in text_clean.lower() for word in ["supply", "installation", "commissioning", "cable", "meter", "booster"]):
            matched_triggers.append("table_spec_item")

        is_requirement = len(matched_triggers) > 0

        # Determine type
        detected_type = "technical" if is_requirement else None
        for t_name, patterns in self.TYPE_PATTERNS.items():
            if any(pat.search(text_clean) for pat in patterns):
                detected_type = t_name
                break

        # Determine mandatory
        is_mandatory = "yes"
        if "should" in matched_triggers and not any(k in matched_triggers for k in ["shall", "must", "mandatory"]):
            is_mandatory = "no"

        # Determine knockout
        is_knockout = "no"
        knockout_type = ""
        for pat in self.KNOCKOUT_TRIGGERS:
            if pat.search(text_clean):
                is_knockout = "yes"
                if "missing" in text_clean.lower() or "security" in text_clean.lower() or "declaration" in text_clean.lower():
                    knockout_type = "missing_document"
                elif "score" in text_clean.lower() or "turnover" in text_clean.lower():
                    knockout_type = "threshold"
                else:
                    knockout_type = "eligibility"
                break

        return {
            "is_requirement": is_requirement,
            "classification": "requirement" if is_requirement else "background",
            "matched_triggers": list(set(matched_triggers)),
            "type": detected_type,
            "mandatory": is_mandatory if is_requirement else None,
            "knockout": is_knockout if is_requirement else None,
            "knockout_type": knockout_type if is_knockout == "yes" else ""
        }
