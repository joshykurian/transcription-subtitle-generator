"""Integration tests: real FFmpeg for burn-in, and the CLI with a stubbed Whisper model."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

from transcription_subtitle_generator import cli
from transcription_subtitle_generator.core import (
    build_burn_command,
    build_force_style,
    burn_subtitles,
    MediaInfo,
    probe_media,
)

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
SRT = "1\n00:00:00,200 --> 00:00:01,800\nHello subtitle\n\n"


def make_video(path: Path, size="320x180", audio="aac", seconds=1):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x303030:s={size}:d={seconds}:r=25"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", audio]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(path)]
    subprocess.run(cmd, check=True)


class CommandBuildingTests(unittest.TestCase):
    """No FFmpeg needed."""

    def test_style_landscape_has_no_margin_override(self):
        self.assertEqual(build_force_style(1920, 1080, font_size=24), "FontSize=24")

    def test_style_portrait_scales_and_lifts(self):
        style = build_force_style(1080, 1920, font_name="Anek Malayalam", font_size=24)
        self.assertIn("FontName=Anek Malayalam", style)
        self.assertIn("MarginV=35", style)
        size = int(style.split("FontSize=")[1].split(",")[0])
        self.assertLess(size, 12)

    def test_comma_in_font_name_rejected(self):
        with self.assertRaises(ValueError):
            build_force_style(1920, 1080, font_name="A,B")

    def test_audio_copy_only_when_safe(self):
        args = (Path("in.mp4"), Path("s.srt"), Path("out.mp4"))
        safe = build_burn_command(*args, MediaInfo(True, 1920, 1080, "aac"))
        unsafe = build_burn_command(*args, MediaInfo(True, 1920, 1080, "wmav2"))
        none = build_burn_command(*args, MediaInfo(True, 1920, 1080, None))
        self.assertEqual(safe[safe.index("-c:a") + 1], "copy")
        self.assertEqual(unsafe[unsafe.index("-c:a") + 1], "aac")
        self.assertNotIn("-c:a", none)
        for cmd in (safe, unsafe, none):
            self.assertIn("yuv420p", cmd)
            self.assertIn("+faststart", cmd)


@unittest.skipUnless(HAVE_FFMPEG, "FFmpeg/ffprobe not installed")
class BurnTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _burn(self, subdir, src="in.mp4", **kw):
        d = self.tmp / subdir
        d.mkdir(parents=True, exist_ok=True)
        srt = d / "in.srt"
        srt.write_text(SRT, encoding="utf-8")
        out = self.tmp / f"out_{abs(hash(subdir)) % 10**6}.mp4"
        burn_subtitles(self.tmp / src, srt, out, **kw)
        return out

    def test_probe_dimensions_and_audio(self):
        make_video(self.tmp / "in.mp4", size="320x180")
        info = probe_media(self.tmp / "in.mp4")
        self.assertTrue(info.has_video)
        self.assertEqual((info.width, info.height, info.audio_codec), (320, 180, "aac"))

    def test_probe_audio_only(self):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1",
                        str(self.tmp / "a.mp3")], check=True)
        self.assertFalse(probe_media(self.tmp / "a.mp3").has_video)

    def test_awkward_paths(self):
        make_video(self.tmp / "in.mp4")
        for name in ["plain", "My Videos", "John's Videos", "God's Word, Part 1",
                     "x [v2]; a=b", "a:b", "100% Gospel", "സന്ദേശം"]:
            with self.subTest(folder=name):
                self.assertTrue(self._burn(name).stat().st_size > 0)

    def test_font_name_with_apostrophe_does_not_break_parsing(self):
        make_video(self.tmp / "in.mp4")
        self.assertTrue(self._burn("p", font_name="O'Brien Sans").exists())

    def test_non_mp4_audio_is_reencoded(self):
        try:
            make_video(self.tmp / "in.mkv", audio="wmav2")
        except subprocess.CalledProcessError:
            self.skipTest("wmav2 encoder not available")
        self.assertTrue(self._burn("w", src="in.mkv").exists())

    def test_video_without_audio(self):
        make_video(self.tmp / "in.mp4", audio=None)
        self.assertTrue(self._burn("n").exists())

    def test_portrait_burn_runs(self):
        make_video(self.tmp / "in.mp4", size="360x640")
        self.assertTrue(self._burn("v").exists())

    def test_rejects_audio_only_and_same_file(self):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1",
                        str(self.tmp / "a.mp3")], check=True)
        (self.tmp / "s.srt").write_text(SRT, encoding="utf-8")
        with self.assertRaises(RuntimeError):
            burn_subtitles(self.tmp / "a.mp3", self.tmp / "s.srt", self.tmp / "o.mp4")
        make_video(self.tmp / "in.mp4")
        with self.assertRaises(RuntimeError):
            burn_subtitles(self.tmp / "in.mp4", self.tmp / "s.srt", self.tmp / "in.mp4")


def install_stub_whisper(words=None, language="en"):
    """Register a fake `faster_whisper` module so the CLI can run without model weights."""
    from types import SimpleNamespace as NS

    class WhisperModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, path, **k):
            info = NS(language=language, language_probability=0.97, duration=2.0)
            if words is None:
                return iter([]), info
            ws = [NS(start=s, end=e, word=t, probability=0.9) for s, e, t in words]
            seg = NS(start=ws[0].start, end=ws[-1].end, text=" ".join(w.word for w in ws), words=ws)
            return iter([seg]), info

    module = types.ModuleType("faster_whisper")
    module.WhisperModel = WhisperModel
    sys.modules["faster_whisper"] = module


WORDS = [(0.2, 0.5, " Faith"), (0.5, 0.9, " &"), (0.9, 1.3, " hope"), (1.3, 1.9, " today.")]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._saved = sys.modules.get("faster_whisper")
        self.addCleanup(self._restore)
        self.media = self.tmp / "clip.mp4"
        self.media.write_bytes(b"not real media")  # content irrelevant: Whisper is stubbed

    def _restore(self):
        if self._saved is None:
            sys.modules.pop("faster_whisper", None)
        else:
            sys.modules["faster_whisper"] = self._saved

    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def test_success_writes_all_files(self):
        install_stub_whisper(WORDS)
        code, out, _ = self._run(self.media, "-o", self.tmp / "o")
        self.assertEqual(code, cli.EXIT_OK)
        for ext in ("srt", "vtt", "txt", "words.json"):
            self.assertTrue((self.tmp / "o" / f"clip.{ext}").exists(), ext)

    def test_no_speech_exits_3_and_writes_nothing(self):
        install_stub_whisper(None)
        code, _, err = self._run(self.media, "-o", self.tmp / "o")
        self.assertEqual(code, cli.EXIT_NO_SPEECH)
        self.assertIn("no speech", err.lower())
        self.assertEqual(list((self.tmp / "o").iterdir()), [])

    def test_missing_input(self):
        code, _, err = self._run(self.tmp / "missing.mp4")
        self.assertEqual(code, cli.EXIT_BAD_INPUT)
        self.assertIn("not found", err)

    def test_txt_layout_sentences(self):
        install_stub_whisper(WORDS)
        self._run(self.media, "-o", self.tmp / "o", "--txt-layout", "sentences")
        self.assertEqual((self.tmp / "o" / "clip.txt").read_text(encoding="utf-8"), "Faith & hope today.\n")

    def test_invalid_numeric_args_rejected(self):
        for bad in (["--max-chars", "0"], ["--max-duration", "-1"], ["--max-gap", "-0.5"]):
            with self.subTest(arg=bad), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    cli.build_parser().parse_args([str(self.media), *bad])

    @unittest.skipUnless(HAVE_FFMPEG, "FFmpeg/ffprobe not installed")
    def test_burn_on_audio_only_fails_before_transcription(self):
        # If transcription were reached, the stub would raise; it is installed to prove it is not.
        install_stub_whisper(WORDS)
        audio = self.tmp / "talk.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1", str(audio)], check=True)
        code, out, err = self._run(audio, "--burn", "-o", self.tmp / "o")
        self.assertEqual(code, cli.EXIT_BAD_INPUT)
        self.assertNotIn("Model:", out)
        self.assertIn("no video stream", err)

    @unittest.skipUnless(HAVE_FFMPEG, "FFmpeg/ffprobe not installed")
    def test_burn_end_to_end(self):
        install_stub_whisper(WORDS)
        make_video(self.media, size="360x640")
        code, _, _ = self._run(self.media, "--burn", "-o", self.tmp / "o")
        self.assertEqual(code, cli.EXIT_OK)
        self.assertTrue((self.tmp / "o" / "clip.subtitled.mp4").stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
