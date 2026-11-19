"""Conversations API router — upload, process, get, list, delete."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import Settings
from app.database import get_db
from app.lib.upload_validation import validate_file_extension, validate_file_size, validate_speaker_count
from app.pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# These will be injected from main.py via app.state
_settings: Settings | None = None
_transcription_service = None
_diarization_service = None
_summarization_service = None


def configure(settings, ts, ds, ss):
    """Inject services — called once from main.py lifespan."""
    global _settings, _transcription_service, _diarization_service, _summarization_service
    _settings = settings
    _transcription_service = ts
    _diarization_service = ds
    _summarization_service = ss


@router.post("", status_code=201)
async def create_conversation(
    audio_file: UploadFile = File(...),
    speaker_count_hint: int | None = Form(None),
    is_debate: bool = Form(False),
    title: str | None = Form(None),
    language: str | None = Form(None),
):
    """Upload audio and create a new conversation."""
    assert _settings is not None

    # Validate extension
    ext_err = validate_file_extension(audio_file.filename or "")
    if ext_err:
        raise HTTPException(status_code=400, detail={"error": ext_err.code, "message": ext_err.message})

    # Read file content
    content = await audio_file.read()

    # Validate size
    size_err = validate_file_size(len(content), _settings.max_upload_bytes)
    if size_err:
        raise HTTPException(status_code=400, detail={"error": size_err.code, "message": size_err.message})

    # Validate speaker count
    sc_err = validate_speaker_count(speaker_count_hint)
    if sc_err:
        raise HTTPException(status_code=400, detail={"error": sc_err.code, "message": sc_err.message})

    # Generate IDs
    conversation_id = str(uuid.uuid4())
    audio_file_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    original_filename = audio_file.filename or "recording.webm"
    ext = original_filename.rsplit(".", 1)[-1].lower()

    # Save audio to disk
    audio_dir = _settings.audio_storage_path / conversation_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / original_filename
    audio_path.write_bytes(content)

    # Auto-generate title if not provided
    if not title:
        title = f"Conversation {now[:10]}"

    # Insert into database
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO conversations (id, title, created_at, speaker_count_hint, processing_status, is_debate, consent_granted_at)
               VALUES (?, ?, ?, ?, 'uploading', ?, ?)""",
            (conversation_id, title, now, speaker_count_hint, int(is_debate), now),
        )
        await db.execute(
            """INSERT INTO audio_files (id, conversation_id, file_path, original_filename, format, size_bytes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (audio_file_id, conversation_id, str(audio_path), original_filename, ext, len(content)),
        )
        await db.commit()
    finally:
        await db.close()

    return {
        "id": conversation_id,
        "title": title,
        "created_at": now,
        "processing_status": "uploading",
        "speaker_count_hint": speaker_count_hint,
        "is_debate": is_debate,
    }


@router.post("/{conversation_id}/process", status_code=202)
async def start_processing(conversation_id: str, background_tasks: BackgroundTasks):
    """Start background pipeline processing for a conversation."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT processing_status FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Conversation not found"})
    finally:
        await db.close()

    # Launch pipeline in background
    background_tasks.add_task(_run_pipeline_bg, conversation_id)

    return {
        "conversation_id": conversation_id,
        "stream_url": f"/conversations/{conversation_id}/progress",
    }


async def _run_pipeline_bg(conversation_id: str):
    """Background task that runs the full pipeline."""
    assert _settings is not None

    db = await get_db()
    try:
        # Get audio path and conversation details
        rows = await db.execute_fetchall(
            """SELECT af.file_path, c.speaker_count_hint, c.is_debate, c.last_completed_step
               FROM audio_files af
               JOIN conversations c ON c.id = af.conversation_id
               WHERE af.conversation_id = ?""",
            (conversation_id,),
        )
        if not rows:
            return

        audio_path = rows[0][0]
        speaker_hint = rows[0][1]
        is_debate = bool(rows[0][2])
        last_step = rows[0][3]

        start_from = None
        from app.pipeline import PIPELINE_STEPS
        if last_step and last_step in PIPELINE_STEPS:
            idx = PIPELINE_STEPS.index(last_step)
            if idx + 1 < len(PIPELINE_STEPS) and PIPELINE_STEPS[idx + 1] != "complete":
                start_from = PIPELINE_STEPS[idx + 1]

        async for event in run_pipeline(
            db=db,
            conversation_id=conversation_id,
            audio_path=audio_path,
            transcription_service=_transcription_service,
            diarization_service=_diarization_service,
            summarization_service=_summarization_service,
            speaker_count_hint=speaker_hint,
            is_debate=is_debate,
            low_confidence_threshold=_settings.low_confidence_threshold,
            start_from=start_from,
        ):
            logger.info("Pipeline event: %s", event)
    finally:
        await db.close()


