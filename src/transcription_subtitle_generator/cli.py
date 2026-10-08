from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .core import (
    burn_subtitles,
    check_ffmpeg_tools,
    probe_media,
    transcribe,
    words_to_cues,
    write_srt,
    write_txt,
    write_txt_sentences,
    write_vtt,
    write_words_json,
)

EXIT_OK = 0
EXIT_BURN_FAILED = 1
EXIT_BAD_INPUT = 2
EXIT_NO_SPEECH = 3


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be 1 or greater")
    return n


def _positive_float(value: str) -> float:
    x = float(value)
    if x <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return x


def _non_negative_float(value: str) -> float:
    x = float(value)
    if x < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return x


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="transcribe-subtitles",
        description="Transcribe audio/video and generate SRT, VTT, TXT and word-level timestamps with faster-whisper.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("input", type=Path, help="Input audio or video file")
    p.add_argument("-o", "--output-dir", type=Path, help="Output directory (default: next to input)")
    p.add_argument("-m", "--model", default="large-v3", help="Whisper model (default: large-v3)")
    p.add_argument("-l", "--language", help="Language code, e.g. en, ml, hi, ta. Default: auto-detect")
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--compute-type", help="CTranslate2 compute type, e.g. int8, float16")
    p.add_argument("--beam-size", type=_positive_int, default=5)
    p.add_argument("--no-vad", action="store_true", help="Disable Silero VAD")
    p.add_argument("--hotwords", help="Hint words/phrases such as names or technical terms")
    p.add_argument("--max-chars", type=_positive_int, default=42, help="Maximum characters per subtitle line")
    p.add_argument("--max-lines", type=int, choices=[1, 2], default=2)
    p.add_argument("--max-duration", type=_positive_float, default=6.0, help="Maximum cue duration in seconds")
    p.add_argument("--max-gap", type=_non_negative_float, default=0.8, help="Split after silence longer than this")
    p.add_argument("--txt-layout", choices=["cues", "sentences"], default="cues",
                   help="Plain-text transcript layout: one subtitle cue per line (default) or one sentence per line")
    p.add_argument("--no-words-json", action="store_true", help="Do not create word-level timestamp JSON")
    p.add_argument("--burn", action="store_true", help="Burn generated SRT into a video using FFmpeg/libass")
    p.add_argument("--burn-output", type=Path, help="Burned video output path")
    p.add_argument("--font", help="Subtitle font name for burning, e.g. 'Anek Malayalam'")
    p.add_argument("--font-size", type=_positive_int, default=24,
                   help="Subtitle font size for burning, as for a 16:9 frame (default: 24)")
    p.add_argument("--margin-v", type=_positive_int,
                   help="Bottom margin for burned subtitles (default: automatic; larger for vertical video)")
    p.add_argument("--no-auto-scale", action="store_true",
                   help="Do not scale the burned font size for portrait or square video")
    return p


def _make_progress():
    last = {"pct": -1}

    def progress(done: float, total: Optional[float]) -> None:
        if not total:
            return
        pct = min(100, int(done / total * 100))
        if pct != last["pct"]:
            last["pct"] = pct
            print(f"\r  Transcribing: {pct:3d}%", end="", file=sys.stderr, flush=True)

    def finish() -> None:
        if last["pct"] >= 0:
            print(file=sys.stderr)

    return progress, finish


def main(argv: Optional[list[str]] = None) -> int:
    # Paths and text may contain non-Latin scripts; never crash on a non-UTF-8 console or redirect.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return EXIT_BAD_INPUT

    media_info = None
    if args.burn:
        # Fail before the (potentially long) transcription, not after it.
        try:
            check_ffmpeg_tools()
            media_info = probe_media(input_path)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_BAD_INPUT
        if not media_info.has_video:
            print("Error: --burn needs a video input; this file has no video stream.", file=sys.stderr)
            return EXIT_BAD_INPUT

    out_dir = args.output_dir.expanduser().resolve() if args.output_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    print(f"Input: {input_path}")
    print(f"Model: {args.model} | device: {args.device}")
    progress, finish_progress = _make_progress()
    words, detected_language, probability = transcribe(
        input_path=input_path,
        model_size=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        vad=not args.no_vad,
        hotwords=args.hotwords,
        progress=progress,
    )
    finish_progress()
    print(f"Detected language: {detected_language} ({probability:.1%})")
    print(f"Word timestamps: {len(words)}")

    if not words:
        print(
            "Warning: no speech was detected, so no files were written. "
            "If the audio does contain speech, try --no-vad or a larger model.",
            file=sys.stderr,
        )
        return EXIT_NO_SPEECH

    cues = words_to_cues(
        words,
        max_chars_per_line=args.max_chars,
        max_lines=args.max_lines,
        max_duration=args.max_duration,
        max_gap=args.max_gap,
    )

    srt = out_dir / f"{stem}.srt"
    vtt = out_dir / f"{stem}.vtt"
    txt = out_dir / f"{stem}.txt"
    write_srt(cues, srt)
    write_vtt(cues, vtt)
    if args.txt_layout == "sentences":
        write_txt_sentences(words, txt)
    else:
        write_txt(cues, txt)
    print(f"Created: {srt}")
    print(f"Created: {vtt}")
    print(f"Created: {txt}")

    if not args.no_words_json:
        words_json = out_dir / f"{stem}.words.json"
        write_words_json(words, words_json)
        print(f"Created: {words_json}")

    if args.burn:
        burn_output = args.burn_output or (out_dir / f"{stem}.subtitled.mp4")
        print(f"Burning subtitles to: {burn_output}")
        try:
            burn_subtitles(
                input_path, srt, burn_output,
                font_name=args.font, font_size=args.font_size,
                margin_v=args.margin_v, auto_scale=not args.no_auto_scale,
                info=media_info,
            )
        except (RuntimeError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_BURN_FAILED
        except subprocess.CalledProcessError as exc:
            print(f"Error: FFmpeg failed (exit status {exc.returncode}). "
                  f"The subtitle files above were still created.", file=sys.stderr)
            return EXIT_BURN_FAILED
        print(f"Created: {burn_output}")

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
