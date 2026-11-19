"""Processing pipeline orchestrator.

Orchestrates: Uploading → Transcribing → Diarizing → Analyzing → Summarizing → Complete.
Updates conversation status in DB after each step.
On failure: sets status='failed', stores error_message, keeps last_completed_step.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Literal

import aiosqlite

from app.lib.analytics import compute_analytics
from app.lib.diarization import DiarizationService
from app.lib.summarization import (
    RateLimitError,
    ServiceUnavailableError,
    SummarizationService,
)
from app.lib.transcription import TranscriptionService
from app.lib.transcript_merger import merge
from app.models import LabelledSegment

logger = logging.getLogger(__name__)

PIPELINE_STEPS = [
    "uploading",
    "transcribing",
    "diarizing",
    "analyzing",
    "summarizing",
    "complete",
]


async def _update_status(
    db: aiosqlite.Connection,
    conversation_id: str,
    status: str,
    last_completed: str | None = None,
    error_msg: str | None = None,
) -> None:
    """Update conversation processing status in the database."""
    await db.execute(
        """UPDATE conversations
           SET processing_status = ?,
               last_completed_step = COALESCE(?, last_completed_step),
               error_message = ?
           WHERE id = ?""",
        (status, last_completed, error_msg, conversation_id),
    )
    await db.commit()


def _compute_transcript_hash(segments: list[LabelledSegment]) -> str:
    """SHA-256 hash of concatenated segment texts for change detection."""
    text = "".join(s.segment.text for s in segments)
    return hashlib.sha256(text.encode()).hexdigest()


async def run_pipeline(
    db: aiosqlite.Connection,
    conversation_id: str,
    audio_path: str,
    transcription_service: TranscriptionService,
    diarization_service: DiarizationService,
    summarization_service: SummarizationService,
    speaker_count_hint: int | None = None,
    is_debate: bool = False,
    language: str | None = None,
    low_confidence_threshold: float = 0.5,
    start_from: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the full processing pipeline, yielding progress events.

    Yields dicts with shape:
        {"step": str, "status": "running"|"done"|"error", "progress_pct": float|None, "error": str|None}

    Args:
        db: Open aiosqlite connection.
        conversation_id: The conversation to process.
        audio_path: Path to the audio file.
        transcription_service: Whisper adapter.
        diarization_service: Pyannote adapter.
        summarization_service: Gemini adapter.
        speaker_count_hint: Optional speaker count.
        is_debate: Whether to use debate mode for summarization.
        language: Optional language hint for transcription.
        low_confidence_threshold: Threshold for merger confidence.
        start_from: If retrying, the step to start from.
    """
    steps_to_run = PIPELINE_STEPS[:]
    if start_from and start_from in steps_to_run:
        idx = steps_to_run.index(start_from)
        steps_to_run = steps_to_run[idx:]

    # Shared state across steps
    transcript_segments = []
    diarization_intervals = []
    labelled_segments: list[LabelledSegment] = []

    # --- Step: Transcribing ---
    if "transcribing" in steps_to_run:
        try:
            await _update_status(db, conversation_id, "transcribing")
            yield {"step": "transcribing", "status": "running", "progress_pct": None, "error": None}

            transcript_segments = transcription_service.transcribe(audio_path, language=language)
            logger.info("Transcription produced %d segments", len(transcript_segments))

            await _update_status(db, conversation_id, "transcribing", last_completed="transcribing")
            yield {"step": "transcribing", "status": "done", "progress_pct": 100, "error": None}
        except Exception as exc:
            error_msg = f"Transcription failed: {exc}"
            logger.error(error_msg)
            await _update_status(db, conversation_id, "failed", error_msg=error_msg)
            yield {"step": "transcribing", "status": "error", "progress_pct": None, "error": error_msg}
            return

    # --- Step: Diarizing ---
    if "diarizing" in steps_to_run:
        try:
            await _update_status(db, conversation_id, "diarizing")
            yield {"step": "diarizing", "status": "running", "progress_pct": None, "error": None}

            diarization_intervals = diarization_service.diarize(
                audio_path, num_speakers=speaker_count_hint
            )
            logger.info("Diarization produced %d intervals", len(diarization_intervals))

            # Merge transcript + diarization
            labelled_segments = merge(
                transcript_segments, diarization_intervals, low_confidence_threshold
            )

            # Save speakers and segments to DB
            await _save_speakers_and_segments(
                db, conversation_id, labelled_segments
            )

            await _update_status(db, conversation_id, "diarizing", last_completed="diarizing")
            yield {"step": "diarizing", "status": "done", "progress_pct": 100, "error": None}
        except Exception as exc:
            error_msg = f"Diarization failed: {exc}"
            logger.error(error_msg)
            await _update_status(db, conversation_id, "failed", error_msg=error_msg)
            yield {"step": "diarizing", "status": "error", "progress_pct": None, "error": error_msg}
            return

    # --- Step: Analyzing ---
    if "analyzing" in steps_to_run:
        try:
            await _update_status(db, conversation_id, "analyzing")
            yield {"step": "analyzing", "status": "running", "progress_pct": None, "error": None}

            # Get total duration from audio file record
            row = await db.execute_fetchall(
                "SELECT duration_seconds FROM audio_files WHERE conversation_id = ?",
                (conversation_id,),
            )
            total_duration = row[0][0] if row and row[0][0] else 0.0

            # If we need to reload segments from DB (retry scenario)
            if not labelled_segments:
                labelled_segments = await _load_labelled_segments(db, conversation_id)

            analytics = compute_analytics(labelled_segments, total_duration)

            # Save analytics to DB
            await _save_analytics(db, conversation_id, analytics)

            await _update_status(db, conversation_id, "analyzing", last_completed="analyzing")
            yield {"step": "analyzing", "status": "done", "progress_pct": 100, "error": None}
        except Exception as exc:
            error_msg = f"Analytics failed: {exc}"
            logger.error(error_msg)
            await _update_status(db, conversation_id, "failed", error_msg=error_msg)
            yield {"step": "analyzing", "status": "error", "progress_pct": None, "error": error_msg}
            return

    # --- Step: Summarizing ---
    if "summarizing" in steps_to_run:
        max_summarize_attempts = 2
        for s_attempt in range(max_summarize_attempts):
            try:
                await _update_status(db, conversation_id, "summarizing")
                yield {"step": "summarizing", "status": "running", "progress_pct": None, "error": None}

                if not labelled_segments:
                    labelled_segments = await _load_labelled_segments(db, conversation_id)

                # Build speaker name map
                speaker_rows = await db.execute_fetchall(
                    "SELECT system_label, display_name FROM speakers WHERE conversation_id = ?",
                    (conversation_id,),
                )
                speaker_names = {r[0]: r[1] for r in speaker_rows}

                mode: Literal["meeting", "debate"] = "debate" if is_debate else "meeting"
                summary = summarization_service.summarize(labelled_segments, speaker_names, mode)

                # Save summary to DB
                transcript_hash = _compute_transcript_hash(labelled_segments)
                await _save_summary(db, conversation_id, summary, transcript_hash)

                await _update_status(db, conversation_id, "complete", last_completed="summarizing")
                yield {"step": "summarizing", "status": "done", "progress_pct": 100, "error": None}
                break  # success, exit retry loop
            except RateLimitError as exc:
                if s_attempt < max_summarize_attempts - 1:
                    import asyncio as _aio
                    wait = 10
                    logger.warning("Summarization rate-limited, retrying in %ds (attempt %d/%d)", wait, s_attempt + 1, max_summarize_attempts)
                    yield {"step": "summarizing", "status": "running", "progress_pct": None, "error": f"Rate limited, retrying in {wait}s..."}
                    await _aio.sleep(wait)
                    continue
                error_msg = f"Summary delayed: {exc}"
                logger.warning(error_msg)
                # Keep conversation complete and accessible!
                await _update_status(db, conversation_id, "complete", last_completed="analyzing", error_msg=error_msg)
                yield {"step": "summarizing", "status": "error", "progress_pct": None, "error": error_msg}
                break
            except (ServiceUnavailableError, Exception) as exc:
                error_msg = f"Summary pending: {exc}"
                logger.warning(error_msg)
                # Keep conversation complete and accessible!
                await _update_status(db, conversation_id, "complete", last_completed="analyzing", error_msg=error_msg)
                yield {"step": "summarizing", "status": "error", "progress_pct": None, "error": error_msg}
                break

    # Final done event
    yield {"step": "complete", "status": "done", "progress_pct": 100, "error": None}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _save_speakers_and_segments(
    db: aiosqlite.Connection,
    conversation_id: str,
    labelled_segments: list[LabelledSegment],
) -> None:
    """Persist speakers and transcript segments to the database."""
    # Collect unique speakers
    unique_speakers: dict[str, str] = {}  # system_label → speaker_id
    speaker_order = 0
    for seg in labelled_segments:
        if seg.speaker_label not in unique_speakers:
            speaker_id = str(uuid.uuid4())
            unique_speakers[seg.speaker_label] = speaker_id
            color_idx = speaker_order % 10
            await db.execute(
                """INSERT INTO speakers (id, conversation_id, system_label, display_name, color_index, order_index)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (speaker_id, conversation_id, seg.speaker_label, seg.speaker_label, color_idx, speaker_order),
            )
            speaker_order += 1

    # Insert segments
    for i, seg in enumerate(labelled_segments):
        speaker_id = unique_speakers[seg.speaker_label]
        await db.execute(
            """INSERT INTO segments (id, conversation_id, speaker_id, start_time, end_time, text, confidence, is_low_confidence, language_code, order_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), conversation_id, speaker_id,
                seg.segment.start, seg.segment.end, seg.segment.text,
                seg.segment.confidence, int(seg.is_low_confidence),
                seg.segment.language, i,
            ),
        )

    # Update conversation duration if available
    if labelled_segments:
        max_end = max(s.segment.end for s in labelled_segments)
        await db.execute(
            "UPDATE conversations SET duration_seconds = ? WHERE id = ?",
            (max_end, conversation_id),
        )

    await db.commit()


