"""LLM-based article summarization and relevance scoring.

Uses Claude Sonnet to:
1. Produce a 3-sentence Chinese summary of each paper
2. Score relevance (1-5) for each active interest category (CRC/SDS/CVDL)

Design notes:
- Interest descriptions come from Supabase `interests` table — edit there, not in code.
- JSON-mode output for reliability; retries with exponential backoff.
- Daily budget enforced upstream in the orchestrator, not here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("journal_tracker")


@dataclass
class LLMResult:
    summary_zh: str
    relevance: dict[str, int]   # {'CRC': 4, 'SDS': 2, 'CVDL': 1}
    reasoning: str              # debug-only; not persisted
    model: str


class LLMSummarizer:
    """Summarize and score one article at a time using Claude."""

    SYSTEM_PROMPT = """You are a research assistant helping a colorectal surgeon and PhD student triage medical literature.

For each paper, you produce:
1. A concise 3-sentence Chinese summary (traditional Chinese, 繁體中文)
2. Relevance scores (1-5) for each of the user's interest categories

Scoring rubric:
  1 = Not relevant at all
  2 = Tangentially related
  3 = Moderately relevant; worth a skim
  4 = Highly relevant; worth reading carefully
  5 = Core to the interest; must-read

Always respond with valid JSON only. No markdown, no commentary outside the JSON object."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929") -> None:
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def summarize(
        self,
        title: str,
        abstract: str | None,
        interests: list[dict[str, Any]],
    ) -> LLMResult:
        """Summarize + score one paper.

        Args:
            title: article title
            abstract: article abstract (may be empty/None)
            interests: list of interest dicts with 'code', 'name', 'description'
        """
        interest_block = "\n".join(
            f"- {it['code']} ({it['name']}): {it['description']}"
            for it in interests
        )
        codes = [it["code"] for it in interests]
        relevance_schema = ", ".join(f'"{c}": <int 1-5>' for c in codes)

        user_prompt = f"""Paper to evaluate:
TITLE: {title}

ABSTRACT: {abstract or "(no abstract available — score based on title only)"}

User's interest categories:
{interest_block}

Return a JSON object with this exact structure:
{{
  "summary_zh": "<three sentences in traditional Chinese, each under 60 characters>",
  "relevance": {{ {relevance_schema} }},
  "reasoning": "<one-sentence justification for the scores, in English>"
}}"""

        raw = self._call_api(user_prompt)
        parsed = self._parse_response(raw, codes)

        return LLMResult(
            summary_zh=parsed["summary_zh"],
            relevance=parsed["relevance"],
            reasoning=parsed.get("reasoning", ""),
            model=self.model,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _call_api(self, user_prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        return "".join(text_blocks).strip()

    def _parse_response(self, raw: str, expected_codes: list[str]) -> dict[str, Any]:
        """Parse JSON, strip markdown fences if present, validate shape."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove leading ```json or ``` and trailing ```
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}\nRaw: {raw[:500]}")
            raise

        # Validate
        if "summary_zh" not in data or not isinstance(data["summary_zh"], str):
            raise ValueError(f"Missing or invalid 'summary_zh' in response: {data}")
        if "relevance" not in data or not isinstance(data["relevance"], dict):
            raise ValueError(f"Missing or invalid 'relevance' in response: {data}")

        # Ensure all expected interest codes are present, clamp to 1-5
        for code in expected_codes:
            v = data["relevance"].get(code)
            if not isinstance(v, int) or not (1 <= v <= 5):
                logger.warning(f"Relevance for {code} invalid ({v}), defaulting to 1")
                data["relevance"][code] = 1
            else:
                data["relevance"][code] = max(1, min(5, int(v)))

        return data
