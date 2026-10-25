import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class LLMExtractor:
    """
    LLM Extractor worker.
    Supports NVIDIA NIM (Nemotron 3.5 Lightning / Nemotron Parse),
    Nebius Token Factory, or Groq fallback.
    """

    def __init__(self, provider: str = "auto", model: Optional[str] = None):
        self.nvidia_key = os.getenv("NVIDIA_API_KEY")
        self.nebius_key = os.getenv("NEBIUS_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

        # 1. NVIDIA NIM (Official build.nvidia.com Nemotron)
        if provider == "nvidia" or (provider == "auto" and self.nvidia_key):
            self.client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.nvidia_key
            )
            self.model = model or "nvidia/nemotron-3.5-lightning-30b-a3b"
            self.provider = "nvidia"

        # 2. Nebius Token Factory
        elif provider == "nebius" or (provider == "auto" and self.nebius_key):
            self.client = OpenAI(
                base_url="https://api.tokenfactory.nebius.com/v1",
                api_key=self.nebius_key
            )
            self.model = model or "nvidia/nemotron-3.5-lightning"
            self.provider = "nebius"

        # 3. Groq Fast Fallback
        elif provider == "groq" or (provider == "auto" and self.groq_key):
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_key
            )
            self.model = model or "qwen/qwen3.8-27b"
            self.provider = "groq"
        else:
            raise ValueError(
                "No API key found! Please set NVIDIA_API_KEY, NEBIUS_API_KEY, or GROQ_API_KEY in .env."
            )

    def extract_requirements_batch(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sends a batch of candidate sentences to the LLM and classifies each one.
        """
        items_payload = [
            {
                "sentence_id": c["sentence_id"],
                "section": c.get("section", "GENERAL"),
                "text": c["text"]
            }
            for c in candidates
        ]

        system_prompt = """You are an expert procurement auditor classifying clauses from a public tender (RFP).
For each candidate sentence, determine if it is a REQUIREMENT for the bidder/vendor or purely non-binding background/boilerplate.

GOLDEN RULE: If a bidder could lose marks, be disqualified, or be in breach of contract by ignoring the sentence, it is a REQUIREMENT.
DO NOT label procuring agency obligations, standard generic boilerplate, or blank form placeholders as requirements.

For each sentence, output a JSON object with:
- sentence_id: exact string from input
- is_requirement: true or false
- type: "technical" | "eligibility" | "compliance" | "commercial" | "submission" | "evaluation" (or null if is_requirement=false)
- mandatory: "yes" | "no" | "conditional" (or null if is_requirement=false)
- knockout: "yes" | "no" (or null if is_requirement=false)
- knockout_type: "missing_document" | "eligibility" | "threshold" | "process" (only if knockout="yes", otherwise "")
- scored_criterion: "yes" | "no" (or null if is_requirement=false)
- marks: numeric string if marks are assigned (e.g. "25", "10.5"), otherwise ""
- notes: brief reason (e.g., "Active Taxpayers List mandatory", "OIDC OAuth2 support", "Background description")

Return a JSON object containing a 'results' key with an array of objects for each input sentence:
{"results": [...]}"""

        user_content = json.dumps(items_payload, indent=2)

        try:
            # Nemotron-3.5-lightning uses internal reasoning, so we provide ample max_tokens
            max_tokens = 1500 if self.provider == "nvidia" else 600

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Classify the following tender clauses:\n{user_content}"}
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=0.0
            )

            raw_text = response.choices[0].message.content or ""
            if not raw_text.strip():
                # Fallback if content was placed in reasoning or empty
                return []

            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                for val in parsed.values():
                    if isinstance(val, list):
                        return val
                return [parsed]
            elif isinstance(parsed, list):
                return parsed
            return []

        except Exception as e:
            print(f"Error calling LLM ({self.provider}/{self.model}): {e}")
            return []

    def adjudicate_disagreement(
        self,
        sentence_id: str,
        text: str,
        regex_label: Dict[str, Any],
        llm_label: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adjudicator (Nemotron Ultra / High Reasoning):
        Resolves conflicts where Regex and Fast LLM disagree.
        Ensures NO sentence passes by without a final authoritative decision.
        """
        system_prompt = """You are the Senior Chief Procurement Adjudicator.
A rule-based regex scanner and a fast classification model disagree on whether the following RFP tender sentence is a binding vendor requirement.
Analyze the sentence thoroughly and make the definitive ruling.

Input format will provide:
- Sentence ID & Text
- Regex Scan determination
- Fast LLM determination

Respond with a single JSON object:
{
  "sentence_id": "...",
  "final_classification": "requirement" | "background" | "ignored",
  "type": "technical" | "eligibility" | "compliance" | "commercial" | "submission",
  "mandatory": "yes" | "no",
  "knockout": "yes" | "no",
  "confidence": 0.95,
  "adjudication_rationale": "one sentence explaining why"
}"""

        user_payload = {
            "sentence_id": sentence_id,
            "text": text,
            "regex_verdict": regex_label,
            "llm_verdict": llm_label
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, indent=2)}
                ],
                response_format={"type": "json_object"},
                max_tokens=800,
                temperature=0.0
            )
            raw = response.choices[0].message.content or "{}"
            return json.loads(raw)
        except Exception as e:
            print(f"Error in adjudication: {e}")
            # Fallback to safer side: if either thought it was a requirement, treat as requirement
            return {
                "sentence_id": sentence_id,
                "final_classification": "requirement",
                "type": "compliance",
                "mandatory": "yes",
                "knockout": "no",
                "confidence": 0.5,
                "adjudication_rationale": "Fallback adjudication on error"
            }
