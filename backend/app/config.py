"""Configuration module — loads .env and exposes typed config values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend root directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    huggingface_token: str
    google_api_key: str
    audio_storage_path: Path
    max_upload_bytes: int
    low_confidence_threshold: float
    whisper_model_size: str
    allowed_origins: list[str]


def load_settings() -> Settings:
    """Read environment variables and return a frozen Settings instance."""
    return Settings(
        huggingface_token=os.getenv("HUGGINGFACE_TOKEN", ""),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        audio_storage_path=Path(
            os.getenv("AUDIO_STORAGE_PATH", "./audio_files")
        ),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", "26214400")),
        low_confidence_threshold=float(
            os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.5")
        ),
        whisper_model_size=os.getenv("WHISPER_MODEL_SIZE", "small"),
        allowed_origins=os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:3000"
        ).split(","),
    )
