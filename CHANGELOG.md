# Changelog

## 1.2.0

### Fixed
- Burn-in on vertical and square video produced oversized text running edge to edge. Font size is now scaled
  to the frame (rotation metadata respected) and the text is lifted off the bottom edge on portrait video.
- Burn-in failed for file paths containing an apostrophe (for example `John's Videos`).
- Sentence endings written with the Devanagari/Bengali danda (`।`, `॥`), Urdu full stop, Arabic question mark
  or ellipsis are now recognised when splitting cues.
- A short cue padded to its minimum duration could overlap the next cue.
- The line limit was checked against total length rather than the wrapped result, so lines could exceed `--max-chars`.
- An empty transcript no longer produces empty files and a traceback; the tool exits with status 3.
- Non-ASCII file names no longer crash the CLI when stdout is not UTF-8 (for example redirected on Windows).
- `&`, `<` and `>` are escaped in WebVTT output.

### Added
- Early checks for `--burn` (FFmpeg/ffprobe present, video stream present) before transcription starts.
- Progress display during transcription.
- `--txt-layout sentences`, `--margin-v`, `--no-auto-scale`.
- Validation of numeric options; documented exit status codes.
- Burn-in re-encodes non-MP4-compatible audio to AAC automatically; output is `yuv420p` with `+faststart`.
- Quieter FFmpeg output, and a clean error message when FFmpeg fails.
- Unit and integration tests (including real FFmpeg burn-in and the CLI with a stubbed model).

### Changed
- Packaging: SPDX `license = "MIT"` with `license-files` (requires setuptools 77+), real author name, `dev` extra with pytest.
- README: FFmpeg is required only for `--burn`.
