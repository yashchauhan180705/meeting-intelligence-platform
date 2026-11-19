"""WhisperService — faster-whisper adapter implementing TranscriptionService."""

from __future__ import annotations

import logging

from app.models import TranscriptSegment

logger = logging.getLogger(__name__)


class WhisperService:
    """Transcription using faster-whisper (CTranslate2).

    Implements the TranscriptionService protocol.
    """

    def __init__(self, model_size: str = "small") -> None:
        self._model_size = model_size
        self._model = None  # lazy-loaded

    def _load_model(self):
        """Lazy-load the Whisper model on first use."""
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info("Loading faster-whisper model '%s'...", self._model_size)
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info("Model loaded.")

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> list[TranscriptSegment]:
        """Transcribe audio file and return timestamped segments."""
        self._load_model()
        assert self._model is not None

        kwargs: dict = {"beam_size": 5, "word_timestamps": True}
        if language:
            kwargs["language"] = language

        segments_gen, info = self._model.transcribe(audio_path, **kwargs)
        logger.info(
            "Detected language: %s (prob %.2f)",
            info.language,
            info.language_probability,
        )

        result: list[TranscriptSegment] = []
        for seg in segments_gen:
            result.append(
                TranscriptSegment(
                    start=round(seg.start, 3),
                    end=round(seg.end, 3),
                    text=seg.text.strip(),
                    confidence=round(seg.avg_logprob, 4) if seg.avg_logprob else None,
                    language=info.language,
                )
            )

        return result
