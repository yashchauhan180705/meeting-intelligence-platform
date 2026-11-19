"""Audio streaming endpoint with range support for seeking."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audio"])


@router.get("/conversations/{conversation_id}/audio")
async def stream_audio(conversation_id: str, request: Request):
    """Stream audio file with Content-Range support for seeking."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT file_path, format FROM audio_files WHERE conversation_id = ?",
            (conversation_id,),
        )
        if not rows:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Audio file not found"})

        file_path = Path(rows[0][0])
        file_format = rows[0][1]
    finally:
        await db.close()

    if not file_path.exists():
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Audio file missing from disk"})

    media_types = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
        "ogg": "audio/ogg",
    }
    media_type = media_types.get(file_format, "application/octet-stream")

    # Use FileResponse for simple serving; supports Range headers natively
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )
