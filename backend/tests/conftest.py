"""Shared pytest fixtures for database and mock services."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from app.database import init_db, get_db
from tests.fixtures.mock_services import (
    MockDiarizationService,
    MockSummarizationService,
    MockTranscriptionService,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_path(tmp_path):
    """Create a temporary database for each test."""
    path = tmp_path / "test.db"
    await init_db(path)
    return path


@pytest_asyncio.fixture
async def db(db_path):
    """Provide an open database connection for each test."""
    conn = await get_db(db_path)
    yield conn
    await conn.close()


@pytest.fixture
def mock_transcription():
    """Provide a mock transcription service."""
    return MockTranscriptionService()


@pytest.fixture
def mock_diarization():
    """Provide a mock diarization service."""
    return MockDiarizationService()


@pytest.fixture
def mock_summarization():
    """Provide a mock summarization service."""
    return MockSummarizationService()


@pytest.fixture
def sample_audio_path(tmp_path) -> str:
    """Create a minimal valid WAV file for testing."""
    import struct

    # Generate a minimal 1-second mono WAV at 8000 Hz
    sample_rate = 8000
    num_samples = sample_rate  # 1 second
    samples = bytes(num_samples * 2)  # 16-bit silence

    wav_path = tmp_path / "test_audio.wav"
    with open(wav_path, "wb") as f:
        # RIFF header
        data_size = len(samples)
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))   # PCM
        f.write(struct.pack("<H", 1))   # mono
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))  # byte rate
        f.write(struct.pack("<H", 2))   # block align
        f.write(struct.pack("<H", 16))  # bits per sample
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(samples)

    return str(wav_path)
