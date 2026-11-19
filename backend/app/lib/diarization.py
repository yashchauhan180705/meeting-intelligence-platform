"""Diarization library module.

Defines the DiarizationService protocol and the SpeakerInterval type.
Business logic only — no framework dependencies.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models import SpeakerInterval


@runtime_checkable
class DiarizationService(Protocol):
    """Interface for speaker diarization."""

    def diarize(
        self,
        audio_path: str,
        num_speakers: int | None = None,
    ) -> list[SpeakerInterval]:
        """Separate audio into speaker-labelled time intervals."""
        ...
