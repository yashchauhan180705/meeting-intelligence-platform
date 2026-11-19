# Research: Meeting & Debate Intelligence Platform

**Branch**: `001-meeting-debate-intelligence` | **Date**: 2026-10-13
**Phase**: 0 — Resolve unknowns, establish technical decisions

---

## Decision Log

### D-01: Frontend Framework

**Decision**: Next.js (current stable, v14/App Router) with TypeScript

**Rationale**: Next.js provides file-based routing, built-in API routes if lightweight BFF endpoints are needed, excellent TypeScript support, and a large ecosystem. The App Router enables React Server Components for fast initial loads while still supporting client components for interactive features (audio playback, real-time progress, inline editing).

**Alternatives considered**:
- Vite + React SPA — simpler, but no SSR; no meaningful advantage for a local-only app
- Plain HTML/JS — ruled out; constitution requires world-class UI/UX and a design system

---

### D-02: Icon Set

**Decision**: Lucide React

**Rationale**: Lucide is MIT-licensed, free, ships as tree-shakeable ESM, and provides a consistent, modern, line-icon style. It integrates seamlessly with Next.js/TypeScript via `lucide-react`. Constitution explicitly prohibits emojis as icons.

**Alternatives considered**:
- Heroicons — similar quality but smaller set
- Phosphor Icons — good but larger bundle if not tree-shaken carefully

---

### D-03: Styling

**Decision**: Vanilla CSS with CSS custom properties (design tokens), augmented by CSS Modules for component scoping. `next-themes` for light/dark mode.

**Rationale**: Constitution mandates Vanilla CSS. CSS custom properties (variables) serve as the design token layer. CSS Modules ensure zero class-name collisions. `next-themes` provides SSR-safe theme switching with no flash of unstyled content.

**Alternatives considered**:
- CSS-in-JS — ruled out; constitution says Vanilla CSS
- Tailwind — ruled out; constitution says Vanilla CSS

---

### D-04: Audio Processing Backend

**Decision**: Python 3.11+ with FastAPI

**Rationale**: FastAPI is free, open-source, production-quality, and provides async support with minimal boilerplate. It integrates cleanly with Python's AI ecosystem (faster-whisper, pyannote.audio). Background job processing uses FastAPI's `BackgroundTasks` plus `asyncio` for non-blocking processing.

**Alternatives considered**:
- Flask — synchronous by default, less suited for streaming progress
- Django — too heavy for a standalone audio API service

---

### D-05: Transcription

**Decision**: `faster-whisper` (open-source, CPU-compatible)

**Rationale**: `faster-whisper` is a CTranslate2-based reimplementation of OpenAI Whisper that runs 4× faster on CPU with lower memory usage. It is fully free, runs locally, and supports English, Hindi, Gujarati, and code-mixed speech. No API key or internet required after model download.

**Key integration notes**:
- Model size: `small` or `medium` recommended for quality/speed balance on a normal laptop
- Output: word-level timestamps, language detection per segment
- Language hint can be passed to improve accuracy when the user selects a language

**Alternatives considered**:
- OpenAI Whisper (original) — slower on CPU; faster-whisper is a strict improvement
- Google Speech-to-Text API — paid after free tier; violates zero-cost constraint

---

### D-06: Speaker Diarization

**Decision**: `pyannote.audio` (free with a Hugging Face token)

**Rationale**: `pyannote.audio` is the leading open-source speaker diarization library. It requires accepting gated model terms on Hugging Face (free) and passing a HF token. The `num_speakers` parameter can be passed when the user provides a speaker count hint, improving accuracy.

**Key integration notes**:
- HF token stored as an environment variable (`HUGGINGFACE_TOKEN`), never hardcoded
- `num_speakers` (1–10) passed when provided; omitted when "unknown"
- Outputs speaker segments with start/end times that are then merged with Whisper transcript segments
- CPU inference is supported but slower; Google Colab GPU is the optional fallback

**Alternatives considered**:
- SpeechBrain — good but more complex setup; pyannote has better out-of-box accuracy
- Resemblyzer — speaker embedding only, not a full diarization pipeline

---

### D-07: Transcript–Speaker Merging

**Decision**: Custom `transcript_merger` library module using interval overlap heuristics

**Rationale**: Whisper produces timestamped text segments; pyannote produces speaker-labelled time intervals. A dedicated merging module assigns each Whisper segment to the speaker with the maximum time overlap. This is a pure function (no side effects) and is independently testable with fixture data.

**Key integration notes**:
- Ties broken by largest overlap fraction
- Segments with no diarization match marked as "unknown speaker" with a low-confidence flag
- Module interface: `merge(segments: list[TranscriptSegment], diarization: list[SpeakerInterval]) -> list[LabelledSegment]`

---

### D-08: AI Summarization

**Decision**: Gemini API (Google AI Studio free tier) via a `SummarizationService` interface

**Rationale**: Gemini 1.5 Flash is available for free on Google AI Studio with a generous rate limit (15 RPM, 1 million tokens/day as of 2025). The `GOOGLE_API_KEY` is stored as an environment variable. The service is wrapped behind a `SummarizationService` abstract interface so tests use a `MockSummarizationService` and the model can be swapped without changing business logic.

