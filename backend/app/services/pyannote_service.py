"""PyannoteService — pyannote.audio adapter implementing DiarizationService."""

from __future__ import annotations

import logging

from app.models import SpeakerInterval

logger = logging.getLogger(__name__)


class PyannoteService:
    """Speaker diarization using pyannote.audio.

    Implements the DiarizationService protocol.
    Requires a Hugging Face token with access to the gated model.
    """

    def __init__(self, hf_token: str) -> None:
        self._hf_token = hf_token
        self._pipeline = None  # lazy-loaded

    def _load_pipeline(self):
        """Lazy-load the pyannote pipeline on first use."""
        if self._pipeline is None:
            from pyannote.audio import Pipeline

            logger.info("Loading pyannote speaker-diarization pipeline...")
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self._hf_token,
            )
            logger.info("Pipeline loaded.")

    def diarize(
        self,
        audio_path: str,
        num_speakers: int | None = None,
    ) -> list[SpeakerInterval]:
        """Run speaker diarization and return speaker intervals."""
        self._load_pipeline()
        assert self._pipeline is not None

        kwargs: dict = {}
        if num_speakers is not None:
            kwargs["num_speakers"] = num_speakers

        import torch
        import torchaudio

        waveform, sr = torchaudio.load(audio_path)
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            waveform = resampler(waveform)
            sr = 16000
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        diarization = self._pipeline({"waveform": waveform, "sample_rate": sr}, **kwargs)

        result: list[SpeakerInterval] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            result.append(
                SpeakerInterval(
                    speaker_label=speaker,
                    start=round(turn.start, 3),
                    end=round(turn.end, 3),
                )
            )

        return result
