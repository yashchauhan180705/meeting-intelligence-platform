"""Unit tests for transcript merger — T032.

Tests the pure merge() function with various overlap scenarios.
"""

from app.lib.transcript_merger import merge
from app.models import SpeakerInterval, TranscriptSegment


class TestTranscriptMerger:
    """Merge function tests."""

    def test_exact_overlap_assigns_correct_speaker(self):
        """Exact time overlap → speaker is assigned correctly."""
        segments = [
            TranscriptSegment(start=0.0, end=5.0, text="Hello"),
            TranscriptSegment(start=5.0, end=10.0, text="World"),
        ]
        diarization = [
            SpeakerInterval(speaker_label="A", start=0.0, end=5.0),
            SpeakerInterval(speaker_label="B", start=5.0, end=10.0),
        ]
        result = merge(segments, diarization)
        assert result[0].speaker_label == "A"
        assert result[1].speaker_label == "B"
        assert not result[0].is_low_confidence
        assert not result[1].is_low_confidence

    def test_partial_overlap_largest_wins(self):
        """Partial overlap → speaker with largest overlap wins."""
        segments = [
            TranscriptSegment(start=2.0, end=6.0, text="Overlap test"),
        ]
        diarization = [
            SpeakerInterval(speaker_label="A", start=0.0, end=3.0),  # 1s overlap
            SpeakerInterval(speaker_label="B", start=3.0, end=8.0),  # 3s overlap
        ]
        result = merge(segments, diarization)
        assert result[0].speaker_label == "B"

    def test_no_match_gives_unknown_low_confidence(self):
        """No diarization overlap → UNKNOWN speaker + low confidence."""
        segments = [
            TranscriptSegment(start=20.0, end=25.0, text="No match"),
        ]
        diarization = [
            SpeakerInterval(speaker_label="A", start=0.0, end=5.0),
        ]
        result = merge(segments, diarization)
        assert result[0].speaker_label == "UNKNOWN"
        assert result[0].is_low_confidence

    def test_empty_segments_returns_empty(self):
        """Empty input → empty output."""
        result = merge([], [])
        assert result == []

    def test_empty_diarization_all_unknown(self):
        """No diarization data → all segments are UNKNOWN."""
        segments = [
            TranscriptSegment(start=0.0, end=5.0, text="Hello"),
        ]
        result = merge(segments, [])
        assert result[0].speaker_label == "UNKNOWN"
        assert result[0].is_low_confidence

    def test_low_confidence_threshold(self):
        """Low overlap ratio triggers low confidence."""
        segments = [
            TranscriptSegment(start=0.0, end=10.0, text="Long segment"),
        ]
        diarization = [
            SpeakerInterval(speaker_label="A", start=0.0, end=2.0),  # 20% overlap
        ]
        result = merge(segments, diarization, low_confidence_threshold=0.5)
        assert result[0].speaker_label == "A"
        assert result[0].is_low_confidence  # 20% < 50% threshold

    def test_multiple_speakers_assigned_correctly(self):
        """Multi-speaker conversation merges correctly."""
        segments = [
            TranscriptSegment(start=0.0, end=3.0, text="First"),
            TranscriptSegment(start=3.0, end=6.0, text="Second"),
            TranscriptSegment(start=6.0, end=9.0, text="Third"),
        ]
        diarization = [
            SpeakerInterval(speaker_label="A", start=0.0, end=3.0),
            SpeakerInterval(speaker_label="B", start=3.0, end=6.0),
            SpeakerInterval(speaker_label="A", start=6.0, end=9.0),
        ]
        result = merge(segments, diarization)
        assert [r.speaker_label for r in result] == ["A", "B", "A"]