**Key integration notes**:
- API key: `GOOGLE_API_KEY` env var; never committed
- Prompt includes the full transcript with speaker names, and a mode parameter ("meeting" or "debate")
- Rate-limit errors (429) are caught and returned to the frontend with a `RATE_LIMITED` status
- Full service unavailability (network error, 5xx) is caught and returned as `SERVICE_UNAVAILABLE`

**Alternatives considered**:
- OpenAI GPT-4o mini — requires credit card; violates zero-cost constraint
- Groq API (LLaMA) — free tier available but less stable; Gemini preferred for reliability
- Local LLM (Ollama) — viable fallback; can be added later by implementing the interface

---

### D-09: Database

**Decision**: SQLite via Python's built-in `sqlite3` module (or `aiosqlite` for async)

**Rationale**: SQLite is free, zero-dependency, runs entirely on disk, and is perfectly suited for single-user local data. No server, no config, no migration tooling required beyond SQL DDL files. Audio files stored on local disk as flat files referenced by path in the database.

**Schema overview**: See `data-model.md`

**Alternatives considered**:
- PostgreSQL — overkill for a single-user local app; contradicts Simplicity principle
- IndexedDB (client-side) — cannot be accessed by the Python service for audio processing

---

### D-10: Visualization

**Decision**: Recharts for analytics charts; custom CSS-based speaker timeline

**Rationale**: Recharts is free, MIT-licensed, React-native, and TypeScript-friendly. It covers bar charts (talk-time) and simple line charts out of the box. The speaker timeline (per-speaker lanes with interval blocks) is better implemented as a custom CSS component for precise pixel control over the audio-sync interaction.

**Alternatives considered**:
- Plotly — heavier bundle; more suited for scientific charts
- D3.js — powerful but low-level; Recharts wraps D3 with a simpler API

---

### D-11: Audio Playback & Sync

**Decision**: Browser native `<audio>` element with the Web Audio API for progress tracking; React state drives transcript highlight and timeline cursor.

**Rationale**: No external dependency needed. The `timeupdate` event fires as audio plays; the frontend maps current time to the active transcript segment and scrolls it into view. Clicking a segment or timeline block sets `audio.currentTime`.

---

### D-12: Background Job Processing

**Decision**: FastAPI `BackgroundTasks` with Server-Sent Events (SSE) for progress reporting

**Rationale**: SSE is natively supported in modern browsers, requires no WebSocket infrastructure, and works perfectly for one-way server→client progress updates. Each pipeline step (Uploading, Transcribing, Diarizing, Analyzing, Summarizing) emits an SSE event with `{ step, status, progress_pct }`. Long audio is processed in configurable chunks to respect free-tier token limits for summarization.

**Alternatives considered**:
- WebSockets — bidirectional; overkill for one-way progress
- Polling — simpler but chatty; SSE is strictly better

---

### D-13: Testing Strategy

**Decision**:
- **Python**: `pytest` + `pytest-asyncio` for unit and integration tests. Fixture audio files: short (3–10 s) WAV files checked into `tests/fixtures/`. `MockSummarizationService` for all AI tests.
- **Frontend**: `Playwright` for E2E and UI tests. `@testing-library/react` + `jest` (via Next.js default config) for component unit tests.
- **Fixture strategy**: pyannote diarization mocked via a fixture RTTM file; faster-whisper mocked via a fixture JSON transcript; real audio only in integration tests.

---

### D-14: Google Colab Fallback

**Decision**: Document a `colab_runner.ipynb` notebook that installs the Python service dependencies and exposes the FastAPI server via `ngrok` free tier. The Next.js frontend's `NEXT_PUBLIC_API_URL` env var is set to the ngrok URL.

**Rationale**: Heavy CPU inference (pyannote on long audio) can be slow on low-end laptops. Colab provides a free GPU/CPU runtime. Setup is one-click; no code changes needed in the service.

---

### D-15: Privacy Implementation

**Decision**: Three concrete mechanisms aligned with constitution principle VII:
1. **Consent notice**: A modal displayed before recording or processing begins, explaining what data is stored locally and what is sent to Gemini. User must click "I consent" before any action proceeds.
2. **Local-only storage**: All audio files and transcripts stored on the local filesystem / SQLite; nothing persisted to external servers except the transcript text sent to Gemini for summarization.
3. **Full delete**: The "Delete conversation" action removes the SQLite rows AND the audio file from disk in a single atomic operation. A confirmation dialog warns the user that the action is irreversible.

---

## Resolved Unknowns Summary

| # | Unknown | Resolution |
|---|---------|------------|
| 1 | Frontend framework | Next.js + TypeScript + CSS Modules + `next-themes` |
| 2 | Icon set | Lucide React |
| 3 | Transcription | faster-whisper (local CPU) |
| 4 | Diarization | pyannote.audio (HF free token) |
| 5 | Merging strategy | Custom `transcript_merger` module (overlap heuristic) |
| 6 | Summarization | Gemini 1.5 Flash via `SummarizationService` interface |
| 7 | Database | SQLite (`aiosqlite`) + local disk for audio |
| 8 | Charts | Recharts for analytics; custom CSS for timeline |
| 9 | Progress reporting | SSE (Server-Sent Events) from FastAPI |
| 10 | Testing | pytest + Playwright + fixture audio files + mocked AI |
| 11 | Colab fallback | `colab_runner.ipynb` + ngrok |
| 12 | Privacy | Consent modal + local storage + atomic delete |
