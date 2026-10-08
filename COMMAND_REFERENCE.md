# Command Reference

## Transcription and Subtitle Generator

Primary command:

```bash
transcribe-subtitles [OPTIONS] INPUT
```

Compatibility alias:

```bash
video-subtitles [OPTIONS] INPUT
```

`INPUT` can be a supported audio or video file. Media decoding is handled by the underlying faster-whisper / FFmpeg stack.

## Quick examples

Basic automatic language detection:

```bash
transcribe-subtitles "video.mp4"
```

Malayalam:

```bash
transcribe-subtitles "video.mp4" --language ml
```

English:

```bash
transcribe-subtitles "video.mp4" --language en
```

Use a smaller model for faster CPU transcription:

```bash
transcribe-subtitles "video.mp4" --model small --device cpu
```

Use NVIDIA CUDA:

```bash
transcribe-subtitles "video.mp4" --model large-v3 --device cuda
```

Create subtitles and burn them into a new video:

```bash
transcribe-subtitles "video.mp4" --burn
```

## Generated files

For an input named `video.mp4`, the default output is:

```text
video.srt
video.vtt
video.txt
video.words.json
```

When `--burn` is used:

```text
video.subtitled.mp4
```

## Positional argument

### `INPUT`

Input audio or video file.

Examples:

```bash
transcribe-subtitles "sermon.mp4"
transcribe-subtitles "interview.wav"
transcribe-subtitles "recording.mp3"
```

Paths containing spaces should be enclosed in quotes.

## General options

### `-h`, `--help`

Display command help and exit.

```bash
transcribe-subtitles --help
```

### `--version`

Display the installed package version and exit.

```bash
transcribe-subtitles --version
```

### `-o OUTPUT_DIR`, `--output-dir OUTPUT_DIR`

Directory in which generated files will be stored.

Default: the same directory as the input file.

```bash
transcribe-subtitles "video.mp4" --output-dir "output"
```

Short form:

```bash
transcribe-subtitles "video.mp4" -o "output"
```

## Whisper model options

### `-m MODEL`, `--model MODEL`

Whisper model to use.

Default:

```text
large-v3
```

Common choices:

| Model | Relative speed | Relative accuracy | Typical use |
|---|---:|---:|---|
| `tiny` | Very fast | Low | Rough drafts |
| `base` | Fast | Moderate | Lightweight transcription |
| `small` | Fast | Good | CPU-friendly use |
| `medium` | Medium | Very good | Better CPU accuracy |
| `large-v3` | Slowest | Best general choice | Multilingual and final subtitles |

Example:

```bash
transcribe-subtitles "video.mp4" --model medium
```

### `-l LANGUAGE`, `--language LANGUAGE`

Force the spoken language instead of automatic language detection.

Default: automatic detection.

Examples:

```bash
transcribe-subtitles "english.mp4" --language en
transcribe-subtitles "malayalam.mp4" --language ml
transcribe-subtitles "hindi.mp4" --language hi
transcribe-subtitles "tamil.mp4" --language ta
transcribe-subtitles "bangla.mp4" --language bn
transcribe-subtitles "nepali.mp4" --language ne
```

When you know the language, specifying it can improve consistency and avoid incorrect auto-detection on short recordings.

### `--device {cpu,cuda}`

Processing device.

Default:

```text
cpu
```

CPU example:

```bash
transcribe-subtitles "video.mp4" --device cpu
```

NVIDIA CUDA example:

```bash
transcribe-subtitles "video.mp4" --device cuda
```

### `--compute-type COMPUTE_TYPE`

Override the CTranslate2 compute type.

Automatic defaults:

- CPU: `int8`
- CUDA: `float16`

Examples:

```bash
transcribe-subtitles "video.mp4" --device cpu --compute-type int8
transcribe-subtitles "video.mp4" --device cuda --compute-type float16
```

Only change this when you know what your hardware and CTranslate2 installation support.

