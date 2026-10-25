import re
from typing import List, Dict, Any, Tuple


class ClaimChecker:
    """
    Code-based auditor for drafted proposal text:
    1. Vague-Claim Checker: Flags generic corporate buzzwords and unquantified puffery.
    2. Fact & Number Checker: Ensures every numerical metric, currency amount,
       and SLA citation is backed by an evidence tag (e.g., [EVID-01]).
    """

    # Fluff and buzzwords prohibited in technical proposals without supporting proof
    VAGUE_WORDS = [
        "industry-leading", "cutting-edge", "world-class", "seamless",
        "seamlessly", "best-in-class", "state-of-the-art", "revolutionary",
        "next-generation", "unmatched", "unparalleled", "market leader",
        "deep expertise", "extensive experience", "proven track record",
        "synergy", "synergies", "synergistic", "game-changing", "superior quality",
        "top-notch", "unrivaled", "highly qualified", "innovative solutions",
        "unmatched reliability", "robust solution", "effortless", "rock-solid"
    ]

    # Regex pattern to match evidence tags: e.g. [EVID-01], [EVID-14], [REF-02]
    EVIDENCE_TAG_PATTERN = re.compile(r'\[(?:EVID|REF|FACT)-\d+\]', re.IGNORECASE)

    # Regex patterns for facts and numbers that require evidence tags
    NUMBER_METRIC_PATTERNS = [
        # Percentages: 99.9%, 100% (no \b after % since % is non-word)
        re.compile(r'\b\d+(?:\.\d+)?\s*%'),
        # Currency: PKR 150 Million, Rs. 10,000, $5M
        re.compile(r'\b(?:pkr|rs\.?|\$)\s*\d+(?:,\d+)*(?:\.\d+)?(?:\s*(?:million|billion|k|m))?\b', re.IGNORECASE),
        re.compile(r'\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:million|billion)\s*(?:pkr|rs\.?|rupees|usd)?\b', re.IGNORECASE),
        # Metrics: 5 years, 24x7, 10,000 users, 5 minutes, 90 days
        re.compile(r'\b\d+\s+(?:years?|months?|days?|hours?|minutes?|seconds?)\b', re.IGNORECASE),
        re.compile(r'\b\d+x\d+(?:x\d+)?\b', re.IGNORECASE),  # e.g. 24x7, 24x7x365
        re.compile(r'\b\d+(?:,\d+)+\b'),  # Large comma-separated counts like 10,000 or 50,000
    ]

    def __init__(self, custom_vague_words: List[str] = None):
        self.vague_words = self.VAGUE_WORDS.copy()
        if custom_vague_words:
            self.vague_words.extend([w.lower() for w in custom_vague_words])

    def check_vague_claims(self, text: str) -> List[Dict[str, Any]]:
        """
        Scans text for prohibited vague buzzwords and corporate puffery.
        """
        flagged = []
        text_lower = text.lower()

        for word in self.vague_words:
            pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                flagged.append({
                    "word": word,
                    "position": match.start(),
                    "snippet": self._get_context_snippet(text, match.start(), match.end())
                })

        return flagged

    def check_facts_and_numbers(self, text: str) -> List[Dict[str, Any]]:
        """
        Checks whether sentences containing numbers, currencies, or metrics
        are properly tagged with an evidence reference [EVID-xx].
        """
        sentences = self._split_sentences(text)
        unsupported_facts = []

        for sent in sentences:
            sent_clean = sent.strip()
            if not sent_clean:
                continue

            has_evidence_tag = bool(self.EVIDENCE_TAG_PATTERN.search(sent_clean))

            # Find all numbers/metrics in this sentence
            found_metrics = []
            for pat in self.NUMBER_METRIC_PATTERNS:
                for match in pat.finditer(sent_clean):
                    found_metrics.append(match.group(0))

            # Deduplicate metrics
            found_metrics = list(set(found_metrics))

            # If sentence contains numbers/metrics but lacks an evidence tag -> FLAG
            if found_metrics and not has_evidence_tag:
                unsupported_facts.append({
                    "sentence": sent_clean,
                    "unsupported_metrics": found_metrics,
                    "status": "UNSUPPORTED_METRIC"
                })

        return unsupported_facts

    def audit_proposal_section(self, section_title: str, text: str) -> Dict[str, Any]:
        """
        Comprehensive audit returning total scores, flagged vague claims,
        and unsupported numerical claims.
        """
        vague_flags = self.check_vague_claims(text)
        unsupported_metrics = self.check_facts_and_numbers(text)

        evidence_tags_found = list(set(self.EVIDENCE_TAG_PATTERN.findall(text)))

        is_passed = (len(vague_flags) == 0 and len(unsupported_metrics) == 0)

        return {
            "section_title": section_title,
            "passed": is_passed,
            "vague_claim_count": len(vague_flags),
            "vague_claims": vague_flags,
            "unsupported_metric_count": len(unsupported_metrics),
            "unsupported_metrics": unsupported_metrics,
            "evidence_tags_cited": evidence_tags_found,
            "total_evidence_citations": len(evidence_tags_found)
        }

    def audit_with_llm_second_pass(self, section_title: str, text: str, extractor=None) -> Dict[str, Any]:
        """
        Two-stage audit: Word list & regex first (cheap & fast).
        Nemotron 3.5 Lightning second (only if first pass passes).
        """
        # Pass 1: Code-based check
        report = self.audit_proposal_section(section_title, text)
        if not report["passed"]:
            report["llm_second_pass"] = "SKIPPED_CODE_CHECK_FAILED"
            return report

        # Pass 2: LLM semantic check if extractor provided
        if extractor is not None:
            prompt = f"""You are a strict procurement bid auditor. 
Review the following proposal excerpt. Every factual or technical claim must be backed by an evidence citation tag like [EVID-xx].
Identify any unsubstantiated, vague, or exaggerated claims that slipped through keyword filters.

Proposal Text:
\"\"\"{text}\"\"\"

Output JSON:
{{
  "has_unsupported_claims": true/false,
  "flagged_claims": ["claim 1", "claim 2"],
  "reason": "explanation"
}}"""
            try:
                import json
                response = extractor.client.chat.completions.create(
                    model=extractor.model,
                    messages=[
                        {"role": "system", "content": "You are a government tender auditor flagging unsubstantiated claims in proposals."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                llm_res = json.loads(response.choices[0].message.content.strip())
                report["llm_second_pass"] = "PASSED" if not llm_res.get("has_unsupported_claims") else "FAILED"
                report["llm_flags"] = llm_res.get("flagged_claims", [])
                if llm_res.get("has_unsupported_claims"):
                    report["passed"] = False
            except Exception as e:
                report["llm_second_pass"] = f"ERROR: {str(e)}"
        else:
            report["llm_second_pass"] = "SKIPPED_NO_EXTRACTOR"

        return report

    def _split_sentences(self, text: str) -> List[str]:
        # Split on sentence boundaries
        splits = re.split(r'(?<=[.?!])\s+(?=[A-Z0-9\[])', text)
        return [s.strip() for s in splits if s.strip()]

    def _get_context_snippet(self, text: str, start: int, end: int, window: int = 40) -> str:
        snippet_start = max(0, start - window)
        snippet_end = min(len(text), end + window)
        snippet = text[snippet_start:snippet_end].replace('\n', ' ')
        return f"...{snippet}..."
