"""Unit tests for analytics computation — T033.

Tests the pure compute_analytics() function.
"""

from app.lib.analytics import compute_analytics
from app.models import LabelledSegment, TranscriptSegment


def _seg(start, end, text, speaker, low_conf=False):
    """Helper to create a LabelledSegment."""
    return LabelledSegment(
        segment=TranscriptSegment(start=start, end=end, text=text),
        speaker_label=speaker,
        is_low_confidence=low_conf,
    )


class TestAnalyticsComputation:
    """compute_analytics() tests."""

    def test_talk_time_pct_sums_to_100(self):
        """All speaker percentages sum to 100%."""
        segments = [
            _seg(0, 5, "Hello", "A"),
            _seg(5, 10, "World", "B"),
        ]
        analytics = compute_analytics(segments, total_duration=10.0)
        total_pct = sum(m.talk_time_pct for m in analytics.speaker_metrics)
        assert abs(total_pct - 100.0) < 0.1

    def test_turn_count_correct(self):
        """Turn count per speaker is accurate."""
        segments = [
            _seg(0, 3, "One", "A"),
            _seg(3, 6, "Two", "B"),
            _seg(6, 9, "Three", "A"),
        ]
        analytics = compute_analytics(segments, total_duration=9.0)
        metrics = {m.speaker_label: m for m in analytics.speaker_metrics}
        assert metrics["A"].turn_count == 2
        assert metrics["B"].turn_count == 1

    def test_avg_turn_length(self):
        """Average turn length = total_time / turn_count."""
        segments = [
            _seg(0, 4, "First", "A"),
            _seg(4, 8, "Second", "A"),
        ]
        analytics = compute_analytics(segments, total_duration=8.0)
        assert analytics.speaker_metrics[0].avg_turn_length_seconds == 4.0

    def test_interruption_detection(self):
        """Overlapping segments from different speakers count as interruptions."""
        segments = [
            _seg(0, 5, "Speaking", "A"),
            _seg(4, 8, "Interrupting", "B"),  # starts before A ends
        ]
        analytics = compute_analytics(segments, total_duration=8.0)
        assert analytics.interruption_count == 1

    def test_no_interruption_sequential(self):
        """Sequential segments have no interruptions."""
        segments = [
            _seg(0, 5, "First", "A"),
            _seg(5, 10, "Second", "B"),
        ]
        analytics = compute_analytics(segments, total_duration=10.0)
        assert analytics.interruption_count == 0

    def test_empty_segments(self):
        """Empty segments return zero metrics."""
        analytics = compute_analytics([], total_duration=0.0)
        assert analytics.speaker_metrics == []
        assert analytics.interruption_count == 0

    def test_single_speaker(self):
        """Single speaker gets 100% talk time."""
        segments = [
            _seg(0, 10, "Monologue", "A"),
        ]
        analytics = compute_analytics(segments, total_duration=10.0)
        assert len(analytics.speaker_metrics) == 1
        assert analytics.speaker_metrics[0].talk_time_pct == 100.0
