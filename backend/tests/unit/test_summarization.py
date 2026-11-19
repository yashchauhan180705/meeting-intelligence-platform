"""Unit tests for mock summarization service — T057, T062.

Tests that MockSummarizationService returns correct data
and simulates errors properly.
"""

from app.models import LabelledSegment, TranscriptSegment
from tests.fixtures.mock_services import MockSummarizationService
from app.lib.summarization import RateLimitError, ServiceUnavailableError

import pytest


def _make_segments():
    return [
        LabelledSegment(
            segment=TranscriptSegment(start=0, end=5, text="Hello"),
            speaker_label="SPEAKER_00",
        ),
        LabelledSegment(
            segment=TranscriptSegment(start=5, end=10, text="World"),
            speaker_label="SPEAKER_01",
        ),
    ]


SPEAKER_NAMES = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}


class TestMockSummarizationService:
    """MockSummarizationService tests."""

    def test_meeting_mode_returns_summary(self):
        svc = MockSummarizationService()
        result = svc.summarize(_make_segments(), SPEAKER_NAMES, "meeting")
        assert result.overview
        assert len(result.key_points) > 0
        assert len(result.action_items) > 0
        assert result.debate_claims is None  # meeting mode

    def test_debate_mode_returns_claims(self):
        svc = MockSummarizationService()
        result = svc.summarize(_make_segments(), SPEAKER_NAMES, "debate")
        assert result.debate_claims is not None
        assert len(result.debate_claims) > 0

    def test_rate_limit_error(self):
        svc = MockSummarizationService(should_fail="rate_limit")
        with pytest.raises(RateLimitError) as exc_info:
            svc.summarize(_make_segments(), SPEAKER_NAMES, "meeting")
        assert exc_info.value.retry_after_seconds == 30

    def test_service_unavailable_error(self):
        svc = MockSummarizationService(should_fail="unavailable")
        with pytest.raises(ServiceUnavailableError):
            svc.summarize(_make_segments(), SPEAKER_NAMES, "meeting")
