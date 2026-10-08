from transcription_subtitle_generator.core import Word, srt_timestamp, words_to_cues


def test_timestamp():
    assert srt_timestamp(61.234) == "00:01:01,234"


def test_cue_split_and_wrap():
    words = [
        Word(0.0, 0.4, "This"), Word(0.4, 0.8, "is"), Word(0.8, 1.2, "a"),
        Word(1.2, 1.6, "subtitle"), Word(1.6, 2.0, "generation"), Word(2.0, 2.4, "test."),
        Word(3.5, 3.9, "New"), Word(3.9, 4.3, "sentence."),
    ]
    cues = words_to_cues(words, max_chars_per_line=20, max_lines=2, max_gap=0.8)
    assert len(cues) >= 2
    assert all(c.end > c.start for c in cues)
