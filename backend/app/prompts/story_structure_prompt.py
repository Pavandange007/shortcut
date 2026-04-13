from __future__ import annotations

import json

from app.models.schemas import ContentAnalysisResult, TranscriptResponse

STORY_STRUCTURE_PROMPT_VERSION = "v1"

SYSTEM = """You are a story editor analyzing spoken video transcripts.

Task: Using the full transcript and the provided high-impact moment spans, infer a concise narrative structure.
Identify story beats with time ranges and roles.

Output rules:
- Return STRICT JSON only (no markdown, no extra text).
- JSON schema:
  {
    "beats": [
      {
        "start_ms": number,
        "end_ms": number,
        "role": "setup" | "tension" | "payoff" | "cta" | "other",
        "summary": string,
        "confidence": number
      }
    ],
    "narrative_summary": string,
    "confidence": number
  }
- Beats must not overlap excessively; cover the arc from hook to close when possible.
- confidence fields are in [0,1].
"""


def build_story_structure_prompt(
    *,
    raw_text: str,
    transcript: TranscriptResponse,
    content: ContentAnalysisResult,
) -> str:
    excerpt = raw_text.strip()
    if len(excerpt) > 12000:
        excerpt = excerpt[:12000] + "\n... [truncated]"

    moments_json = json.dumps(
        [m.model_dump(mode="json") for m in content.moments],
        ensure_ascii=False,
    )
    duration_ms = transcript.words[-1].end_ms if transcript.words else 0

    return "\n".join(
        [
            SYSTEM,
            "",
            f"Approximate duration (last word end): {duration_ms} ms.",
            "",
            "High-impact moments (from prior analysis):",
            moments_json,
            "",
            "Transcript:",
            excerpt,
        ]
    )