async def _save_analytics(
    db: aiosqlite.Connection,
    conversation_id: str,
    analytics,
) -> None:
    """Persist analytics and speaker metrics to the database."""
    analytics_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT OR REPLACE INTO analytics (id, conversation_id, computed_at, total_duration_seconds, interruption_count)
           VALUES (?, ?, ?, ?, ?)""",
        (analytics_id, conversation_id, now, analytics.total_duration_seconds, analytics.interruption_count),
    )

    # Get speaker_id map
    speaker_rows = await db.execute_fetchall(
        "SELECT system_label, id FROM speakers WHERE conversation_id = ?",
        (conversation_id,),
    )
    speaker_id_map = {r[0]: r[1] for r in speaker_rows}

    for metric in analytics.speaker_metrics:
        speaker_db_id = speaker_id_map.get(metric.speaker_label, "unknown")
        await db.execute(
            """INSERT INTO speaker_metrics (id, analytics_id, speaker_id, talk_time_seconds, talk_time_pct, turn_count, avg_turn_length_seconds, interruption_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), analytics_id, speaker_db_id,
                metric.talk_time_seconds, metric.talk_time_pct,
                metric.turn_count, metric.avg_turn_length_seconds,
                metric.interruption_count,
            ),
        )

    await db.commit()


async def _save_summary(
    db: aiosqlite.Connection,
    conversation_id: str,
    summary,
    transcript_hash: str,
) -> None:
    """Persist AI-generated summary to the database."""
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT OR REPLACE INTO summaries (id, conversation_id, overview, key_points, decisions, action_items, debate_claims, generated_at, transcript_hash, model_used)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()), conversation_id,
            summary.overview,
            json.dumps(summary.key_points),
            json.dumps(summary.decisions),
            json.dumps(summary.action_items),
            json.dumps(summary.debate_claims) if summary.debate_claims else None,
            now, transcript_hash, "gemini-1.5-flash",
        ),
    )
    await db.commit()


async def _load_labelled_segments(
    db: aiosqlite.Connection,
    conversation_id: str,
) -> list[LabelledSegment]:
    """Reload labelled segments from the database (for retry scenarios)."""
    from app.models import TranscriptSegment as TS

    rows = await db.execute_fetchall(
        """SELECT s.start_time, s.end_time, s.text, s.confidence, s.language_code,
                  s.is_low_confidence, sp.system_label
           FROM segments s
           JOIN speakers sp ON s.speaker_id = sp.id
           WHERE s.conversation_id = ?
           ORDER BY s.order_index""",
        (conversation_id,),
    )
    return [
        LabelledSegment(
            segment=TS(
                start=r[0], end=r[1], text=r[2],
                confidence=r[3], language=r[4],
            ),
            speaker_label=r[6],
            is_low_confidence=bool(r[5]),
        )
        for r in rows
    ]
