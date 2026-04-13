from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.config import settings
from app.models.schemas import CaptionLine

logger = logging.getLogger(__name__)


def resolve_ffprobe_executable() -> Path | None:
    """``ffprobe`` next to configured ``ffmpeg``, or ``shutil.which("ffprobe")``."""

    ff = resolve_ffmpeg_executable()
    if ff is not None:
        name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
        sibling = ff.parent / name
        if sibling.is_file():
            return sibling
    found = shutil.which("ffprobe")
    return Path(found) if found else None


def probe_video_dimensions(path: Path) -> tuple[int, int] | None:
    """Return ``(width, height)`` of the first video stream, or ``None`` if unknown."""

    exe = resolve_ffprobe_executable()
    if exe is None or not path.is_file():
        return None
    cmd = [
        str(exe),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None
    streams = data.get("streams") or []
    if not streams:
        return None
    w = streams[0].get("width")
    h = streams[0].get("height")
    if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
        return (w, h)
    return None


def default_os_fonts_dir() -> Path | None:
    """Directory libass should search (Windows/macOS/Linux); ``None`` if unknown."""

    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        p = Path(windir) / "Fonts"
        return p if p.is_dir() else None
    if sys.platform == "darwin":
        p = Path("/System/Library/Fonts")
        return p if p.is_dir() else None
    for candidate in (Path("/usr/share/fonts"), Path("/usr/local/share/fonts")):
        if candidate.is_dir():
            return candidate
    return None


def resolve_ffmpeg_executable() -> Path | None:
    """
    Return the ffmpeg binary: valid ``FFMPEG_BIN`` if set, otherwise ``shutil.which("ffmpeg")``.
    A non-existent ``FFMPEG_BIN`` (e.g. a leftover placeholder path) is ignored so PATH can still win.
    """
    raw = settings.ffmpeg_bin.strip()
    if raw:
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return candidate
    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def ffmpeg_available() -> bool:
    """True if a usable ffmpeg binary exists (configured path or PATH)."""
    return resolve_ffmpeg_executable() is not None


def get_ffmpeg_status() -> tuple[bool, str | None]:
    """Return ``(available, resolved_executable_path)`` for health checks and logging."""
    exe = resolve_ffmpeg_executable()
    if exe is None:
        return (False, None)
    return (True, str(exe))


def log_ffmpeg_startup_status() -> None:
    """Log a single startup line to stderr (``app`` logger) for operators."""
    log = logging.getLogger("app")
    available, path = get_ffmpeg_status()
    raw_bin = settings.ffmpeg_bin.strip()
    if available:
        log.info(
            "startup: ffmpeg ok path=%s FFMPEG_BIN=%r",
            path,
            raw_bin or "",
        )
    else:
        log.warning(
            "startup: ffmpeg missing — rough-cut/caption burn-in will fail until ffmpeg is on PATH or "
            "FFMPEG_BIN points to ffmpeg.exe (current FFMPEG_BIN=%r)",
            raw_bin or "(unset)",
        )


def _ffmpeg_exe_or_raise() -> Path:
    raw = settings.ffmpeg_bin.strip()
    configured_missing = bool(raw) and not Path(raw).expanduser().is_file()
    exe = resolve_ffmpeg_executable()
    if exe is not None:
        if configured_missing:
            logger.warning(
                "FFMPEG_BIN=%r is not a valid file; using ffmpeg from PATH (%s)",
                raw,
                exe,
            )
        return exe
    if raw:
        raise FileNotFoundError(
            f"FFmpeg not found at FFMPEG_BIN={raw!r} and not on PATH. "
            "Install FFmpeg, fix the path to ffmpeg.exe, or clear FFMPEG_BIN if ffmpeg is on PATH."
        )
    raise FileNotFoundError(
        "FFmpeg executable not found in PATH. Install FFmpeg, add it to PATH, or set "
        "FFMPEG_BIN in .env to the full path (e.g. C:/ffmpeg/bin/ffmpeg.exe)."
    )


def ms_to_ass_time(ms: int) -> str:
    """
    Convert milliseconds to ASS timestamp (H:MM:SS.CS).

    Args:
        ms: Milliseconds.

    Returns:
        ASS timestamp string.
    """

    ms = max(0, int(ms))
    centiseconds = int(round(ms / 10.0))
    hours = centiseconds // 360000
    centiseconds %= 360000
    minutes = centiseconds // 6000
    centiseconds %= 6000
    seconds = centiseconds // 100
    cs = centiseconds % 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"


def _path_for_ffmpeg_subtitles_filter(path: Path) -> str:
    """
    Build a path string for the ``subtitles`` video filter.

    Filter arguments use ``:`` as a separator; a Windows drive letter (``C:``)
    must be written as ``C\\:`` or parsing breaks and FFmpeg exits with an error.
    """
    resolved = path.resolve()
    s = resolved.as_posix()
    if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
        s = f"{s[0]}\\:{s[2:]}"
    return s.replace("'", r"\'")


def _subtitles_video_filter_arg(ass_path: Path, fonts_dir: Path | None) -> str:
    """Single ``-vf`` value for libass burn-in (optional OS fonts dir for glyph lookup)."""

    ass_esc = _path_for_ffmpeg_subtitles_filter(ass_path)
    if fonts_dir is not None and fonts_dir.is_dir():
        fd = fonts_dir.resolve().as_posix()
        if len(fd) >= 2 and fd[1] == ":" and fd[0].isalpha():
            fd = f"{fd[0]}\\:{fd[2:]}"
        fd = fd.replace("'", r"\'")
        return f"subtitles='{ass_esc}':fontsdir='{fd}'"
    return f"subtitles='{ass_esc}'"


def _run_ffmpeg(cmd: list[str], *, context: str) -> None:
    """Run FFmpeg; raise ``RuntimeError`` with log output if it fails."""
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        return
    err = (proc.stderr or "").strip()
    if not err:
        err = (proc.stdout or "").strip()
    tail = err[-4000:] if len(err) > 4000 else err
    raise RuntimeError(
        f"FFmpeg {context} failed (exit {proc.returncode}): {tail or '(no output)'}"
    )


def _escape_ass_text(text: str) -> str:
    # Minimal escaping to avoid override tags breaking rendering.
    return (
        text.replace("\\", "\\\\")
        .replace("{", "")
        .replace("}", "")
        .replace("\n", r"\N")
    )


def burn_in_captions(
    video_path: Path,
    captions: list[CaptionLine],
    output_path: Path,
    *,
    font_name: str = "Arial",
    font_size: int | None = None,
    fonts_dir: Path | None = None,
) -> None:
    """
    Burn captions into the video using FFmpeg + ASS subtitles.

    Args:
        video_path: Input video file.
        captions: Caption lines with word-accurate timestamps.
        output_path: Output MP4 file path.
        font_name: Font used by ASS.
        font_size: Font size in ASS points; ``None`` scales from video height.
        fonts_dir: Optional font search path for libass (defaults to OS fonts when found).
    """

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not captions:
        logger.warning(
            "ffmpeg: caption burn-in — zero lines; copying video without re-encode"
        )
        shutil.copy2(video_path, output_path)
        return

    dims = probe_video_dimensions(video_path)
    if dims is not None:
        play_w, play_h = dims
    else:
        play_w, play_h = 1920, 1080
    if font_size is None:
        font_size = max(28, min(72, int(play_h / 16)))

    resolved_fonts = fonts_dir if fonts_dir is not None else default_os_fonts_dir()
    if resolved_fonts is not None:
        logger.info(
            "ffmpeg: caption burn-in fontsdir=%s play_res=%dx%d font_size=%d lines=%d",
            resolved_fonts,
            play_w,
            play_h,
            font_size,
            len(captions),
        )
    else:
        logger.info(
            "ffmpeg: caption burn-in (no fontsdir) play_res=%dx%d font_size=%d lines=%d",
            play_w,
            play_h,
            font_size,
            len(captions),
        )

    ass_lines: list[str] = []
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append("ScaledBorderAndShadow: yes")
    ass_lines.append(f"PlayResX: {play_w}")
    ass_lines.append(f"PlayResY: {play_h}")
    ass_lines.append("WrapStyle: 0")
    ass_lines.append("")
    ass_lines.append("[V4+ Styles]")
    ass_lines.append(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    # PrimaryColour is &HAABBGGRR (ASS). White text, thick dark outline for contrast on any footage.
    ass_lines.append(
        f"Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,4,2,2,20,20,80,1"
    )
    ass_lines.append("")
    ass_lines.append("[Events]")
    ass_lines.append(
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    )

    for line in captions:
        start = ms_to_ass_time(line.start_ms)
        end = ms_to_ass_time(line.end_ms)
        text = _escape_ass_text(line.text)
        ass_lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    ass_text = "\n".join(ass_lines)

    # Use a temp file because FFmpeg expects a real path.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".ass",
        delete=False,
    ) as f:
        ass_path = Path(f.name)
        f.write(ass_text)

    try:
        video_path_str = str(video_path).replace("\\", "/")
        output_path_str = str(output_path).replace("\\", "/")
        vf = _subtitles_video_filter_arg(ass_path, resolved_fonts)

        ffmpeg_exe = _ffmpeg_exe_or_raise()

        cmd = [
            str(ffmpeg_exe),
            "-y",
            "-i",
            video_path_str,
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            output_path_str,
        ]

        _run_ffmpeg(cmd, context="caption burn-in")
    finally:
        try:
            os.remove(ass_path)
        except OSError:
            pass


def export_rough_cut(
    video_path: Path,
    keep_segments: list[tuple[int, int]],
    output_path: Path,
    *,
    crossfade_ms: int = 150,
) -> None:
    """
    Export a rough cut by stitching timeline keep segments.

    - Video: concatenated back-to-back.
    - Audio: optional crossfade via `acrossfade` between keep segments.

    Note:
        Video and audio are not frame-overlapped; audio length may be
        slightly shorter when crossfading. Crossfade duration is expected
        to be small (e.g., 100-200ms) for MVP.
    """

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not keep_segments:
        raise ValueError("keep_segments must not be empty.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    seg_count = len(keep_segments)
    crossfade_s = max(0.0, crossfade_ms / 1000.0)

    # Build a filter graph that trims each keep segment, then concatenates video
    # and mixes audio with optional crossfades.
    filters: list[str] = []
    for idx, (start_ms, end_ms) in enumerate(keep_segments):
        start_s = start_ms / 1000.0
        end_s = end_ms / 1000.0
        filters.append(
            f"[0:v]trim=start={start_s}:end={end_s},setpts=PTS-STARTPTS[v{idx}]"
        )
        filters.append(
            f"[0:a]atrim=start={start_s}:end={end_s},asetpts=PTS-STARTPTS[a{idx}]"
        )

    # Video concat
    v_inputs = "".join(f"[v{i}]" for i in range(seg_count))
    filters.append(
        f"{v_inputs}concat=n={seg_count}:v=1:a=0[vout]"
    )

    # Audio concat or acrossfade
    if seg_count == 1 or crossfade_s <= 0.0:
        a_inputs = "".join(f"[a{i}]" for i in range(seg_count))
        filters.append(
            f"{a_inputs}concat=n={seg_count}:v=0:a=1[aout]"
        )
    else:
        # Chain acrossfades: af1 combines a0+a1, af2 combines af1+a2, etc.
        filters.append(
            f"[a0][a1]acrossfade=d={crossfade_s}:c1=tri:c2=tri[af1]"
        )
        for i in range(2, seg_count):
            filters.append(
                f"[af{i-1}][a{i}]acrossfade=d={crossfade_s}:c1=tri:c2=tri[af{i}]"
            )
        filters.append(f"[af{seg_count-1}]anull[aout]")

    filter_complex = ";".join(filters)

    ffmpeg_exe = _ffmpeg_exe_or_raise()

    video_path_str = str(video_path).replace("\\", "/")
    output_path_str = str(output_path).replace("\\", "/")

    cmd = [
        str(ffmpeg_exe),
        "-y",
        "-i",
        video_path_str,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        output_path_str,
    ]

    _run_ffmpeg(cmd, context="rough-cut export")


def export_clip(
    *,
    video_path: Path,
    start_ms: int,
    end_ms: int,
    output_path: Path,
) -> None:
    """
    Export a single MP4 clip from ``video_path`` for preview.

    Uses a fast H.264/AAC encode to avoid keyframe/codec edge-cases when cutting with stream-copy.
    """

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    start_ms_i = max(0, int(start_ms))
    end_ms_i = max(0, int(end_ms))
    if end_ms_i <= start_ms_i:
        raise ValueError("end_ms must be greater than start_ms.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_exe = _ffmpeg_exe_or_raise()
    start_s = start_ms_i / 1000.0
    duration_s = (end_ms_i - start_ms_i) / 1000.0

    cmd = [
        str(ffmpeg_exe),
        "-y",
        "-i",
        str(video_path).replace("\\", "/"),
        "-ss",
        f"{start_s:.3f}",
        "-t",
        f"{duration_s:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_path).replace("\\", "/"),
    ]
    _run_ffmpeg(cmd, context="clip export")

