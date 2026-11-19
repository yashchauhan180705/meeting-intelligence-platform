"""Mock services for testing — implements all service protocols without real AI calls."""

from __future__ import annotations

from typing import Literal

from app.models import (
    ConversationSummary,
    LabelledSegment,
    SpeakerInterval,
    TranscriptSegment,
)


class MockTranscriptionService:
    """Returns fixture transcript segments without calling Whisper."""

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(start=0.0, end=3.5, text="Hello, welcome to the meeting.", confidence=0.95, language=language or "en"),
            TranscriptSegment(start=3.5, end=7.0, text="Thanks for having me.", confidence=0.92, language=language or "en"),
            TranscriptSegment(start=7.0, end=12.0, text="Let's discuss the project timeline.", confidence=0.88, language=language or "en"),
            TranscriptSegment(start=12.0, end=16.0, text="I think we need two more weeks.", confidence=0.90, language=language or "en"),
        ]


class MockDiarizationService:
    """Returns fixture speaker intervals without calling pyannote."""

    def diarize(
        self,
        audio_path: str,
        num_speakers: int | None = None,
    ) -> list[SpeakerInterval]:
        return [
            SpeakerInterval(speaker_label="SPEAKER_00", start=0.0, end=3.5),
            SpeakerInterval(speaker_label="SPEAKER_01", start=3.5, end=7.0),
            SpeakerInterval(speaker_label="SPEAKER_00", start=7.0, end=12.0),
            SpeakerInterval(speaker_label="SPEAKER_01", start=12.0, end=16.0),
        ]


class MockSummarizationService:
    """Returns fixture summary without calling Gemini."""

    def __init__(self, should_fail: str | None = None):
        """Args: should_fail — 'rate_limit' or 'unavailable' to simulate errors."""
        self._should_fail = should_fail

    def summarize(
        self,
        segments: list[LabelledSegment],
        speaker_names: dict[str, str],
        mode: Literal["meeting", "debate"],
    ) -> ConversationSummary:
        if self._should_fail == "rate_limit":
            from app.lib.summarization import RateLimitError
            raise RateLimitError(retry_after_seconds=30)
        if self._should_fail == "unavailable":
            from app.lib.summarization import ServiceUnavailableError
            raise ServiceUnavailableError("Mock service unavailable")

        debate_claims = None
        if mode == "debate":
            debate_claims = [
                {"speaker": list(speaker_names.values())[0] if speaker_names else "Speaker 1", "claim": "We need more time for testing."},
                {"speaker": list(speaker_names.values())[1] if len(speaker_names) > 1 else "Speaker 2", "claim": "The current timeline is sufficient."},
            ]

        return ConversationSummary(
            overview="This was a productive meeting discussing project timeline and deliverables.",
            key_points=[
                "Project timeline was reviewed",
                "Two additional weeks were proposed",
                "Team agreed to reassess next week",
            ],
            decisions=[
                "Extend timeline by one week as a compromise",
            ],
            action_items=[
                {"text": "Update project plan with new dates", "owner": list(speaker_names.values())[0] if speaker_names else None},
                {"text": "Send status report to stakeholders", "owner": list(speaker_names.values())[1] if len(speaker_names) > 1 else None},
            ],
            debate_claims=debate_claims,
        )
