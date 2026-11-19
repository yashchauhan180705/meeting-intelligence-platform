"""Domain dataclasses for the audio processing pipeline.

These types are pure data containers — no I/O, no DB logic.
They match the data-model.md specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Pipeline intermediate types (used between library modules)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TranscriptSegment:
    """A single segment produced by the transcription service."""

    start: float
    end: float
    text: str
    confidence: float | None = None
    language: str | None = None


@dataclass(frozen=True)
class SpeakerInterval:
    """A speaker-labelled time interval produced by diarization."""

    speaker_label: str  # e.g. "SPEAKER_00"
    start: float
    end: float


@dataclass(frozen=True)
class LabelledSegment:
    """A transcript segment merged with its speaker assignment."""

    segment: TranscriptSegment
    speaker_label: str
    is_low_confidence: bool = False


@dataclass(frozen=True)
class SpeakerMetric:
    """Per-speaker analytics."""

    speaker_label: str
    talk_time_seconds: float
    talk_time_pct: float
    turn_count: int
    avg_turn_length_seconds: float
    interruption_count: int = 0


@dataclass(frozen=True)
class Analytics:
    """Computed analytics for a conversation."""

    total_duration_seconds: float
    interruption_count: int
    speaker_metrics: list[SpeakerMetric] = field(default_factory=list)


@dataclass(frozen=True)
class ConversationSummary:
    """AI-generated summary of a conversation."""

    overview: str
    key_points: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[dict] = field(default_factory=list)
    debate_claims: list[dict] | None = None


# ---------------------------------------------------------------------------
# DB row types (mirror SQLite tables for type-safe reads/writes)
# ---------------------------------------------------------------------------

@dataclass
class ConversationRow:
    """Mirrors the `conversations` table."""

    id: str
    title: str
    created_at: str
    duration_seconds: float | None = None
    speaker_count_hint: int | None = None
    processing_status: str = "uploading"
    is_debate: bool = False
    consent_granted_at: str = ""
    last_completed_step: str | None = None
    error_message: str | None = None


@dataclass
class AudioFileRow:
    """Mirrors the `audio_files` table."""

    id: str
    conversation_id: str
    file_path: str
    original_filename: str
    format: str
    size_bytes: int
    duration_seconds: float | None = None


@dataclass
class SpeakerRow:
    """Mirrors the `speakers` table."""

    id: str
    conversation_id: str
    system_label: str
    display_name: str
    color_index: int
    order_index: int


@dataclass
class SegmentRow:
    """Mirrors the `segments` table."""

    id: str
    conversation_id: str
    speaker_id: str
    start_time: float
    end_time: float
    text: str
    confidence: float | None = None
    is_low_confidence: bool = False
    language_code: str | None = None
    order_index: int = 0


@dataclass
class SummaryRow:
    """Mirrors the `summaries` table."""

    id: str
    conversation_id: str
    overview: str
    key_points: str  # JSON string
    decisions: str  # JSON string
    action_items: str  # JSON string
    debate_claims: str | None = None  # JSON string
    generated_at: str = ""
    transcript_hash: str = ""
    model_used: str = ""