@router.get("/{conversation_id}/progress")
async def get_progress(conversation_id: str):
    """SSE endpoint for pipeline progress (simplified polling version)."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT processing_status, last_completed_step, error_message FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Conversation not found"})

        status = row[0][0]
        last_step = row[0][1]
        error = row[0][2]

        return {
            "conversation_id": conversation_id,
            "processing_status": status,
            "last_completed_step": last_step,
            "error_message": error,
        }
    finally:
        await db.close()


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get full conversation with speakers, segments, analytics, summary."""
    db = await get_db()
    try:
        # Conversation
        conv_rows = await db.execute_fetchall(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        if not conv_rows:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Conversation not found"})

        conv = conv_rows[0]

        # Speakers
        speaker_rows = await db.execute_fetchall(
            "SELECT * FROM speakers WHERE conversation_id = ? ORDER BY order_index",
            (conversation_id,),
        )

        # Segments
        segment_rows = await db.execute_fetchall(
            """SELECT s.*, sp.system_label, sp.display_name, sp.color_index
               FROM segments s
               JOIN speakers sp ON s.speaker_id = sp.id
               WHERE s.conversation_id = ?
               ORDER BY s.order_index""",
            (conversation_id,),
        )

        # Analytics
        analytics_rows = await db.execute_fetchall(
            "SELECT * FROM analytics WHERE conversation_id = ?",
            (conversation_id,),
        )
        metrics_rows = []
        if analytics_rows:
            metrics_rows = await db.execute_fetchall(
                """SELECT sm.*, sp.display_name, sp.color_index
                   FROM speaker_metrics sm
                   JOIN speakers sp ON sm.speaker_id = sp.id
                   WHERE sm.analytics_id = ?""",
                (analytics_rows[0][0],),
            )

        # Summary
        summary_rows = await db.execute_fetchall(
            "SELECT * FROM summaries WHERE conversation_id = ?",
            (conversation_id,),
        )

        return _build_conversation_response(
            conv, speaker_rows, segment_rows, analytics_rows, metrics_rows, summary_rows
        )
    finally:
        await db.close()


@router.get("")
async def list_conversations(limit: int = 50, offset: int = 0):
    """List conversations, sorted by created_at descending."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT c.id, c.title, c.created_at, c.duration_seconds, c.processing_status
               FROM conversations c
               ORDER BY c.created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        items = []
        for r in rows:
            speaker_rows = await db.execute_fetchall(
                "SELECT display_name FROM speakers WHERE conversation_id = ? ORDER BY order_index",
                (r[0],),
            )
            items.append({
                "id": r[0],
                "title": r[1],
                "created_at": r[2],
                "duration_seconds": r[3],
                "processing_status": r[4],
                "speaker_display_names": [s[0] for s in speaker_rows],
            })
        return {"items": items, "total": len(items)}
    finally:
        await db.close()


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str):
    """Delete conversation and all associated data."""
    assert _settings is not None

    db = await get_db()
    try:
        # Get audio path before deleting
        audio_rows = await db.execute_fetchall(
            "SELECT file_path FROM audio_files WHERE conversation_id = ?",
            (conversation_id,),
        )

        # Delete from DB (CASCADE handles children)
        result = await db.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Conversation not found"})

        # Delete audio files from disk
        for row in audio_rows:
            try:
                audio_path = Path(row[0])
                if audio_path.exists():
                    audio_path.unlink()
                # Remove parent directory if empty
                parent = audio_path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError as exc:
                logger.warning("Failed to delete audio file %s: %s", row[0], exc)
    finally:
        await db.close()


@router.patch("/{conversation_id}/speakers/{speaker_id}")
async def rename_speaker(conversation_id: str, speaker_id: str, body: dict):
    """Rename a speaker's display name."""
    display_name = body.get("display_name", "").strip()
    if not display_name or len(display_name) > 80:
        raise HTTPException(
            status_code=400,
            detail={"error": "VALIDATION_ERROR", "message": "display_name is required (max 80 chars)"},
        )

    db = await get_db()
    try:
        result = await db.execute(
            "UPDATE speakers SET display_name = ? WHERE id = ? AND conversation_id = ?",
            (display_name, speaker_id, conversation_id),
        )
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Speaker not found"})

        row = await db.execute_fetchall(
            "SELECT * FROM speakers WHERE id = ?", (speaker_id,)
        )
        return {
            "id": row[0][0],
            "conversation_id": row[0][1],
            "system_label": row[0][2],
            "display_name": row[0][3],
            "color_index": row[0][4],
        }
    finally:
        await db.close()


@router.patch("/{conversation_id}/segments/{segment_id}")
async def update_segment(conversation_id: str, segment_id: str, body: dict):
    """Update segment text and/or reassign to a different speaker."""
    text = body.get("text")
    speaker_id = body.get("speaker_id")

    if text is not None and len(text) > 4000:
        raise HTTPException(
            status_code=400,
            detail={"error": "VALIDATION_ERROR", "message": "Segment text cannot exceed 4000 characters"},
        )

    db = await get_db()
    try:
        updates = []
        params: list[Any] = []
        if text is not None:
            updates.append("text = ?")
            params.append(text)
        if speaker_id is not None:
            speaker_rows = await db.execute_fetchall(
                "SELECT id FROM speakers WHERE id = ? AND conversation_id = ?",
                (speaker_id, conversation_id),
            )
            if not speaker_rows:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "VALIDATION_ERROR",
                        "message": "speaker_id must belong to this conversation",
                    },
                )
            updates.append("speaker_id = ?")
            params.append(speaker_id)

        if not updates:
            raise HTTPException(status_code=400, detail={"error": "VALIDATION_ERROR", "message": "Nothing to update"})

        params.extend([segment_id, conversation_id])
        await db.execute(
            f"UPDATE segments SET {', '.join(updates)} WHERE id = ? AND conversation_id = ?",
            tuple(params),
        )
        await db.commit()

        row = await db.execute_fetchall(
            "SELECT * FROM segments WHERE id = ?", (segment_id,)
        )
        if not row:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Segment not found"})

        return {
            "id": row[0][0],
            "conversation_id": row[0][1],
            "speaker_id": row[0][2],
            "start_time": row[0][3],
            "end_time": row[0][4],
            "text": row[0][5],
        }
    finally:
        await db.close()


