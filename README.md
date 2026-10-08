# Transcription and Subtitle Generator

A local Python command-line tool that transcribes audio or video and generates readable subtitle and transcript files using **faster-whisper**.

## Features

- Accepts common audio and video formats
- Generates `.srt`, `.vtt`, and plain `.txt`
- Exports word-level timestamps to `.words.json`
- Automatic language detection or explicit language selection
- Silero VAD to reduce transcription of silence
- Intelligent subtitle cue splitting based on line length, cue duration, silence, and sentence endings
- Keeps subtitle cues to 1 or 2 readable lines
- Optional FFmpeg/libass subtitle burn-in to MP4, with automatic font scaling for vertical (9:16) and square video
- Sentence-aware splitting that understands the Devanagari/Bengali danda (`।`) and other non-Latin sentence endings
- Progress display during transcription, and early, clear errors (no speech, missing FFmpeg, audio-only input with `--burn`)
- CPU and NVIDIA CUDA modes
- Supports `hotwords` for names, Scripture terminology, organization names, and specialist vocabulary
- Primary CLI command: `transcribe-subtitles`
- Compatibility alias: `video-subtitles`

The tool uses faster-whisper word-level timestamps to build subtitle cues instead of relying only on Whisper's original segment boundaries.

## Requirements

- Python 3.10+
- FFmpeg and ffprobe in `PATH` **only for `--burn`** (transcription decodes media through the PyAV library installed with faster-whisper)
- For burn-in, FFmpeg must include the `subtitles` filter and libass
- NVIDIA CUDA libraries are required only when using `--device cuda`

Check FFmpeg:

```bash
ffmpeg -version
```

Check subtitle filter support on Windows:

```powershell
ffmpeg -filters | findstr subtitles
```

On Linux or macOS:

```bash
ffmpeg -filters | grep subtitles
```

## Installation

### Windows

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

## Basic usage

```bash
transcribe-subtitles "video.mp4"
```

For an audio file:

```bash
transcribe-subtitles "recording.mp3"
```

By default, output files are created next to the source file:

```text
video.srt
video.vtt
video.txt
video.words.json
```

## Malayalam example

```bash
transcribe-subtitles "message.mp4" --language ml --model large-v3
```

For names or specialized vocabulary:

```bash
transcribe-subtitles "message.mp4" --language ml --hotwords "Faith Comes By Hearing, Bible.is, യേശുക്രിസ്തു"
```

## English example

```bash
transcribe-subtitles "session.mp4" --language en
```

## Faster CPU mode

```bash
transcribe-subtitles "video.mp4" --model small --device cpu
```

CPU defaults to `int8` compute.

## NVIDIA GPU

```bash
transcribe-subtitles "video.mp4" --model large-v3 --device cuda
```

CUDA defaults to `float16` compute.

## Control subtitle readability

Default formatting uses approximately 42 characters per line, up to 2 lines, a maximum cue duration of 6 seconds, and a silence split threshold of 0.8 seconds.

```bash
transcribe-subtitles "video.mp4" --max-chars 38 --max-lines 2 --max-duration 5 --max-gap 0.7
```

One-line subtitles:

```bash
transcribe-subtitles "video.mp4" --max-lines 1 --max-chars 45
```

## Burn subtitles into video

```bash
transcribe-subtitles "video.mp4" --burn
```

This creates:

```text
video.subtitled.mp4
```

Choose a font:

```bash
transcribe-subtitles "malayalam.mp4" --language ml --burn --font "Anek Malayalam" --font-size 28
```

The selected font must be installed on the computer and visible to FFmpeg/libass.

## Vertical video (Reels, Shorts, Status)

libass sizes subtitle text against the video height, which makes text far too large on portrait video. Burn-in therefore scales the font automatically for portrait and square frames, and lifts the text off the bottom edge so platform interface elements are less likely to cover it. Rotation metadata (common on phone clips) is taken into account.

```bash
transcribe-subtitles "reel.mp4" --burn
```

Fine-tune with `--font-size` (specified as for a 16:9 frame) and `--margin-v`, or disable the automatic scaling with `--no-auto-scale`.

## Transcript layout

By default the `.txt` file has one subtitle cue per line. For a readable transcript with one sentence per line, independent of subtitle breaks:

```bash
transcribe-subtitles "message.mp4" --txt-layout sentences
```

## Custom output directory

```bash
transcribe-subtitles "video.mp4" -o "output"
```

## Word-level timestamps

`video.words.json` contains entries such as:

```json
[
  {
    "start": 1.42,
    "end": 1.78,
    "text": "Welcome",
    "probability": 0.98
  }
]
```

Disable the JSON file:

```bash
transcribe-subtitles "video.mp4" --no-words-json
```

## Model suggestions

| Model | Speed | Accuracy | Suggested use |
|---|---:|---:|---|
| `small` | Fast | Good | Drafts and lower-spec CPU systems |
| `medium` | Medium | Very good | Better CPU quality |
| `large-v3` | Slower | Best general choice | Multilingual and final subtitles |

The first use of a model normally downloads the model files.

## Full command reference

See **[COMMAND_REFERENCE.md](COMMAND_REFERENCE.md)** for every CLI option, default value, recommended presets, subtitle-burning examples, and troubleshooting commands.

You can also view built-in help:

```bash
transcribe-subtitles --help
```

Check the installed version:

```bash
transcribe-subtitles --version
```

The older command remains available as an alias:

```bash
video-subtitles "video.mp4"
```

## Notes on subtitle burning

The project uses FFmpeg's `subtitles` video filter and encodes the output video as H.264 (`yuv420p`, `+faststart`, suitable for web and social upload). The source audio is copied when it is MP4-compatible (AAC, MP3, Opus, FLAC and similar) and otherwise re-encoded to AAC 192 kb/s automatically.

## License

MIT