### `--beam-size BEAM_SIZE`

Beam search size used during transcription.

Default:

```text
5
```

Example:

```bash
transcribe-subtitles "video.mp4" --beam-size 5
```

A larger value can increase processing time. It does not guarantee better output for every recording.

### `--no-vad`

Disable Silero voice activity detection.

VAD is enabled by default and helps skip silence or non-speech regions.

```bash
transcribe-subtitles "video.mp4" --no-vad
```

This can be useful if VAD is incorrectly removing very quiet speech.

### `--hotwords HOTWORDS`

Provide important words or phrases as recognition hints.

Useful for:

- people's names
- organization names
- ministry terminology
- Scripture names and terms
- product names
- technical vocabulary

Example:

```bash
transcribe-subtitles "session.mp4" --hotwords "Faith Comes By Hearing, Bible.is, Scripture Engagement"
```

Malayalam example:

```bash
transcribe-subtitles "message.mp4" --language ml --hotwords "യേശുക്രിസ്തു, ബൈബിൾ"
```

Hotwords are hints, not guaranteed replacements. Always review names and specialized terminology in the final transcript.

## Subtitle formatting options

### `--max-chars MAX_CHARS`

Maximum target characters per subtitle line.

Default:

```text
42
```

Example:

```bash
transcribe-subtitles "video.mp4" --max-chars 38
```

Lower values produce shorter lines and usually more subtitle cues.

### `--max-lines {1,2}`

Maximum number of readable lines per subtitle cue.

Default:

```text
2
```

Two lines:

```bash
transcribe-subtitles "video.mp4" --max-lines 2
```

One line:

```bash
transcribe-subtitles "video.mp4" --max-lines 1
```

### `--max-duration MAX_DURATION`

Maximum subtitle cue duration in seconds.

Default:

```text
6.0
```

Example:

```bash
transcribe-subtitles "video.mp4" --max-duration 5
```

### `--max-gap MAX_GAP`

Start a new subtitle cue when the silence between words exceeds this value in seconds.

Default:

```text
0.8
```

Example:

```bash
transcribe-subtitles "video.mp4" --max-gap 0.7
```

## Word-level timestamps

### `--no-words-json`

By default, the tool creates a `.words.json` file containing word-level timing and confidence information.

Disable it with:

```bash
transcribe-subtitles "video.mp4" --no-words-json
```

Example JSON entry:

```json
{
  "start": 1.42,
  "end": 1.78,
  "text": "Welcome",
  "probability": 0.98
}
```

## Subtitle burn-in options

Subtitle burning requires FFmpeg with the `subtitles` filter and libass.

### `--burn`

Burn the generated SRT subtitles into the source video.

```bash
transcribe-subtitles "video.mp4" --burn
```

Default output:

```text
video.subtitled.mp4
```

### `--burn-output BURN_OUTPUT`

Specify the output filename for the burned video.

```bash
transcribe-subtitles "video.mp4" --burn --burn-output "final-video.mp4"
```

### `--font FONT`

Font family used by FFmpeg/libass when burning subtitles.

Example:

```bash
transcribe-subtitles "video.mp4" --burn --font "Arial"
```

Malayalam example:

```bash
transcribe-subtitles "video.mp4" --language ml --burn --font "Anek Malayalam"
```

The font must already be installed on the system and visible to FFmpeg/libass.

### `--font-size FONT_SIZE`

Subtitle font size used during burn-in.

Default:

```text
24
```

Example:

```bash
transcribe-subtitles "video.mp4" --burn --font-size 28
```

Font and font size together:

```bash
transcribe-subtitles "video.mp4" --burn --font "Anek Malayalam" --font-size 28
```

## Recommended presets

### High-quality multilingual transcription

```bash
transcribe-subtitles "video.mp4" --model large-v3 --max-chars 42 --max-lines 2 --max-duration 6 --max-gap 0.8
```

### Malayalam final subtitles

