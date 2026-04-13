from __future__ import annotations

import json

from app.models.schemas import ViralAnalysisResult

TITLE_HOOK_PROMPT_VERSION = "v1"

SYSTEM = """You are a growth copywriter for short-form video.

Task: For each viral clip candidate (by index order), write scroll-stopping titles and hooks.
Provide platform-flavored variants where useful.

Output rules:
- Return STRICT JSON only (no markdown, no extra text).
- JSON schema:
  {
    "clips": [
      {
        "clip_index": number,
        "title_hook_set": {
          "primary_title": string,
          "hooks": string[],
          "ab_variants": string[]
        }
      }
    ],
    "confidence": number
  }
- clip_index is 0-based matching the input clips array order.
- hooks: 2–5 short lines; ab_variants: 2–4 alternate titles.
"""


def build_title_hook_prompt(*, viral: ViralAnalysisResult) -> str:
    clips_json = json.dumps(
        [c.model_dump(mode="json", by_alias=True) for c in viral.clips],
        ensure_ascii=False,
    )
    return "\n".join(
        [
            SYSTEM,
            "",
            "Viral clip candidates (preserve order; clip_index matches array index):",
            clips_json,
        ]
    )
