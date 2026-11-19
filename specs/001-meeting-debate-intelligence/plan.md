# Implementation Plan: Meeting & Debate Intelligence Platform

**Branch**: `001-meeting-debate-intelligence` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-meeting-debate-intelligence/spec.md`

---

## Summary

Build a browser-based platform that records or ingests audio, runs it through a local Python pipeline (faster-whisper transcription → pyannote diarization → analytics computation → Gemini summarization), and presents the results as a speaker-separated, interactive transcript with timeline visualization, analytics charts, and an AI summary — all stored locally in SQLite with full delete support.

---

## Technical Context

**Frontend Language/Version**: TypeScript 5.x, Node.js 20 LTS, Next.js 14 (App Router)

**Backend Language/Version**: Python 3.11+

**Primary Dependencies**:
- Frontend: `next`, `react`, `lucide-react`, `recharts`, `next-themes`
- Backend: `fastapi`, `uvicorn`, `faster-whisper`, `pyannote.audio`, `google-generativeai`, `aiosqlite`, `python-multipart`, `python-dotenv`

**Storage**: SQLite (via `aiosqlite`) for structured data; local disk for audio files

**Testing**:
- Backend: `pytest`, `pytest-asyncio`
- Frontend unit: `jest`, `@testing-library/react`
- E2E: `playwright`

**Target Platform**: Local laptop (Windows/macOS/Linux); Google Colab as optional GPU fallback

**Project Type**: Web application (Next.js frontend + FastAPI backend as separate processes)

**Performance Goals**:
- 10-minute, 2–4 speaker audio processes end-to-end without blocking the UI (SC-001, SC-005)
- Speaker rename propagates to all views within 1 second (SC-002)
- UI responsive at all screen widths 360 px–1920 px (SC-009)

**Constraints**:
- Zero-cost only — no paid APIs, no credit cards (constitution II)
- All AI calls wrapped behind interfaces for mockability (constitution IV)
- Audio and transcripts stored locally; data sent to Gemini only for summarization, with user consent (constitution VII)
- Maximum 10 speakers per conversation (spec FR-004, clarification Q2)

**Scale/Scope**: Single user, local machine, ~25 MB max audio upload

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|---------|
| I. Professional Product Quality | ✅ | TypeScript + Python with strict types; modular architecture |
| II. Zero-Cost Constraint | ✅ | faster-whisper (local), pyannote (free HF token), Gemini free tier, SQLite; no paid services |
| III. Library-First Architecture | ✅ | Six standalone library modules: `transcription`, `diarization`, `transcript_merger`, `analytics`, `summarization`, `speaker_renaming` |
| IV. TDD by Default | ✅ | pytest for Python modules; fixture WAV files; `MockSummarizationService`; Playwright E2E |
| V. Automation at Every Level | ✅ | Unit, integration, E2E test suites; Playwright smoke tests for critical journeys |
| VI. Functional Programming Preference | ✅ | `transcript_merger`, `analytics`, `speaker_renaming` are pure functions; side effects isolated in service adapters |
| VII. Privacy and Consent by Design | ✅ | Consent modal before any processing; local SQLite + disk storage; atomic delete (FR-020); Gemini disclosure in consent |
| VIII. Honest AI Output | ✅ | Low-confidence flag on segments (FR-012); "Regenerate Summary" explicit trigger; no certainty claims in UI |
| IX. World-Class UI/UX | ✅ | Next.js + CSS Modules + Lucide icons; light/dark via `next-themes`; Recharts for analytics; no emoji icons |
| X. Security and Performance by Design | ✅ | MIME type + size validation (FR-005); SSE for non-blocking progress (FR-023); input sanitization before DB writes |
| XI. AI-Assisted Development | ✅ | Same architecture, testing, and quality standards apply regardless of code origin |
| XII. Simplicity and Maintainability | ✅ | No ORM; plain SQL via `aiosqlite`; CSS Modules over CSS-in-JS; no unnecessary abstractions |

**Gate Result: PASS** — No violations. Complexity Tracking table not required.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-meeting-debate-intelligence/
├── plan.md              ← This file
├── research.md          ← Phase 0 output (15 technical decisions)
├── data-model.md        ← Phase 1 output (SQLite schema + type definitions)
├── contracts/
│   └── api.md           ← Phase 1 output (REST API + library interfaces)
├── quickstart.md        ← Phase 1 output (setup + 10 validation scenarios)
└── tasks.md             ← Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
my-antigravity-app/
│
├── frontend/                          # Next.js application
│   ├── src/
│   │   ├── app/                       # App Router
│   │   │   ├── layout.tsx             # Root layout + ThemeProvider
│   │   │   ├── page.tsx               # Landing: upload / record
│   │   │   ├── conversations/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx       # Results: Transcript / Analytics / Summary tabs
│   │   │   └── history/
│   │   │       └── page.tsx           # Conversation history list
│   │   ├── components/
│   │   │   ├── consent/               # ConsentModal component
│   │   │   ├── audio/                 # AudioRecorder, AudioPlayer
│   │   │   ├── upload/                # FileUpload with validation
│   │   │   ├── pipeline/              # PipelineProgress (SSE consumer)
│   │   │   ├── transcript/            # TranscriptPanel, SegmentRow (editable)
│   │   │   ├── timeline/              # SpeakerTimeline (custom CSS)
│   │   │   ├── analytics/             # TalkTimeChart, TurnMetricsTable (Recharts)
│   │   │   ├── summary/               # SummaryPanel, RegenerateSummaryButton
│   │   │   ├── speaker/               # SpeakerLabel (renaming UI)
│   │   │   └── shared/                # Button, Icon, Badge, Tabs, Modal, Banner
│   │   ├── lib/                       # Frontend library modules (pure / typed)
│   │   │   ├── api-client.ts          # Typed fetch wrapper for all backend endpoints
│   │   │   ├── audio-sync.ts          # timeupdate → segment highlight logic
│   │   │   ├── speaker-rename.ts      # Client-side name substitution in summary text
│   │   │   └── transcript-hash.ts     # SHA-256 of transcript for staleness detection
│   │   ├── hooks/                     # useConversation, useSpeakers, useSSEProgress
│   │   └── styles/
│   │       ├── tokens.css             # Design tokens (colors, spacing, typography)
│   │       ├── global.css             # Reset + base styles
│   │       └── themes.css             # Light / dark mode token overrides
│   ├── tests/
│   │   ├── e2e/                       # Playwright specs (smoke, rename, delete)
│   │   └── unit/                      # Jest + Testing Library component tests
│   ├── .env.local                     # NEXT_PUBLIC_API_URL
│   └── package.json
│
├── backend/                           # FastAPI audio processing service
│   ├── app/
│   │   ├── main.py                    # FastAPI app + CORS + lifespan (DB init)
│   │   ├── routers/
│   │   │   ├── conversations.py       # All /conversations/* endpoints
│   │   │   └── audio.py               # Audio streaming endpoint
│   │   ├── lib/                       # Library modules — pure functions
│   │   │   ├── transcription.py       # TranscriptSegment dataclass + Protocol
│   │   │   ├── diarization.py         # SpeakerInterval dataclass + Protocol
│   │   │   ├── transcript_merger.py   # merge() pure function
│   │   │   ├── analytics.py           # compute_analytics() pure function
│   │   │   ├── summarization.py       # SummarizationService Protocol + dataclasses
│   │   │   └── speaker_renaming.py    # apply_rename() pure function
│   │   ├── services/                  # I/O adapters implementing lib Protocols
│   │   │   ├── whisper_service.py     # faster-whisper adapter
│   │   │   ├── pyannote_service.py    # pyannote.audio adapter
│   │   │   └── gemini_service.py      # Gemini API adapter
│   │   ├── pipeline.py                # Orchestrates Uploading→…→Complete; emits SSE events
│   │   ├── database.py                # aiosqlite pool + schema DDL
│   │   └── models.py                  # Python dataclasses matching data-model.md
│   ├── tests/
│   │   ├── fixtures/
│   │   │   ├── two_speakers_10s.wav   # Short fixture audio
│   │   │   ├── transcript_fixture.json
│   │   │   └── diarization_fixture.rttm
│   │   ├── unit/
│   │   │   ├── test_transcript_merger.py
│   │   │   ├── test_analytics.py
│   │   │   └── test_speaker_renaming.py
│   │   └── integration/
│   │       ├── test_pipeline.py       # Uses fixture files + MockSummarizationService
│   │       └── test_api.py            # FastAPI TestClient against real DB
│   ├── .env                           # HUGGINGFACE_TOKEN, GOOGLE_API_KEY, …
│   └── requirements.txt
│
└── colab_runner.ipynb                 # Google Colab GPU fallback runner
```

**Structure Decision**: Option 2 (Web Application) — separate `frontend/` and `backend/` directories. They are independent processes communicating over HTTP. This separation is required because the backend uses Python AI libraries that cannot run in the browser and because FastAPI must manage long-running background jobs independently of the Next.js dev server.

---

## Complexity Tracking

No constitution violations — table not required.

---

## Phase Outputs

| Phase | Artifact | Status |
|-------|----------|--------|
| 0 | `research.md` | ✅ Complete |
| 1 | `data-model.md` | ✅ Complete |
| 1 | `contracts/api.md` | ✅ Complete |
| 1 | `quickstart.md` | ✅ Complete |
| 2 | `tasks.md` | ⏳ Run `/speckit-tasks` |
