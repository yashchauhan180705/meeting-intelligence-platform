"""Integration tests for API endpoints — T023.

Tests POST /conversations with various inputs using httpx + TestClient.
"""

from __future__ import annotations

import io
import struct

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import init_db
from app.main import app


def _make_wav_bytes(duration_seconds: float = 1.0) -> bytes:
    """Generate minimal WAV file bytes."""
    sample_rate = 8000
    num_samples = int(sample_rate * duration_seconds)
    samples = bytes(num_samples * 2)

    buf = io.BytesIO()
    data_size = len(samples)
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 1))  # PCM
    buf.write(struct.pack("<H", 1))  # mono
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * 2))
    buf.write(struct.pack("<H", 2))
    buf.write(struct.pack("<H", 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(samples)
    return buf.getvalue()


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Provide an async test client with a temporary database."""
    import os
    from pathlib import Path

    db_path = tmp_path / "test.db"
    audio_path = tmp_path / "audio_files"
    audio_path.mkdir()

    # Override the module-level DB path so get_db() uses the temp DB
    import app.database as db_mod
    monkeypatch.setattr(db_mod, "_DB_PATH", db_path)

    await init_db(db_path)

    from tests.fixtures.mock_services import (
        MockTranscriptionService,
        MockDiarizationService,
        MockSummarizationService,
    )
    from app.config import Settings
    from app.routers.conversations import configure

    settings = Settings(
        huggingface_token="",
        google_api_key="",
        audio_storage_path=audio_path,
        max_upload_bytes=26214400,
        low_confidence_threshold=0.5,
        whisper_model_size="small",
        allowed_origins=["http://localhost:3000"],
    )
    configure(settings, MockTranscriptionService(), MockDiarizationService(), MockSummarizationService())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestCreateConversation:
    """POST /conversations tests."""

    @pytest.mark.asyncio
    async def test_successful_upload_wav(self, client):
        wav = _make_wav_bytes()
        response = await client.post(
            "/conversations",
            files={"audio_file": ("test.wav", wav, "audio/wav")},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["processing_status"] == "uploading"

    @pytest.mark.asyncio
    async def test_unsupported_format(self, client):
        response = await client.post(
            "/conversations",
            files={"audio_file": ("test.txt", b"not audio", "text/plain")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "UNSUPPORTED_FORMAT"

    @pytest.mark.asyncio
    async def test_empty_file_rejected(self, client):
        response = await client.post(
            "/conversations",
            files={"audio_file": ("test.wav", b"", "audio/wav")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "EMPTY_FILE"

    @pytest.mark.asyncio
    async def test_with_speaker_count(self, client):
        wav = _make_wav_bytes()
        response = await client.post(
            "/conversations",
            files={"audio_file": ("test.wav", wav, "audio/wav")},
            data={"speaker_count_hint": "3"},
        )
        assert response.status_code == 201
        assert response.json()["speaker_count_hint"] == 3

    @pytest.mark.asyncio
    async def test_invalid_speaker_count(self, client):
        wav = _make_wav_bytes()
        response = await client.post(
            "/conversations",
            files={"audio_file": ("test.wav", wav, "audio/wav")},
            data={"speaker_count_hint": "15"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_upload_process_and_read_results(self, client):
        wav = _make_wav_bytes()
        upload = await client.post(
            "/conversations",
            files={"audio_file": ("test.wav", wav, "audio/wav")},
        )
        assert upload.status_code == 201
        conversation_id = upload.json()["id"]

        process = await client.post(f"/conversations/{conversation_id}/process")
        assert process.status_code == 202

        result = await client.get(f"/conversations/{conversation_id}")
        assert result.status_code == 200
        data = result.json()
        assert data["processing_status"] == "complete"
        assert len(data["segments"]) == 4
        assert [speaker["system_label"] for speaker in data["speakers"]] == [
            "SPEAKER_00",
            "SPEAKER_01",
        ]
        assert [speaker["color_index"] for speaker in data["speakers"]] == [0, 1]
        assert all(
            segment["speaker_display_name"] in {"SPEAKER_00", "SPEAKER_01"}
            for segment in data["segments"]
        )
        assert all(not segment["is_low_confidence"] for segment in data["segments"])
        assert data["summary"]["overview"]

        first_speaker = data["speakers"][0]
        rename = await client.patch(
            f"/conversations/{conversation_id}/speakers/{first_speaker['id']}",
            json={"display_name": "Rahul"},
        )
        assert rename.status_code == 200
        assert rename.json()["display_name"] == "Rahul"

        first_segment = data["segments"][0]
        update = await client.patch(
            f"/conversations/{conversation_id}/segments/{first_segment['id']}",
            json={
                "text": "Corrected greeting.",
                "speaker_id": data["speakers"][1]["id"],
            },
        )
        assert update.status_code == 200
        assert update.json()["text"] == "Corrected greeting."
        assert update.json()["speaker_id"] == data["speakers"][1]["id"]

        refreshed = (await client.get(f"/conversations/{conversation_id}")).json()
        corrected = next(
            segment for segment in refreshed["segments"]
            if segment["id"] == first_segment["id"]
        )
        assert corrected["text"] == "Corrected greeting."
        assert corrected["speaker_display_name"] == data["speakers"][1]["display_name"]

    @pytest.mark.asyncio
    async def test_segment_cannot_be_assigned_to_foreign_speaker(self, client):
        first_upload = await client.post(
            "/conversations",
            files={"audio_file": ("first.wav", _make_wav_bytes(), "audio/wav")},
        )
        second_upload = await client.post(
            "/conversations",
            files={"audio_file": ("second.wav", _make_wav_bytes(), "audio/wav")},
        )
        first_id = first_upload.json()["id"]
        second_id = second_upload.json()["id"]
        await client.post(f"/conversations/{first_id}/process")
        await client.post(f"/conversations/{second_id}/process")
        first = (await client.get(f"/conversations/{first_id}")).json()
        second = (await client.get(f"/conversations/{second_id}")).json()

        response = await client.patch(
            f"/conversations/{first_id}/segments/{first['segments'][0]['id']}",
            json={"speaker_id": second["speakers"][0]["id"]},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_history_and_exports(self, client):
        upload = await client.post(
            "/conversations",
            files={"audio_file": ("history.wav", _make_wav_bytes(), "audio/wav")},
        )
        conversation_id = upload.json()["id"]
        await client.post(f"/conversations/{conversation_id}/process")

        history = await client.get("/conversations")
        assert history.status_code == 200
        assert any(item["id"] == conversation_id for item in history.json()["items"])

        text_export = await client.get(
            f"/conversations/{conversation_id}/export?format=text"
        )
        assert text_export.status_code == 200
        assert "# Conversation" in text_export.text
        assert "## Transcript" in text_export.text

        json_export = await client.get(
            f"/conversations/{conversation_id}/export?format=json"
        )
        assert json_export.status_code == 200
        assert json_export.json()["id"] == conversation_id

        deleted = await client.delete(f"/conversations/{conversation_id}")
        assert deleted.status_code == 204
        assert (await client.get(f"/conversations/{conversation_id}")).status_code == 404


class TestHealthEndpoint:
    """GET /health tests."""

    @pytest.mark.asyncio
    async def test_health_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
