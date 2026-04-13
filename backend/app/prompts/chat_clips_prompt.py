from __future__ import annotations

import json

from app.models.schemas import ContentAnalysisResult, StoryAnalysisResult

CHAT_CLIPS_PROMPT_VERSION = "v1"

SYSTEM = """You are a short-form social video strategist (YouTube Shorts, TikTok, Reels).

Task: Propose clip candidates that could perform well as standalone posts, given story beats and high-impact moments.
The user has provided an explicit request. Follow it as closely as possible while staying grounded in the evidence.

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
- start_ms/end_ms must be consistent with the provided timing evidence (beats/moments).
- viral_score in [0,1].
"""


def build_chat_clips_prompt(
    *,
    user_request: str,
    target_duration_s: int,
    clip_count: int,
    content: ContentAnalysisResult,
    story: StoryAnalysisResult,
) -> str:
    """Build a constrained clip-selection prompt for chat requests.

    Args:
        user_request: The user's natural language request.
        target_duration_s: Preferred clip duration in seconds.
        clip_count: Preferred number of clips to return.
        content: Content analysis result (moments + summary).
        story: Story structure result (beats + narrative summary).

    Returns:
        A prompt string for the LLM.
    """

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
            f"User request: {user_request}",
            f"Constraints: Return ~{clip_count} clips. Prefer each clip to be ~{target_duration_s} seconds.",
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

