from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import burn_subtitles, transcribe, words_to_cues, write_srt, write_txt, write_vtt, write_words_json
from . import __version__


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
    p.add_argument("--beam-size", type=int, default=5)
    p.add_argument("--no-vad", action="store_true", help="Disable Silero VAD")
    p.add_argument("--hotwords", help="Hint words/phrases such as names or technical terms")
    p.add_argument("--max-chars", type=int, default=42, help="Maximum characters per subtitle line")
    p.add_argument("--max-lines", type=int, choices=[1, 2], default=2)
    p.add_argument("--max-duration", type=float, default=6.0, help="Maximum cue duration in seconds")
    p.add_argument("--max-gap", type=float, default=0.8, help="Split after silence longer than this")
    p.add_argument("--no-words-json", action="store_true", help="Do not create word-level timestamp JSON")
    p.add_argument("--burn", action="store_true", help="Burn generated SRT into a video using FFmpeg/libass")
    p.add_argument("--burn-output", type=Path, help="Burned video output path")
    p.add_argument("--font", help="Subtitle font name for burning, e.g. 'Anek Malayalam'")
    p.add_argument("--font-size", type=int, default=24)
    return p


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 2

    out_dir = (args.output_dir.expanduser().resolve() if args.output_dir else input_path.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    print(f"Input: {input_path}")
    print(f"Model: {args.model} | device: {args.device}")
    words, detected_language, probability = transcribe(
        input_path=input_path,
        model_size=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        vad=not args.no_vad,
        hotwords=args.hotwords,
    )
    print(f"Detected language: {detected_language} ({probability:.1%})")
    print(f"Word timestamps: {len(words)}")

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
        burn_subtitles(input_path, srt, burn_output, font_name=args.font, font_size=args.font_size)
        print(f"Created: {burn_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
