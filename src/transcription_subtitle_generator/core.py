from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional



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
    left = ""
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

    max_chars_total = max_chars_per_line * max_lines
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

        candidate = current + [word]
        candidate_text = _join_words([w.text for w in candidate])
        duration = word.end - current[0].start
        gap = word.start - current[-1].end
        previous_text = _join_words([w.text for w in current])
        sentence_break = bool(re.search(r"[.!?][\"'”’)]?$", previous_text))

        should_split = (
            len(candidate_text) > max_chars_total
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
    return cues


def srt_timestamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def vtt_timestamp(seconds: float) -> str:
    return srt_timestamp(seconds).replace(",", ".")


def write_srt(cues: Iterable[Cue], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for i, cue in enumerate(cues, 1):
            f.write(f"{i}\n{srt_timestamp(cue.start)} --> {srt_timestamp(cue.end)}\n{cue.text}\n\n")


def write_vtt(cues: Iterable[Cue], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for cue in cues:
            f.write(f"{vtt_timestamp(cue.start)} --> {vtt_timestamp(cue.end)}\n{cue.text}\n\n")


def write_txt(cues: Iterable[Cue], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for cue in cues:
            f.write(cue.text.replace("\n", " ") + "\n")


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
) -> tuple[list[Word], str, float]:
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

    return words, info.language, float(info.language_probability)


def _ffmpeg_escape_filter_path(path: Path) -> str:
    # FFmpeg filter syntax needs escaping for backslashes, colons, apostrophes and commas.
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")
    return value


def burn_subtitles(
    input_video: Path,
    subtitle_path: Path,
    output_video: Path,
    font_name: Optional[str] = None,
    font_size: int = 24,
) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg was not found in PATH. Install FFmpeg with libass support first.")

    subtitle_filter = f"subtitles='{_ffmpeg_escape_filter_path(subtitle_path)}'"
    if font_name:
        safe_font = font_name.replace("'", r"\'")
        subtitle_filter += f":force_style='FontName={safe_font},FontSize={font_size}'"
    elif font_size:
        subtitle_filter += f":force_style='FontSize={font_size}'"

    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy", str(output_video),
    ]
    subprocess.run(cmd, check=True)
