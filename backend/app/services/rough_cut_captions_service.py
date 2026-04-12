from __future__ import annotations

import logging
import os
from pathlib import Path

from app.models.schemas import WordTiming
from app.services.caption_service import group_words_into_captions, remap_word_timings_to_rough_cut
from app.services.ffmpeg_service import burn_in_captions, export_rough_cut

logger = logging.getLogger(__name__)


def export_rough_cut_and_burn_captions(
    source_video: Path,
    keep_segments: list[tuple[int, int]],
    rough_cut_path: Path,
    transcript_words: list[WordTiming],
    *,
    crossfade_ms: int = 150,
) -> None:
    """Export silence-stripped rough cut, then burn captions timed for that output."""

    export_rough_cut(
        source_video,
        keep_segments,
        rough_cut_path,
        crossfade_ms=crossfade_ms,
    )
    burn_captions_onto_existing_rough_cut(
        rough_cut_path=rough_cut_path,
        transcript_words=transcript_words,
        keep_segments=keep_segments,
    )


def burn_captions_onto_existing_rough_cut(
    *,
    rough_cut_path: Path,
    transcript_words: list[WordTiming],
    keep_segments: list[tuple[int, int]],
) -> None:
    """
    Burn subtitles into ``rough_cut_path`` using words remapped from source time to rough-cut time.

    Writes to a sibling temp file, then replaces the rough cut atomically.
    """

    remapped = remap_word_timings_to_rough_cut(transcript_words, keep_segments)
    if not remapped:
        raise RuntimeError(
            "Caption burn-in: no words overlap the kept-audio timeline segments "
            "(transcript vs timeline mismatch)."
        )
    caption_lines = group_words_into_captions(remapped)
    if not caption_lines:
        raise RuntimeError("Caption burn-in: grouped caption lines are empty after timeline remap.")
    logger.info(
        "rough_cut captions: burning %d lines (%d remapped words) onto %s",
        len(caption_lines),
        len(remapped),
        rough_cut_path.name,
    )
    tmp = rough_cut_path.with_name(
        f"{rough_cut_path.stem}.captioning{rough_cut_path.suffix}"
    )
    try:
        burn_in_captions(rough_cut_path, caption_lines, tmp)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, rough_cut_path)
