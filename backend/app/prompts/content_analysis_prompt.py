from __future__ import annotations

from app.models.schemas import WordTiming

CONTENT_ANALYSIS_PROMPT_VERSION = "v1"

SYSTEM = """You are a senior video editor analyzing spoken content for high-impact moments.

Task: From the transcript (with approximate timing hints), identify moments viewers are most likely to care about:
- strong hooks, punchlines, emotional peaks, clear value statements, calls-to-action
- avoid filler-only regions unless they set up a payoff

Output rules:
- Return STRICT JSON only (no markdown, no extra text).
- JSON schema:
  {
    "moments": [
      {
        "start_ms": number,
        "end_ms": number,
        "label": string,
        "impact_score": number,
        "evidence": string
      }
    ],
    "confidence": number,
    "summary": string
  }
- Provide 4–12 moments when possible; impact_score in [0,1]; start_ms < end_ms.
- evidence should be a short verbatim quote from the transcript when possible.
"""


def _format_word_hints(words: list[WordTiming], max_words: int = 400) -> str:
    parts: list[str] = []
    for w in words[:max_words]:
        parts.append(f"[{w.start_ms}-{w.end_ms}ms] {w.text}")
    if len(words) > max_words:
        parts.append(f"... ({len(words) - max_words} more words omitted)")
    return "\n".join(parts)


def build_content_analysis_prompt(*, raw_text: str, words: list[WordTiming]) -> str:
    excerpt = raw_text.strip()
    if len(excerpt) > 14000:
        excerpt = excerpt[:14000] + "\n... [transcript truncated]"

    duration_ms = words[-1].end_ms if words else 0
    hints = _format_word_hints(words) if words else "(no word timings)"

    return "\n".join(
        [
            SYSTEM,
            "",
            f"Approximate total duration from last word end: {duration_ms} ms.",
            "",
            "Transcript:",
            excerpt,
            "",
            "Word timing hints (subset):",
            hints,
        ]
    )
