import json
import random
import tempfile
import unittest
from pathlib import Path

from transcription_subtitle_generator.core import (
    SENTENCE_END,
    Cue,
    Word,
    _ffmpeg_escape_filter_path,
    compute_font_size,
    srt_timestamp,
    vtt_timestamp,
    words_to_cues,
    words_to_sentences,
    write_srt,
    write_txt_sentences,
    write_vtt,
    write_words_json,
)


def _words(texts, step=0.4, start=0.0):
    out, t = [], start
    for text in texts:
        out.append(Word(t, t + step, text))
        t += step
    return out


class TimestampTests(unittest.TestCase):
    def test_srt(self):
        self.assertEqual(srt_timestamp(61.234), "00:01:01,234")

    def test_vtt_uses_dot(self):
        self.assertEqual(vtt_timestamp(61.234), "00:01:01.234")

    def test_negative_clamped(self):
        self.assertEqual(srt_timestamp(-1), "00:00:00,000")


class CueTests(unittest.TestCase):
    def test_cue_split_and_wrap(self):
        words = _words(["This", "is", "a", "subtitle", "generation", "test."]) + [
            Word(3.5, 3.9, "New"), Word(3.9, 4.3, "sentence.")]
        cues = words_to_cues(words, max_chars_per_line=20, max_lines=2, max_gap=0.8)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0].text, "This is a subtitle\ngeneration test.")
        self.assertEqual(cues[1].text, "New sentence.")

    def test_empty(self):
        self.assertEqual(words_to_cues([]), [])

    def test_gap_splits(self):
        cues = words_to_cues([Word(0, 0.5, "one"), Word(3.0, 3.5, "two")], max_gap=0.8)
        self.assertEqual([c.text for c in cues], ["one", "two"])

    def test_no_overlap_when_padding_short_cue(self):
        # A long word duration forces a duration split; "Okay." is then padded to min_duration.
        words = [Word(0.0, 0.2, "Okay."), Word(0.3, 7.0, "Alright"), Word(7.1, 7.5, "then.")]
        cues = words_to_cues(words)
        for a, b in zip(cues, cues[1:]):
            self.assertLessEqual(a.end, b.start)
            self.assertGreater(a.end, a.start)

    def test_hindi_danda_breaks_sentence(self):
        hi = _words(["यह", "एक", "बहुत", "अच्छा", "संदेश", "है।", "आइए", "प्रार्थना", "करें।"], step=0.5)
        cues = words_to_cues(hi, max_chars_per_line=20, max_duration=60)
        self.assertTrue(cues[0].text.replace("\n", " ").endswith("है।"))
        self.assertEqual(cues[1].text.replace("\n", " "), "आइए प्रार्थना करें।")

    def test_sentence_end_markers(self):
        for token in ["done.", "what?", "wow!", "है।", "समाप्त॥", "ختم۔", "کیا؟", "wait…", 'said."']:
            self.assertTrue(SENTENCE_END.search(token), token)
        for token in ["hello", "and,", "3.5x"]:
            self.assertFalse(SENTENCE_END.search(token), token)

    def test_lines_respect_limits_fuzz(self):
        """No cue may have more than max_lines lines or a line longer than max_chars (single
        over-long words excepted), and cues must never overlap."""
        random.seed(5)
        for _ in range(600):
            mc = random.choice([20, 30, 38, 42])
            ml = random.choice([1, 2])
            t, words = 0.0, []
            for _ in range(random.randint(1, 30)):
                dur = random.choice([0.1, 0.3, 0.5, 1.5])
                text = "x" * random.choice([2, 4, 6, 9, 12, 16, 20]) + random.choice(["", "", "."])
                words.append(Word(t, t + dur, text))
                t += dur + random.uniform(0, 0.5)
            cues = words_to_cues(words, max_chars_per_line=mc, max_lines=ml)
            for c in cues:
                lines = c.text.split("\n")
                self.assertLessEqual(len(lines), ml)
                if not any(len(w) > mc for w in c.text.split()):
                    self.assertTrue(all(len(l) <= mc for l in lines), (mc, ml, c.text))
            for a, b in zip(cues, cues[1:]):
                self.assertLessEqual(a.end, b.start + 1e-9)


class SentenceTests(unittest.TestCase):
    def test_words_to_sentences(self):
        words = _words(["Hello", "there.", "How", "are", "you?", "Fine"])
        self.assertEqual(words_to_sentences(words), ["Hello there.", "How are you?", "Fine"])


class WriterTests(unittest.TestCase):
    def test_outputs(self):
        cues = [Cue(0.0, 1.5, "Faith & hope <b>win</b>"), Cue(2.0, 3.0, "Line one\nLine two")]
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            write_srt(cues, d / "a.srt")
            write_vtt(cues, d / "a.vtt")
            srt = (d / "a.srt").read_text(encoding="utf-8")
            vtt = (d / "a.vtt").read_text(encoding="utf-8")
        self.assertTrue(srt.startswith("1\n00:00:00,000 --> 00:00:01,500\n"))
        self.assertIn("Line one\nLine two", srt)
        self.assertTrue(vtt.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.500\n"))
        self.assertIn("Faith &amp; hope &lt;b&gt;win&lt;/b&gt;", vtt)
        self.assertIn("Faith & hope <b>win</b>", srt)  # SRT text is left as spoken

    def test_words_json_and_txt_sentences_unicode(self):
        words = _words(["യേശു", "സ്നേഹിക്കുന്നു."])
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            write_words_json(words, d / "w.json")
            write_txt_sentences(words, d / "t.txt")
            data = json.loads((d / "w.json").read_text(encoding="utf-8"))
            txt = (d / "t.txt").read_text(encoding="utf-8")
        self.assertEqual(data[0]["text"], "യേശു")
        self.assertEqual(txt, "യേശു സ്നേഹിക്കുന്നു.\n")


class FontScaleTests(unittest.TestCase):
    def test_landscape_16_9_unchanged(self):
        self.assertEqual(compute_font_size(24, 1920, 1080), 24)
        self.assertEqual(compute_font_size(24, 1280, 720), 24)

    def test_ultrawide_unchanged(self):
        self.assertEqual(compute_font_size(24, 2560, 1080), 24)

    def test_portrait_and_square_scaled_down(self):
        self.assertLess(compute_font_size(24, 1080, 1920), 12)
        self.assertLess(compute_font_size(24, 1080, 1080), 24)

    def test_disabled_and_unknown(self):
        self.assertEqual(compute_font_size(24, 1080, 1920, auto_scale=False), 24)
        self.assertEqual(compute_font_size(24, None, None), 24)


class EscapeTests(unittest.TestCase):
    def test_apostrophe_is_closed_escaped_reopened(self):
        value = _ffmpeg_escape_filter_path(Path("/tmp/John's Videos/in.srt"))
        self.assertNotIn("Johns", value)
        self.assertIn("John'", value)
        self.assertIn("\\\\\\'", value)

    def test_colon_and_comma_escaped(self):
        value = _ffmpeg_escape_filter_path(Path("/tmp/a:b,c/in.srt"))
        self.assertIn(r"a\:b\,c", value)


if __name__ == "__main__":
    unittest.main()