```bash
transcribe-subtitles "video.mp4" --language ml --model large-v3 --max-chars 38 --max-lines 2 --max-duration 5 --max-gap 0.7
```

### Fast CPU draft

```bash
transcribe-subtitles "video.mp4" --model small --device cpu --compute-type int8
```

### NVIDIA GPU

```bash
transcribe-subtitles "video.mp4" --model large-v3 --device cuda --compute-type float16
```

### Presentation-style shorter subtitles

```bash
transcribe-subtitles "video.mp4" --max-chars 36 --max-lines 2 --max-duration 4.5 --max-gap 0.6
```

### One-line captions

```bash
transcribe-subtitles "video.mp4" --max-chars 45 --max-lines 1 --max-duration 4
```

### Malayalam subtitles burned into video

```bash
transcribe-subtitles "video.mp4" --language ml --model large-v3 --burn --font "Anek Malayalam" --font-size 28
```

## Windows examples

PowerShell:

```powershell
transcribe-subtitles "C:\Videos\message.mp4" --language ml
```

Custom output folder:

```powershell
transcribe-subtitles "C:\Videos\message.mp4" -o "C:\Videos\Subtitles"
```

A path containing spaces:

```powershell
transcribe-subtitles "D:\Conference Videos\Session 01.mp4" --language en
```

## Checking FFmpeg

Confirm FFmpeg is available:

```bash
ffmpeg -version
```

Windows - confirm subtitle filter support:

```powershell
ffmpeg -filters | findstr subtitles
```

Linux or macOS:

```bash
ffmpeg -filters | grep subtitles
```

You should see a `subtitles` video filter if libass support is present.

## Troubleshooting

### `transcribe-subtitles` is not recognized

Make sure the virtual environment is active and reinstall the project:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Then test:

```powershell
transcribe-subtitles --help
```

You can also invoke the module directly from the project directory:

```powershell
python -m transcription_subtitle_generator.cli --help
```

### FFmpeg is not found

Run:

```bash
ffmpeg -version
```

If the command is not recognized, install FFmpeg and add its `bin` directory to the operating system `PATH`.

### `No such filter: subtitles`

Your FFmpeg build does not include the libass subtitle filter. Install an FFmpeg build compiled with libass support.

### Malayalam characters display incorrectly when burned

Check all of the following:

1. The subtitle file is UTF-8 encoded.
2. A Malayalam-capable font such as Anek Malayalam is installed.
3. FFmpeg includes libass.
4. HarfBuzz/font shaping support is available in the FFmpeg/libass environment.

Example:

```bash
transcribe-subtitles "video.mp4" --language ml --burn --font "Anek Malayalam" --font-size 28
```

### Audio works but burn-in fails

Transcription can accept audio files, but `--burn` is intended for video input because it creates a subtitled video output.

### MP4 audio-copy error during burn-in

The current burn command copies the source audio with:

```text
-c:a copy
```

Some source audio codecs cannot be copied directly into an MP4 container. In that case, edit `core.py` and replace the audio-copy arguments with an AAC encode such as:

```text
-c:a aac -b:a 192k
```

### CUDA errors

Confirm that your NVIDIA driver, CUDA-related runtime libraries, CTranslate2, and faster-whisper installation are compatible. As a fallback, run on CPU:

```bash
transcribe-subtitles "video.mp4" --device cpu --compute-type int8
```

## Current defaults summary

| Option | Default |
|---|---|
| Model | `large-v3` |
| Language | Auto-detect |
| Device | `cpu` |
| CPU compute type | `int8` |
| CUDA compute type | `float16` |
| Beam size | `5` |
| VAD | Enabled |
| Max characters per line | `42` |
| Max lines | `2` |
| Max cue duration | `6.0` seconds |
| Max silence gap | `0.8` seconds |
| Word JSON | Enabled |
| Burn subtitles | Disabled |
| Burn font size | `24` |