@router.post("/{conversation_id}/summary/regenerate")
async def regenerate_summary(conversation_id: str):
    """Regenerate summary using current transcript."""
    from app.pipeline import _load_labelled_segments, _compute_transcript_hash, _save_summary

    db = await get_db()
    try:
        conv_rows = await db.execute_fetchall(
            "SELECT is_debate FROM conversations WHERE id = ?", (conversation_id,)
        )
        if not conv_rows:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Conversation not found"})

        is_debate = bool(conv_rows[0][0])
        labelled = await _load_labelled_segments(db, conversation_id)

        speaker_rows = await db.execute_fetchall(
            "SELECT system_label, display_name FROM speakers WHERE conversation_id = ?",
            (conversation_id,),
        )
        speaker_names = {r[0]: r[1] for r in speaker_rows}

        mode = "debate" if is_debate else "meeting"

        try:
            summary = _summarization_service.summarize(labelled, speaker_names, mode)
        except Exception as exc:
            from app.lib.summarization import RateLimitError, ServiceUnavailableError
            if isinstance(exc, RateLimitError):
                return JSONResponse(status_code=429, content={
                    "error": "RATE_LIMITED",
                    "message": str(exc),
                    "retry_after_seconds": exc.retry_after_seconds,
                })
            raise HTTPException(status_code=503, detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": str(exc),
            })

        transcript_hash = _compute_transcript_hash(labelled)
        await _save_summary(db, conversation_id, summary, transcript_hash)

        return {
            "overview": summary.overview,
            "key_points": summary.key_points,
            "decisions": summary.decisions,
            "action_items": summary.action_items,
            "debate_claims": summary.debate_claims,
            "transcript_hash": transcript_hash,
        }
    finally:
        await db.close()


