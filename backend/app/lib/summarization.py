"""Summarization library module.

Defines the SummarizationService protocol and error types.
Business logic only — no framework dependencies.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from app.models import ConversationSummary, LabelledSegment


class RateLimitError(Exception):
    """Raised when the AI API returns a 429 rate-limit response."""

    def __init__(self, retry_after_seconds: int = 60):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limited. Retry after {retry_after_seconds}s.")


class ServiceUnavailableError(Exception):
    """Raised when the AI API is unreachable or returns 5xx."""

    pass


@runtime_checkable
class SummarizationService(Protocol):
    """Interface for AI-powered conversation summarization."""

    def summarize(
        self,
        segments: list[LabelledSegment],
        speaker_names: dict[str, str],
        mode: Literal["meeting", "debate"],
    ) -> ConversationSummary:
        """Generate a conversation summary.

        Args:
            segments: The full transcript with speaker labels.
            speaker_names: Mapping of speaker_label → display name.
            mode: "meeting" for standard summary, "debate" for claim extraction.

        Returns:
            A ConversationSummary.

        Raises:
            RateLimitError: If the API rate limit is hit.
            ServiceUnavailableError: If the API is unreachable.
        """
        ...
