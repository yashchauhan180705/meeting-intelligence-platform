"""GeminiService — Google Gemini API adapter implementing SummarizationService."""

from __future__ import annotations

import json
import logging
from typing import Literal

from app.lib.summarization import RateLimitError, ServiceUnavailableError
from app.models import ConversationSummary, LabelledSegment

logger = logging.getLogger(__name__)

_MEETING_PROMPT = """You are an expert meeting analyst. Summarize the following conversation transcript.

Return a JSON object with these exact keys:
- "overview": A concise paragraph summarizing the conversation.
- "key_points": An array of the most important points discussed.
- "decisions": An array of decisions made during the conversation.
- "action_items": An array of objects with "text" (description) and "owner" (speaker name or null).

Transcript:
{transcript}

Return ONLY valid JSON, no markdown fences."""

_DEBATE_PROMPT = """You are an expert debate analyst. Summarize the following debate transcript.

Return a JSON object with these exact keys:
- "overview": A concise paragraph summarizing the debate.
- "key_points": An array of the most important arguments made.
- "decisions": An array of conclusions or resolutions reached.
- "action_items": An array of objects with "text" (description) and "owner" (speaker name or null).
- "debate_claims": An array of objects with "speaker" (name) and "claim" (the key argument).

Transcript:
{transcript}

Return ONLY valid JSON, no markdown fences."""


class GeminiService:
    """Conversation summarization via Google Gemini API.

    Implements the SummarizationService protocol.
    """

    FALLBACK_MODELS = [
        "gemini-flash-latest",
        "gemini-1.5-flash",
        "gemini-2.5-flash",
        "gemini-1.5-pro",
        "gemini-pro-latest",
    ]

    def __init__(self, api_key: str, model_name: str = "gemini-flash-latest") -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._model = None

    def _get_model(self, model_name: str | None = None):
        import google.generativeai as genai

        target_model = model_name or self._model_name
        genai.configure(api_key=self._api_key)
        return genai.GenerativeModel(target_model)

    def _build_transcript_text(
        self,
        segments: list[LabelledSegment],
        speaker_names: dict[str, str],
    ) -> str:
        lines: list[str] = []
        for seg in segments:
            name = speaker_names.get(seg.speaker_label, seg.speaker_label)
            lines.append(f"[{name}]: {seg.segment.text}")
        return "\n".join(lines)

    def summarize(
        self,
        segments: list[LabelledSegment],
        speaker_names: dict[str, str],
        mode: Literal["meeting", "debate"],
    ) -> ConversationSummary:
        """Generate a summary using Gemini API with automatic retry on rate limit."""
        import time

        transcript = self._build_transcript_text(segments, speaker_names)
        prompt_template = _DEBATE_PROMPT if mode == "debate" else _MEETING_PROMPT
        prompt = prompt_template.format(transcript=transcript)

        models_to_try = [self._model_name] + [m for m in self.FALLBACK_MODELS if m != self._model_name]
        last_exception = None

        for model_name in models_to_try:
            try:
                model = self._get_model(model_name)
                response = model.generate_content(prompt)
                raw = response.text.strip()

                # Strip markdown fences if present
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                    if raw.endswith("```"):
                        raw = raw[:-3].strip()
                    if raw.startswith("json"):
                        raw = raw[4:].strip()

                data = json.loads(raw)
                self._model_name = model_name  # Remember working model

                return ConversationSummary(
                    overview=data.get("overview", ""),
                    key_points=data.get("key_points", []),
                    decisions=data.get("decisions", []),
                    action_items=data.get("action_items", []),
                    debate_claims=data.get("debate_claims"),
                )

            except Exception as exc:
                exc_str = str(exc).lower()
                last_exception = exc

                # If 404/not found/deprecated, try next model in the fallback list immediately
                if "404" in exc_str or "not found" in exc_str or "not supported" in exc_str or "no longer available" in exc_str:
                    logger.warning("Model %s unavailable, trying next candidate...", model_name)
                    continue

                is_rate_limit = "429" in exc_str or "rate" in exc_str or "resource_exhausted" in exc_str
                if is_rate_limit:
                    raise RateLimitError(retry_after_seconds=60) from exc

                is_server_error = "500" in exc_str or "503" in exc_str or "unavailable" in exc_str
                if is_server_error:
                    raise ServiceUnavailableError(str(exc)) from exc

                logger.warning("Gemini model %s encountered error: %s", model_name, exc)

        raise ServiceUnavailableError(f"Gemini summarization failed: {last_exception}") from last_exception
