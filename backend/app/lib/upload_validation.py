"""Upload validation module.

Pure functions — validates file type, size, and speaker count hint.
"""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    "wav", "mp3", "m4a", "webm", "ogg",
})

ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3",
    "audio/m4a", "audio/mp4", "audio/x-m4a",
    "audio/webm",
    "audio/ogg", "audio/vorbis",
})


@dataclass(frozen=True)
class ValidationError:
    """Structured validation error."""

    code: str
    message: str


def validate_file_extension(filename: str) -> ValidationError | None:
    """Validate file extension against the allowlist."""
    if not filename or "." not in filename:
        return ValidationError(
            code="UNSUPPORTED_FORMAT",
            message=f"File must have one of these extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return ValidationError(
            code="UNSUPPORTED_FORMAT",
            message=f"'.{ext}' is not supported. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return None


def validate_file_size(size_bytes: int, max_bytes: int) -> ValidationError | None:
    """Validate file size does not exceed the maximum."""
    if size_bytes <= 0:
        return ValidationError(
            code="EMPTY_FILE",
            message="The uploaded file is empty (0 bytes).",
        )
    if size_bytes > max_bytes:
        max_mb = round(max_bytes / (1024 * 1024), 1)
        return ValidationError(
            code="FILE_TOO_LARGE",
            message=f"File exceeds the {max_mb} MB limit.",
        )
    return None


def validate_speaker_count(hint: int | None) -> ValidationError | None:
    """Validate speaker count hint is within 1–10 or None."""
    if hint is None:
        return None
    if not isinstance(hint, int) or hint < 1 or hint > 10:
        return ValidationError(
            code="VALIDATION_ERROR",
            message="Speaker count must be between 1 and 10.",
        )
    return None
