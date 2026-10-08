from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Iterable, Optional


@dataclass
class Word:
    start: float
    end: float
    text: str
    probability: Optional[float] = None


@dataclass
class Cue:
    start: float
    end: float
    text: str


@dataclass
class MediaInfo:
    has_video: bool
    width: Optional[int] = None
    height: Optional[int] = None
    audio_codec: Optional[str] = None


# Sentence-final punctuation. Includes the Devanagari/Bengali danda (। ॥), the Urdu full stop (۔),
# the Arabic question mark (؟) and the ellipsis, in addition to . ! ?
SENTENCE_END = re.compile(r"[.!?…।॥۔؟][\"'”’)\]]?$")

# Audio codecs that can be stream-copied into an MP4 container without re-encoding.
MP4_COPY_SAFE_AUDIO = {"aac", "mp3", "mp2", "ac3", "eac3", "opus", "flac", "alac"}


def _clean_token(token: str) -> str:
    return token.strip()


def _join_words(words: list[str]) -> str:
    text = " ".join(w for w in words if w)
    text = re.sub(r"\s+([,.;:!?%])", r"\1", text)
    text = re.sub(r"([([{])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]}])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _wrap_two_lines(text: str, max_chars_per_line: int = 42) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars_per_line:
        return text

    words = text.split()
    if not words:
        return text

    # Choose a split near the visual midpoint while respecting line length.
    best = None
    midpoint = len(text) / 2
    for i in range(1, len(words)):
        left = " ".join(words[:i])
        right = " ".join(words[i:])
        overflow = max(0, len(left) - max_chars_per_line) + max(0, len(right) - max_chars_per_line)
        balance = abs(len(left) - midpoint) + abs(len(right) - midpoint)
        score = overflow * 1000 + balance
        if best is None or score < best[0]:
            best = (score, left, right)
    if best:
        return best[1] + "\n" + best[2]
    return text


def _fits(text: str, max_chars_per_line: int, max_lines: int) -> bool:
    """True if `text` can be displayed in at most `max_lines` lines of `max_chars_per_line`."""
    wrapped = _wrap_two_lines(text, max_chars_per_line) if max_lines >= 2 else text
    lines = wrapped.split("\n")
    return len(lines) <= max_lines and all(len(line) <= max_chars_per_line for line in lines)


def words_to_cues(
    words: list[Word],
    max_chars_per_line: int = 42,
    max_lines: int = 2,
    max_duration: float = 6.0,
    min_duration: float = 0.7,
    max_gap: float = 0.8,
) -> list[Cue]:
    if not words:
        return []

    cues: list[Cue] = []
    current: list[Word] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = _join_words([w.text for w in current])
        end = max(current[-1].end, current[0].start + min_duration)
        cues.append(Cue(current[0].start, end, _wrap_two_lines(text, max_chars_per_line)))
        current = []

    for word in words:
        if not current:
            current = [word]
            continue

        candidate_text = _join_words([w.text for w in current + [word]])
        previous_text = _join_words([w.text for w in current])
        duration = word.end - current[0].start
        gap = word.start - current[-1].end
        sentence_break = bool(SENTENCE_END.search(previous_text))

        should_split = (
            # Check the wrapped result, not just total length, so no line exceeds max_chars_per_line.
            not _fits(candidate_text, max_chars_per_line, max_lines)
            or duration > max_duration
            or gap > max_gap
            or (sentence_break and len(previous_text) >= max_chars_per_line // 2)
        )

        if should_split:
            flush()
            current = [word]
        else:
            current.append(word)

    flush()

    # Padding a short cue up to min_duration must never push it into the next cue.
    for a, b in zip(cues, cues[1:]):
        if a.end > b.start:
            a.end = max(min(a.end, b.start), a.start + 0.05)

    return cues


def words_to_sentences(words: list[Word]) -> list[str]:
    """Group words into sentences (used for the readable transcript layout)."""
    sentences: list[str] = []
    current: list[str] = []
    for w in words:
        current.append(w.text)
        if SENTENCE_END.search(w.text):
            sentences.append(_join_words(current))
            current = []
    if current:
        sentences.append(_join_words(current))
    return sentences


def srt_timestamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def vtt_timestamp(seconds: float) -> str:
    return srt_timestamp(seconds).replace(",", ".")


def _vtt_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_srt(cues: Iterable[Cue], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for i, cue in enumerate(cues, 1):
            f.write(f"{i}\n{srt_timestamp(cue.start)} --> {srt_timestamp(cue.end)}\n{cue.text}\n\n")


def write_vtt(cues: Iterable[Cue], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for cue in cues:
            f.write(f"{vtt_timestamp(cue.start)} --> {vtt_timestamp(cue.end)}\n{_vtt_escape(cue.text)}\n\n")


def write_txt(cues: Iterable[Cue], path: Path) -> None:
    """One subtitle cue per line."""
    with path.open("w", encoding="utf-8") as f:
        for cue in cues:
            f.write(cue.text.replace("\n", " ") + "\n")


def write_txt_sentences(words: list[Word], path: Path) -> None:
    """One sentence per line, independent of subtitle cue boundaries."""
    with path.open("w", encoding="utf-8") as f:
        for sentence in words_to_sentences(words):
            f.write(sentence + "\n")


def write_words_json(words: list[Word], path: Path) -> None:
    path.write_text(json.dumps([asdict(w) for w in words], ensure_ascii=False, indent=2), encoding="utf-8")


def transcribe(
    input_path: Path,
    model_size: str = "large-v3",
    language: Optional[str] = None,
    device: str = "cpu",
    compute_type: Optional[str] = None,
    beam_size: int = 5,
    vad: bool = True,
    hotwords: Optional[str] = None,
    progress: Optional[Callable[[float, Optional[float]], None]] = None,
) -> tuple[list[Word], str, float]:
    """Transcribe `input_path`. `progress(seconds_done, total_seconds)` is called after each segment."""
    if compute_type is None:
        compute_type = "float16" if device == "cuda" else "int8"

    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        str(input_path),
        language=language,
        beam_size=beam_size,
        vad_filter=vad,
        word_timestamps=True,
        hotwords=hotwords,
    )
    total = getattr(info, "duration", None)

    words: list[Word] = []
    for segment in segments:
        if segment.words:
            for w in segment.words:
                token = _clean_token(w.word)
                if token:
                    words.append(Word(float(w.start), float(w.end), token, getattr(w, "probability", None)))
        elif segment.text.strip():
            # Defensive fallback if a backend returns no word objects.
            words.append(Word(float(segment.start), float(segment.end), segment.text.strip(), None))
        if progress is not None:
            progress(float(segment.end), total)

    return words, info.language, float(info.language_probability)


# --------------------------------------------------------------------------------------
# FFmpeg helpers
# --------------------------------------------------------------------------------------

def check_ffmpeg_tools() -> None:
    """Raise RuntimeError with a clear message if ffmpeg or ffprobe is unavailable."""
    missing = [tool for tool in ("ffmpeg", "ffprobe") if not shutil.which(tool)]
    if missing:
        raise RuntimeError(
            f"{' and '.join(missing)} not found in PATH. Install FFmpeg (with libass support) to use --burn."
        )


def probe_media(path: Path) -> MediaInfo:
    """Inspect a media file with ffprobe. Display dimensions account for rotation metadata."""
    check_ffmpeg_tools()
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe could not read {path}: {result.stderr.strip()[-300:]}")

    streams = json.loads(result.stdout or "{}").get("streams", [])
    video = next(
        (s for s in streams
         if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")),
        None,
    )
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = height = None
    if video:
        width, height = video.get("width"), video.get("height")
        rotation = video.get("tags", {}).get("rotate")
        for side in video.get("side_data_list", []) or []:
            if "rotation" in side:
                rotation = side["rotation"]
        try:
            if rotation is not None and abs(int(float(rotation))) % 180 == 90:
                width, height = height, width
        except (TypeError, ValueError):
            pass

    return MediaInfo(
        has_video=video is not None,
        width=width,
        height=height,
        audio_codec=audio.get("codec_name") if audio else None,
    )


# An apostrophe cannot be escaped inside single quotes: close the quote, emit an escaped apostrophe,
# and reopen it (two escaping levels apply, hence the triple backslash).
_APOSTROPHE_ESCAPE = r"'\\\''"


def _ffmpeg_escape_filter_path(path: Path) -> str:
    """Escape a path for use inside single quotes in an FFmpeg filter argument."""
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", r"\:").replace(",", r"\,")
    value = value.replace("'", _APOSTROPHE_ESCAPE)
    return value


def compute_font_size(font_size: int, width: Optional[int], height: Optional[int], auto_scale: bool = True) -> int:
    """libass scales font size against video height. For portrait and square video that makes text
    far too wide, so scale it to what a 16:9 frame of the same width would use."""
    if not auto_scale or not width or not height:
        return font_size
    factor = min(1.0, (width * 9 / 16) / height)
    return max(8, round(font_size * factor))


def build_force_style(
    width: Optional[int],
    height: Optional[int],
    font_name: Optional[str] = None,
    font_size: int = 24,
    margin_v: Optional[int] = None,
    auto_scale: bool = True,
) -> str:
    if font_name and "," in font_name:
        raise ValueError("Font names containing a comma are not supported for burn-in.")
    parts = []
    if font_name:
        parts.append(f"FontName={font_name}")
    parts.append(f"FontSize={compute_font_size(font_size, width, height, auto_scale)}")
    if margin_v is None and width and height and height > width:
        margin_v = 35  # keep text clear of platform UI along the bottom of vertical video
    if margin_v is not None:
        parts.append(f"MarginV={margin_v}")
    return ",".join(parts)


def build_burn_command(
    input_video: Path,
    subtitle_path: Path,
    output_video: Path,
    info: MediaInfo,
    font_name: Optional[str] = None,
    font_size: int = 24,
    margin_v: Optional[int] = None,
    auto_scale: bool = True,
) -> list[str]:
    style = build_force_style(info.width, info.height, font_name, font_size, margin_v, auto_scale)
    style = style.replace("'", _APOSTROPHE_ESCAPE)
    subtitle_filter = f"subtitles='{_ffmpeg_escape_filter_path(subtitle_path)}':force_style='{style}'"

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
        "-i", str(input_video),
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
    ]
    if info.audio_codec:
        if info.audio_codec in MP4_COPY_SAFE_AUDIO:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(output_video)]
    return cmd


def burn_subtitles(
    input_video: Path,
    subtitle_path: Path,
    output_video: Path,
    font_name: Optional[str] = None,
    font_size: int = 24,
    margin_v: Optional[int] = None,
    auto_scale: bool = True,
    info: Optional[MediaInfo] = None,
) -> None:
    check_ffmpeg_tools()
    info = info or probe_media(input_video)
    if not info.has_video:
        raise RuntimeError("--burn needs a video input; this file has no video stream.")
    if input_video.resolve() == output_video.resolve():
        raise RuntimeError("The burned output must not be the same file as the input.")

    cmd = build_burn_command(input_video, subtitle_path, output_video, info,
                             font_name, font_size, margin_v, auto_scale)
    subprocess.run(cmd, check=True)
