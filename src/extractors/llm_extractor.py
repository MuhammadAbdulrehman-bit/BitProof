import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class LLMExtractor:
    """
    LLM Extractor worker.
    Supports Groq, Nebius Token Factory (Nemotron), or standard OpenAI-compatible endpoints.
    """

    def __init__(self, provider: str = "auto", model: Optional[str] = None):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.nebius_key = os.getenv("NEBIUS_API_KEY")

        if provider == "nebius" or (provider == "auto" and self.nebius_key):
            self.client = OpenAI(
                base_url="https://api.tokenfactory.nebius.com/v1",
                api_key=self.nebius_key
            )
            self.model = model or "nvidia/nemotron-3.5-lightning"
            self.provider = "nebius"
        elif provider == "groq" or (provider == "auto" and self.groq_key):
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_key
            )
            self.model = model or "qwen/qwen3.8-27b"
            self.provider = "groq"
        else:
            raise ValueError(
                "No API key found! Please set GROQ_API_KEY or NEBIUS_API_KEY in your .env file."
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Classify the following tender clauses:\n{user_content}"}
                ],
                response_format={"type": "json_object"},
                max_tokens=600,
                temperature=0.0
            )

            raw_text = response.choices[0].message.content.strip()
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
