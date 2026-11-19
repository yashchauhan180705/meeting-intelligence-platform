"""Transcription library module.

Defines the TranscriptionService protocol and the TranscriptSegment type.
Business logic only — no framework dependencies.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models import TranscriptSegment


@runtime_checkable
class TranscriptionService(Protocol):
    """Interface for audio-to-text transcription."""

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> list[TranscriptSegment]:
        """Transcribe audio and return timestamped segments."""
        ...
