from __future__ import annotations

import json

from app.models.schemas import ContentAnalysisResult, StoryAnalysisResult

VIRAL_POTENTIAL_PROMPT_VERSION = "v1"

SYSTEM = """You are a short-form social video strategist (YouTube Shorts, TikTok, Reels).

Task: Propose clip candidates that could perform well as standalone posts.
Use the story beats and high-impact moments as evidence.

Output rules:
- Return STRICT JSON only (no markdown, no extra text).
- JSON schema:
  {
    "clips": [
      {
        "start_ms": number,
        "end_ms": number,
        "viral_score": number,
        "rationale": string,
        "platform_recommendations": string[]
      }
    ],
    "confidence": number
  }
- Prefer clips roughly 8–45 seconds when the source allows (shorter is OK for weak material).
- viral_score in [0,1]; suggest 3–8 clips when possible.
- platform_recommendations: short labels like "tiktok", "reels", "shorts".
"""


def build_viral_potential_prompt(
    *,
    content: ContentAnalysisResult,
    story: StoryAnalysisResult,
) -> str:
    moments_json = json.dumps(
        [m.model_dump(mode="json") for m in content.moments],
        ensure_ascii=False,
    )
    beats_json = json.dumps(
        [b.model_dump(mode="json") for b in story.beats],
        ensure_ascii=False,
    )

    return "\n".join(
        [
            SYSTEM,
            "",
            "Story beats:",
            beats_json,
            "",
            "High-impact moments:",
            moments_json,
            "",
            "Narrative summary:",
            story.narrative_summary or "(none)",
        ]
    )