@router.get("/{conversation_id}/export")
async def export_conversation(conversation_id: str, format: str = "text"):
    """Export conversation as text or JSON."""
    db = await get_db()
    try:
        conv_data = await get_conversation(conversation_id)

        if format == "json":
            return conv_data

        # Build plain text export
        lines = [
            f"# {conv_data['title']}",
            f"Date: {conv_data['created_at']}",
            f"Speakers: {', '.join(s['display_name'] for s in conv_data.get('speakers', []))}",
            "",
            "## Transcript",
            "",
        ]
        for seg in conv_data.get("segments", []):
            lines.append(f"[{seg['start_time']:.1f}s - {seg['end_time']:.1f}s] {seg['speaker_display_name']}: {seg['text']}")

        if conv_data.get("summary"):
            s = conv_data["summary"]
            lines.extend(["", "## Summary", "", s.get("overview", "")])
            if s.get("key_points"):
                lines.extend(["", "### Key Points"])
                for kp in s["key_points"]:
                    lines.append(f"- {kp}")
            if s.get("action_items"):
                lines.extend(["", "### Action Items"])
                for ai in s["action_items"]:
                    owner = ai.get("owner", "Unassigned")
                    lines.append(f"- [{owner}] {ai.get('text', '')}")

        text = "\n".join(lines)
        return StreamingResponse(
            iter([text]),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{conv_data["title"]}.txt"'},
        )
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _build_conversation_response(conv, speakers, segments, analytics, metrics, summaries) -> dict:
    """Build the full conversation JSON response."""
    result: dict[str, Any] = {
        "id": conv[0],
        "title": conv[1],
        "created_at": conv[2],
        "duration_seconds": conv[3],
        "speaker_count_hint": conv[4],
        "processing_status": conv[5],
        "is_debate": bool(conv[6]),
        "last_completed_step": conv[8],
        "error_message": conv[9],
    }

    result["speakers"] = [
        {
            "id": s[0],
            "system_label": s[2],
            "display_name": s[3],
            "color_index": s[4],
        }
        for s in speakers
    ]

    result["segments"] = [
        {
            "id": s[0],
            "speaker_id": s[2],
            "start_time": s[3],
            "end_time": s[4],
            "text": s[5],
            "confidence": s[6],
            "is_low_confidence": bool(s[7]),
            "language_code": s[8],
            "speaker_system_label": s[10],
            "speaker_display_name": s[11],
            "speaker_color_index": s[12],
        }
        for s in segments
    ]

    if analytics:
        a = analytics[0]
        result["analytics"] = {
            "total_duration_seconds": a[3],
            "interruption_count": a[4],
            "speaker_metrics": [
                {
                    "speaker_display_name": m[-2],
                    "speaker_color_index": m[-1],
                    "talk_time_seconds": m[3],
                    "talk_time_pct": m[4],
                    "turn_count": m[5],
                    "avg_turn_length_seconds": m[6],
                    "interruption_count": m[7],
                }
                for m in metrics
            ],
        }
    else:
        result["analytics"] = None

    if summaries:
        s = summaries[0]
        result["summary"] = {
            "overview": s[2],
            "key_points": json.loads(s[3]),
            "decisions": json.loads(s[4]),
            "action_items": json.loads(s[5]),
            "debate_claims": json.loads(s[6]) if s[6] else None,
            "generated_at": s[7],
            "transcript_hash": s[8],
            "model_used": s[9],
        }
    else:
        result["summary"] = None

    return result
