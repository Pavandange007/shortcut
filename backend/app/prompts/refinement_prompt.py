from __future__ import annotations

import json
from typing import Any

from app.models.schemas import (
    ContentAnalysisResult,
    StoryAnalysisResult,
    TimelineSegment,
    TitleHookAnalysisResult,
    ViralAnalysisResult,
)

REFINEMENT_PROMPT_VERSION = "v1"

SYSTEM = """You are a senior video editor refining an automatic rough-cut timeline.

Task: You are given the current timeline as segments with keep_audio flags and optional crossfades.
Adjust keep_audio (and crossfade hints if needed) to improve pacing, protect hooks/payoffs,
trim weak silence, and respect user feedback when provided.

Output rules:
- Return STRICT JSON only (no markdown, no extra text).
- JSON schema:
  {
    "timeline": [
      {
        "start_ms": number,
        "end_ms": number,
        "keep_audio": boolean,
        "crossfade_to_next_ms": number | null
      }
    ],
    "quality": {
      "pacing": number,
      "clarity": number,
      "hook_strength": number,
      "redundancy": number,
      "recommendations": string[]
    },
    "overall_quality_score": number,
    "should_continue": boolean,
    "summary": string
  }
- The timeline array MUST have the SAME LENGTH and the SAME start_ms/end_ms per index as the input.
  Only change keep_audio and crossfade_to_next_ms unless a segment is clearly invalid (then keep it unchanged).
- Scores are in [0,1]. Higher redundancy means more dead air to remove.
- should_continue: true if another refinement pass might meaningfully improve the edit.
"""


def build_refinement_prompt(
    *,
    iteration_index: int,
    timeline: list[TimelineSegment],
    content: ContentAnalysisResult,
    story: StoryAnalysisResult,
    viral: ViralAnalysisResult,
    titles: TitleHookAnalysisResult | None,
    user_feedback: dict[str, Any] | None,
) -> str:
    tl_json = json.dumps(
        [s.model_dump(mode="json") for s in timeline],
        ensure_ascii=False,
    )
    payload = {
        "content_moments": [m.model_dump(mode="json") for m in content.moments],
        "story_beats": [b.model_dump(mode="json") for b in story.beats],
        "viral_clips": [c.model_dump(mode="json", by_alias=True) for c in viral.clips],
        "titles": [x.model_dump(mode="json", by_alias=True) for x in titles.clips]
        if titles
        else [],
        "user_feedback": user_feedback or {},
    }
    ctx_json = json.dumps(payload, ensure_ascii=False)
    return "\n".join(
        [
            SYSTEM,
            "",
            f"Refinement iteration: {iteration_index}.",
            "",
            "Current timeline (edit in place; preserve segment count and boundaries):",
            tl_json,
            "",
            "Agent context (JSON):",
            ctx_json,
        ]
    )
