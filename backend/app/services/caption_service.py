from __future__ import annotations

import re

from app.models.schemas import CaptionLine, WordTiming


def remap_word_timings_to_rough_cut(
    words: list[WordTiming],
    keep_segments: list[tuple[int, int]],
) -> list[WordTiming]:
    """
    Map source-video word times onto the rough-cut output timeline (ms from t=0).

    Each keep segment is concatenated in order; words are clipped to segment bounds.
    Audio crossfades shorten the real output slightly vs. sum(segment lengths); subtitle
    timing may drift by a small fraction of a second at joins (MVP).
    """

    result: list[WordTiming] = []
    cumulative_out = 0
    for seg_start, seg_end in keep_segments:
        for w in words:
            ws, we = w.start_ms, w.end_ms
            if we <= seg_start or ws >= seg_end:
                continue
            o0 = max(ws, seg_start)
            o1 = min(we, seg_end)
            if o1 <= o0:
                continue
            result.append(
                WordTiming(
                    text=w.text,
                    start_ms=cumulative_out + (o0 - seg_start),
                    end_ms=cumulative_out + (o1 - seg_start),
                    confidence=w.confidence,
                    segment_index=w.segment_index,
                )
            )
        cumulative_out += seg_end - seg_start
    return result


def _words_to_text(words: list[WordTiming]) -> str:
    raw = " ".join(w.text.strip() for w in words if w.text.strip())
    # Remove space before punctuation for readability.
    return re.sub(r"\s+([.,!?;:])", r"\1", raw).strip()


def group_words_into_captions(
    words: list[WordTiming],
    *,
    max_chars: int = 42,
    max_duration_ms: int = 2400,
) -> list[CaptionLine]:
    """
    Group word-level timestamps into readable caption lines.

    Heuristics:
    - Start a new line when adding the next word would exceed `max_chars`
      or `max_duration_ms`.
    - Produce human-readable text by joining words and removing spaces
      before punctuation.

    Args:
        words: Word timings from Whisper.
        max_chars: Maximum character count per caption line.
        max_duration_ms: Maximum time span per caption line.

    Returns:
        CaptionLine list with start/end millisecond accuracy.
    """

    if not words:
        return []

    captions: list[CaptionLine] = []
    current_words: list[WordTiming] = []
    current_start_ms: int | None = None
    current_text_len: int = 0

    def finalize() -> None:
        nonlocal current_words, current_start_ms, current_text_len
        if not current_words or current_start_ms is None:
            return

        start_ms = current_words[0].start_ms
        end_ms = current_words[-1].end_ms
        if end_ms <= start_ms:
            return

        text = _words_to_text(current_words)
        captions.append(
            CaptionLine(
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                words=current_words,
            )
        )
        current_words = []
        current_start_ms = None
        current_text_len = 0

    for w in words:
        w_text = w.text.strip()
        if not w_text:
            continue

        if current_start_ms is None:
            current_start_ms = w.start_ms
            current_words = [w]
            current_text_len = len(w_text)
            continue

        prospective_len = current_text_len + 1 + len(w_text)
        prospective_duration_ms = w.end_ms - current_start_ms

        if prospective_len > max_chars or prospective_duration_ms > max_duration_ms:
            finalize()
            current_start_ms = w.start_ms
            current_words = [w]
            current_text_len = len(w_text)
            continue

        current_words.append(w)
        current_text_len = prospective_len

    finalize()
    return captions

