"""End-to-end Phase 1 pipeline test using deterministic service doubles."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.pipeline import run_pipeline


async def test_pipeline_transcribes_and_summarizes_one_uploaded_file(
    db,
    sample_audio_path,
    mock_transcription,
    mock_diarization,
    mock_summarization,
):
    conversation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO conversations
           (id, title, created_at, processing_status, consent_granted_at)
           VALUES (?, ?, ?, 'uploading', ?)""",
        (conversation_id, "Pipeline test", now, now),
    )
    await db.execute(
        """INSERT INTO audio_files
           (id, conversation_id, file_path, original_filename, format, size_bytes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            conversation_id,
            sample_audio_path,
            "test_audio.wav",
            "wav",
            1,
        ),
    )
    await db.commit()

    events = [
        event
        async for event in run_pipeline(
            db=db,
            conversation_id=conversation_id,
            audio_path=sample_audio_path,
            transcription_service=mock_transcription,
            diarization_service=mock_diarization,
            summarization_service=mock_summarization,
        )
    ]

    assert events[-1]["step"] == "complete"
    assert events[-1]["status"] == "done"
    assert [event["step"] for event in events if event["status"] == "done"] == [
        "transcribing",
        "diarizing",
        "analyzing",
        "summarizing",
        "complete",
    ]

    conversation = await db.execute_fetchall(
        "SELECT processing_status, last_completed_step FROM conversations WHERE id = ?",
        (conversation_id,),
    )
    assert tuple(conversation[0]) == ("complete", "summarizing")

    segments = await db.execute_fetchall(
        "SELECT text FROM segments WHERE conversation_id = ? ORDER BY order_index",
        (conversation_id,),
    )
    assert len(segments) == 4
    assert segments[0][0] == "Hello, welcome to the meeting."

    summary = await db.execute_fetchall(
        "SELECT overview FROM summaries WHERE conversation_id = ?",
        (conversation_id,),
    )
    assert summary[0][0]
