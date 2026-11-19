"""Unit tests for speaker renaming — T049.

Tests the pure apply_rename() function.
"""

from app.lib.speaker_renaming import apply_rename


class TestSpeakerRenaming:
    """apply_rename() tests."""

    def test_basic_replacement(self):
        text = "Speaker 1 said hello. Speaker 1 then asked a question."
        result = apply_rename(text, "Speaker 1", "Rahul")
        assert result == "Rahul said hello. Rahul then asked a question."

    def test_multiple_occurrences(self):
        text = "Speaker 2 spoke, then Speaker 2 continued."
        result = apply_rename(text, "Speaker 2", "Priya")
        assert "Speaker 2" not in result
        assert result.count("Priya") == 2

    def test_word_boundary_prevents_partial_match(self):
        """'Speaker 1' must not match inside 'Speaker 10'."""
        text = "Speaker 1 and Speaker 10 discussed."
        result = apply_rename(text, "Speaker 1", "Rahul")
        assert result == "Rahul and Speaker 10 discussed."

    def test_empty_text_returns_empty(self):
        assert apply_rename("", "Speaker 1", "Rahul") == ""

    def test_empty_old_name_returns_unchanged(self):
        text = "Hello world"
        assert apply_rename(text, "", "Rahul") == text

    def test_no_match_returns_unchanged(self):
        text = "Nobody mentioned Speaker 5 here."
        result = apply_rename(text, "Speaker 3", "Rahul")
        assert result == text

    def test_special_chars_in_name(self):
        text = "Dr. Smith (PhD) presented."
        result = apply_rename(text, "Dr. Smith (PhD)", "Dr. Johnson")
        assert result == "Dr. Johnson presented."
