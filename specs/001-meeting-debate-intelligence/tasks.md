# Tasks: Meeting & Debate Intelligence Platform

**Feature**: Meeting & Debate Intelligence Platform
**Branch**: `001-meeting-debate-intelligence`
**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)
**Date**: 2026-10-13

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize both projects, install dependencies, configure tooling

- [ ] T001 Create repository root structure with `frontend/` and `backend/` directories per plan.md project structure
- [ ] T002 [P] Initialize Next.js 14 project with TypeScript in `frontend/` using `npx create-next-app@latest` with App Router enabled
- [ ] T003 [P] Initialize Python 3.11 project in `backend/` with `python -m venv .venv` and create `backend/requirements.txt` with: `fastapi`, `uvicorn[standard]`, `faster-whisper`, `pyannote.audio`, `google-generativeai`, `aiosqlite`, `python-multipart`, `python-dotenv`, `pytest`, `pytest-asyncio`, `httpx`
- [ ] T004 [P] Install frontend dependencies: `lucide-react`, `recharts`, `next-themes` in `frontend/`
- [ ] T005 [P] Create `frontend/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000`
- [ ] T006 [P] Create `backend/.env` with `HUGGINGFACE_TOKEN`, `GOOGLE_API_KEY`, `AUDIO_STORAGE_PATH=./audio_files`, `MAX_UPLOAD_BYTES=26214400`, `LOW_CONFIDENCE_THRESHOLD=0.5`, `WHISPER_MODEL_SIZE=small`
- [ ] T007 [P] Configure ESLint and Prettier for `frontend/`
- [ ] T008 [P] Configure `pytest` with `pytest.ini` or `pyproject.toml` in `backend/`, set `tests/` as the test directory
- [ ] T009 [P] Install Playwright in `frontend/` with `npx playwright install` and create `playwright.config.ts`
- [ ] T010 [P] Create `backend/tests/fixtures/` directory and add a short 10-second, 2-speaker WAV fixture file `two_speakers_10s.wav`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can begin

**⚠ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T011 Create SQLite database module in `backend/app/database.py` — implement `async init_db()` that creates all tables from data-model.md schema: `conversations` (id TEXT PK, title TEXT NOT NULL, created_at TEXT NOT NULL, duration_seconds REAL NULL, speaker_count_hint INTEGER NULL CHECK(speaker_count_hint BETWEEN 1 AND 10), processing_status TEXT NOT NULL DEFAULT 'uploading', is_debate INTEGER NOT NULL DEFAULT 0, consent_granted_at TEXT NOT NULL, last_completed_step TEXT NULL, error_message TEXT NULL), `audio_files`, `speakers` (color_index INTEGER NOT NULL CHECK(color_index BETWEEN 0 AND 9)), `segments` (end_time > start_time), `analytics`, `speaker_metrics`, `summaries` (transcript_hash TEXT NOT NULL). Include `ON DELETE CASCADE` on all foreign keys. Create indexes: `idx_segments_conversation`, `idx_speaker_metrics_analytics`, `idx_conversations_created`
- [ ] T012 [P] Create Python dataclass models in `backend/app/models.py` — define `TranscriptSegment(start: float, end: float, text: str, confidence: float | None, language: str | None)`, `SpeakerInterval(speaker_label: str, start: float, end: float)`, `LabelledSegment(segment: TranscriptSegment, speaker_label: str, is_low_confidence: bool)`, `ConversationSummary(overview: str, key_points: list[str], decisions: list[str], action_items: list[dict], debate_claims: list[dict] | None)`, and DB row dataclasses for each table
- [ ] T013 [P] Create frontend TypeScript types in `frontend/src/lib/types.ts` — define `ProcessingStatus` union type (`'uploading' | 'transcribing' | 'diarizing' | 'analyzing' | 'summarizing' | 'complete' | 'failed'`), `Conversation`, `Speaker` (colorIndex: 0–9), `Segment` (isLowConfidence: boolean), `SpeakerMetric`, `Summary` (transcriptHash: string) interfaces per data-model.md
- [ ] T014 [P] Create CSS design tokens in `frontend/src/styles/tokens.css` — define CSS custom properties for: 10 visually distinct speaker colors (must meet WCAG AA contrast on both light and dark backgrounds), spacing scale, typography (Google Font: Inter or similar), border radii, shadows, and transition durations
- [ ] T015 [P] Create global styles in `frontend/src/styles/global.css` — CSS reset, base typography, focus-visible styles for accessibility
- [ ] T016 [P] Create theme styles in `frontend/src/styles/themes.css` — light and dark mode token overrides using `[data-theme='light']` and `[data-theme='dark']` selectors
- [ ] T017 Create root layout in `frontend/src/app/layout.tsx` — integrate `next-themes` ThemeProvider, import global CSS, set up persistent navigation bar with Lucide icons linking to Landing (`/`) and History (`/history`) views per FR-030
- [ ] T018 [P] Create shared UI components in `frontend/src/components/shared/` — `Button.tsx`, `Icon.tsx` (Lucide wrapper), `Badge.tsx`, `Tabs.tsx` (accessible tab panel with ARIA roles and keyboard nav), `Modal.tsx` (focus trap, Escape to close), `Banner.tsx` (persistent service-unavailable banner per FR-029) with CSS Modules
- [ ] T019 Create FastAPI application entry point in `backend/app/main.py` — configure CORS (allow frontend origin), lifespan hook for `init_db()`, register routers, add `/health` endpoint returning `{"status": "ok"}`
- [ ] T020 [P] Create environment config loader in `backend/app/config.py` — load `.env` with `python-dotenv`, expose typed config: `HUGGINGFACE_TOKEN`, `GOOGLE_API_KEY`, `AUDIO_STORAGE_PATH`, `MAX_UPLOAD_BYTES` (int, default 26214400), `LOW_CONFIDENCE_THRESHOLD` (float, default 0.5), `WHISPER_MODEL_SIZE` (str, default "small")
- [ ] T021 [P] Create typed API client in `frontend/src/lib/api-client.ts` — implement typed fetch wrapper with methods for all endpoints in contracts/api.md: `createConversation()`, `startProcessing()`, `getConversation()`, `listConversations()`, `renameSpeaker()`, `updateSegment()`, `regenerateSummary()`, `deleteConversation()`, `getAudioUrl()`, `exportConversation()`. Handle error responses by parsing the `{ error, message, retry_after_seconds }` shape

**Checkpoint**: Foundation ready — backend boots with empty DB, frontend renders nav shell with theme toggle, API client is typed

---

## Phase 3: User Story 1 — Record or Upload a Conversation (Priority: P1) 🏁 MVP

**Goal**: User can record audio in-browser or upload a file, grant consent, and have the audio saved locally

**Independent Test**: Upload a short WAV fixture → consent modal appears → file accepted with progress → conversation record created in DB. Upload an unsupported file → rejected with clear error

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T022 [P] [US1] Unit test for upload validation in `backend/tests/unit/test_upload_validation.py` — test MIME type allowlist (wav, mp3, m4a, webm, ogg accepted; txt, exe, pdf rejected), size limit (reject files > MAX_UPLOAD_BYTES), zero-length file rejection, and speaker_count_hint validation (1–10 valid, 0 and 11 rejected, null accepted)
- [ ] T023 [P] [US1] Integration test for POST `/conversations` in `backend/tests/integration/test_create_conversation.py` — test successful upload with fixture WAV (201), unsupported format (400 UNSUPPORTED_FORMAT), oversized file (400 FILE_TOO_LARGE), missing file (400 VALIDATION_ERROR)
- [ ] T024 [P] [US1] Playwright E2E test in `frontend/tests/e2e/upload.spec.ts` — test: consent modal appears on Upload click, cancel aborts, accept proceeds; valid file shows progress; invalid file shows specific error message

### Implementation for User Story 1

- [ ] T025 [US1] Create conversations router in `backend/app/routers/conversations.py` — implement `POST /conversations` endpoint: accept `multipart/form-data` with `audio_file` (required), `speaker_count_hint` (optional int 1–10), `is_debate` (optional bool), `title` (optional str). Validate file extension against allowlist `{wav, mp3, m4a, webm, ogg}`, validate size against `MAX_UPLOAD_BYTES`, reject zero-length files. Save audio to `AUDIO_STORAGE_PATH/{conversation_id}/{original_filename}`. Create conversation row with `processing_status='uploading'`, audio_file row. Return 201 with conversation JSON
- [ ] T026 [US1] Create consent modal component in `frontend/src/components/consent/ConsentModal.tsx` — display before recording or upload processing: explain what data is stored locally, that transcript text is sent to Gemini for summarization, require explicit "I consent" click before proceeding. "Cancel" aborts the action. Use `Modal.tsx` with focus trap. Store `consent_granted_at` timestamp
- [ ] T027 [US1] Create file upload component in `frontend/src/components/upload/FileUpload.tsx` — client-side validation: check file type against allowlist, check file size against limit, show specific error messages per rejection reason (FR-005). On valid file: show upload progress bar. Include optional speaker count input (number 1–10 or "Unknown" radio, default "Unknown") and debate toggle checkbox
- [ ] T028 [US1] Create audio recorder component in `frontend/src/components/audio/AudioRecorder.tsx` — use `MediaRecorder` API to record audio in-browser as WEBM. Show recording timer. Stop recording saves blob. Trigger consent modal before recording starts. Handle browser permission denied with clear message
- [ ] T029 [US1] Create landing page in `frontend/src/app/page.tsx` — two main actions: "Record" (opens recorder) and "Upload" (opens file picker). Show ConsentModal before either action proceeds. After successful upload/recording, redirect to `/conversations/{id}` results page

**Checkpoint**: User can upload or record audio → consent required → file validated and saved → conversation created in DB

---

## Phase 4: User Story 2 — View Speaker-Separated Transcript (Priority: P1)

**Goal**: Audio is processed through the full pipeline and the user sees a speaker-separated, color-coded, timestamped transcript with a speaker timeline

**Independent Test**: Process fixture WAV → transcript segments displayed with distinct speaker labels/colors/timestamps → timeline shows per-speaker lanes → clicking a segment plays audio from that time

### Tests for User Story 2

- [ ] T030 [P] [US2] Unit test for transcription service in `backend/tests/unit/test_transcription.py` — mock faster-whisper, test that `transcribe()` returns `list[TranscriptSegment]` with start, end, text, confidence, language fields
- [ ] T031 [P] [US2] Unit test for diarization service in `backend/tests/unit/test_diarization.py` — mock pyannote.audio, test that `diarize()` returns `list[SpeakerInterval]` with speaker_label, start, end; test `num_speakers` param passed correctly when provided vs None
- [ ] T032 [P] [US2] Unit test for transcript merger in `backend/tests/unit/test_transcript_merger.py` — test `merge()` pure function: exact overlap → correct speaker assigned; partial overlap → largest overlap wins; no match → "unknown" speaker + `is_low_confidence=True`; test with fixture JSON transcript + RTTM diarization
- [ ] T033 [P] [US2] Unit test for analytics computation in `backend/tests/unit/test_analytics.py` — test `compute_analytics()` pure function: talk_time_pct sums to 100%, turn_count counted correctly, avg_turn_length = total_time / turn_count, interruption detection (overlapping segments from different speakers)

### Implementation for User Story 2

- [ ] T034 [US2] Create TranscriptionService protocol and WhisperService adapter in `backend/app/lib/transcription.py` and `backend/app/services/whisper_service.py` — protocol: `transcribe(audio_path: str, language: str | None = None) -> list[TranscriptSegment]`. Adapter: load faster-whisper model (size from config), call `model.transcribe()`, map output to `TranscriptSegment` list with word-level timestamps
- [ ] T035 [US2] Create DiarizationService protocol and PyannoteService adapter in `backend/app/lib/diarization.py` and `backend/app/services/pyannote_service.py` — protocol: `diarize(audio_path: str, num_speakers: int | None = None) -> list[SpeakerInterval]`. Adapter: load pyannote pipeline with HF token, pass `num_speakers` when not None, map output to `SpeakerInterval` list
- [ ] T036 [US2] Create transcript merger module in `backend/app/lib/transcript_merger.py` — pure function `merge(segments: list[TranscriptSegment], diarization: list[SpeakerInterval], low_confidence_threshold: float = 0.5) -> list[LabelledSegment]`: assign each segment to speaker with maximum time overlap, mark unmatched as low-confidence
- [ ] T037 [US2] Create analytics module in `backend/app/lib/analytics.py` — pure function `compute_analytics(labelled_segments: list[LabelledSegment], total_duration: float) -> Analytics`: compute per-speaker talk_time_seconds, talk_time_pct, turn_count, avg_turn_length_seconds, interruption_count (overlapping segments from different speakers)
- [ ] T038 [US2] Create processing pipeline orchestrator in `backend/app/pipeline.py` — orchestrate: Uploading → Transcribing → Diarizing → Analyzing → Summarizing → Complete. Update `processing_status` in DB after each step. On failure: set status to `failed`, store `error_message`, keep `last_completed_step`. Save speakers, segments, analytics to DB after diarization and analytics steps
- [ ] T039 [US2] Create SSE progress endpoint in `backend/app/routers/conversations.py` — implement `POST /conversations/{id}/process` (returns 202 with `stream_url`) and `GET /conversations/{id}/progress` (SSE stream). Emit events: `progress` with `{step, status, progress_pct}`, `error` with `{step, error, message}`, `done` with `{conversation_id, processing_status}` per contracts/api.md
- [ ] T040 [US2] Implement `GET /conversations/{id}` endpoint in `backend/app/routers/conversations.py` — return full conversation JSON with speakers, segments, analytics, summary per contracts/api.md response schema
- [ ] T041 [US2] Create audio streaming endpoint in `backend/app/routers/audio.py` — implement `GET /conversations/{id}/audio` with `Content-Range` support for seeking
- [ ] T042 [US2] Create SSE progress hook in `frontend/src/hooks/useSSEProgress.ts` — connect to `/conversations/{id}/progress` SSE endpoint, parse events, expose `{currentStep, status, progressPct, error, isDone}` state
- [ ] T043 [US2] Create pipeline progress component in `frontend/src/components/pipeline/PipelineProgress.tsx` — render multi-step progress indicator showing all 5 pipeline steps (Uploading → Transcribing → Diarizing → Analyzing → Summarizing → Complete) per FR-023. Show determinate progress bar where available, indeterminate spinner otherwise. Show error state with "Retry" button on failure (FR-027)
- [ ] T044 [US2] Create transcript panel component in `frontend/src/components/transcript/TranscriptPanel.tsx` — render ordered list of segments: each row shows speaker display name (with speaker color indicator), start time – end time, transcript text. Low-confidence segments marked with a visual indicator (dashed border + warning icon) per FR-012. Clicking a segment row calls `onSegmentClick(startTime)` for audio sync
- [ ] T045 [US2] Create speaker timeline component in `frontend/src/components/timeline/SpeakerTimeline.tsx` — custom CSS component: one horizontal lane per speaker (labeled with display name and speaker color), time blocks positioned proportionally to start/end time. Clicking a block calls `onBlockClick(startTime)`. Include time axis. Accessible: ARIA labels on blocks with speaker name and time range
- [ ] T046 [US2] Create audio player component in `frontend/src/components/audio/AudioPlayer.tsx` — wrap `<audio>` element, expose `play()`, `pause()`, `seekTo(seconds)`. Emit `onTimeUpdate(currentTime)` for syncing with transcript and timeline
- [ ] T047 [US2] Create audio sync hook in `frontend/src/hooks/useAudioSync.ts` — map `currentTime` from audio player to the active segment index, scroll active segment into view, highlight the corresponding timeline block
- [ ] T048 [US2] Create results page in `frontend/src/app/conversations/[id]/page.tsx` — fetch conversation via API client. Show `PipelineProgress` while processing. Once complete, render `Tabs` component with three tabs: Transcript (TranscriptPanel + SpeakerTimeline + AudioPlayer), Analytics (Phase 5), Summary (Phase 6). Wire audio sync between player, transcript, and timeline

**Checkpoint**: Full pipeline runs for fixture audio → transcript + timeline displayed → clicking syncs audio → low-confidence segments flagged

---

## Phase 5: User Story 3 — Rename Speakers and Correct Transcript (Priority: P1)

**Goal**: User renames speakers and edits transcript text; changes propagate instantly to all views

**Independent Test**: Rename "Speaker 1" → "Rahul" → name updates in transcript, timeline, analytics, summary within 1 second with no page reload. Edit segment text → change persists

### Tests for User Story 3

- [ ] T049 [P] [US3] Unit test for speaker renaming in `backend/tests/unit/test_speaker_renaming.py` — test `apply_rename()` pure function: "Speaker 1 said..." → "Rahul said..." replacement; test multiple occurrences; test name that is substring of another (e.g., "Speaker 1" vs "Speaker 10")
- [ ] T050 [P] [US3] Integration test for PATCH endpoints in `backend/tests/integration/test_rename_reassign.py` — test `PATCH /conversations/{id}/speakers/{speaker_id}` (rename), `PATCH /conversations/{id}/segments/{segment_id}` (text edit, speaker reassign). Verify DB updated, analytics recomputed on reassignment

### Implementation for User Story 3

- [ ] T051 [US3] Create speaker renaming module in `backend/app/lib/speaker_renaming.py` — pure function `apply_rename(summary_text: str, old_name: str, new_name: str) -> str`: replace all occurrences of old_name with new_name in text, handle word boundaries to avoid partial matches
- [ ] T052 [US3] Implement `PATCH /conversations/{id}/speakers/{speaker_id}` in `backend/app/routers/conversations.py` — accept `{"display_name": "Rahul"}` (max 80 chars), update speaker row, return updated speaker JSON
- [ ] T053 [US3] Implement `PATCH /conversations/{id}/segments/{segment_id}` in `backend/app/routers/conversations.py` — accept optional `text` (max 4000 chars) and/or `speaker_id`. If `speaker_id` changes: update segment, recompute analytics via `compute_analytics()`, return updated segment + `updated_analytics`
- [ ] T054 [US3] Create speaker rename UI in `frontend/src/components/speaker/SpeakerLabel.tsx` — clicking speaker name opens inline edit field, Enter or blur saves via API client `renameSpeaker()`. Name propagates instantly to transcript panel, timeline, and any visible analytics/summary via React state (no page reload per SC-002)
- [ ] T055 [US3] Create client-side name substitution in `frontend/src/lib/speaker-rename.ts` — pure function: substitute old speaker name with new name in the cached summary text client-side (no API call per FR-018 clarification Q3)
- [ ] T056 [US3] Add inline transcript editing in `frontend/src/components/transcript/TranscriptPanel.tsx` — double-click or edit icon on a segment enables inline text editing. Save via API client `updateSegment()`. Add speaker reassignment dropdown on each segment row per FR-014

**Checkpoint**: Rename speaker → all views update instantly → edit text → persisted → reassign segment → analytics recalculated

---

## Phase 6: User Story 4 — View Analytics (Priority: P2)

**Goal**: User sees per-speaker talk-time, turn metrics, interruptions, and (for debates) key claims

**Independent Test**: Process multi-speaker file → Analytics tab shows bar chart of talk-time %, table of turn count / avg length / interruptions per speaker. Tag as debate → debate claims listed

### Tests for User Story 4

- [ ] T057 [P] [US4] Unit test for debate claims extraction prompt in `backend/tests/unit/test_summarization.py` — test `MockSummarizationService` with mode="debate" returns `debate_claims` list; mode="meeting" returns `None` for debate_claims

### Implementation for User Story 4

- [ ] T058 [US4] Create talk-time chart component in `frontend/src/components/analytics/TalkTimeChart.tsx` — Recharts horizontal bar chart showing talk_time_pct per speaker, colored by speaker color. Accessible: include data table fallback for screen readers
- [ ] T059 [US4] Create turn metrics table component in `frontend/src/components/analytics/TurnMetricsTable.tsx` — table with columns: Speaker, Turns, Avg Length, Interruptions. Rows colored by speaker color. Sortable by any column
- [ ] T060 [US4] Create debate claims component in `frontend/src/components/analytics/DebateClaims.tsx` — render key claims/arguments per speaker only when `isDebate=true`. Show speaker name and claim text. Hidden when conversation is not tagged as debate
- [ ] T061 [US4] Wire Analytics tab in `frontend/src/app/conversations/[id]/page.tsx` — add Analytics tab content: TalkTimeChart + TurnMetricsTable + DebateClaims (conditional). Metrics update immediately when a speaker is renamed (via React state)

**Checkpoint**: Analytics tab shows charts and tables → speaker rename updates analytics instantly → debate claims shown for debate-tagged conversations

---

## Phase 7: User Story 5 — View Summary, Key Points, and Action Items (Priority: P2)

**Goal**: User sees an AI-generated summary with key points, decisions, and action items. Regenerate button appears after transcript edits

**Independent Test**: Process conversation → Summary tab shows overview, key points, decisions, action items with owners. Edit transcript text → "Regenerate Summary" button appears → click regenerates using updated transcript

### Tests for User Story 5

- [ ] T062 [P] [US5] Unit test for summarization service in `backend/tests/unit/test_summarization_service.py` — test `MockSummarizationService.summarize()` returns `ConversationSummary` with all fields populated; test Gemini adapter error handling (rate limit → RATE_LIMITED, network error → SERVICE_UNAVAILABLE)
- [ ] T063 [P] [US5] Unit test for transcript hash in `frontend/tests/unit/test_transcript_hash.ts` — test SHA-256 hash computation matches for identical transcript text, differs for edited text

### Implementation for User Story 5

- [ ] T064 [US5] Create SummarizationService protocol and GeminiService adapter in `backend/app/lib/summarization.py` and `backend/app/services/gemini_service.py` — protocol: `summarize(segments, speaker_names, mode) -> ConversationSummary`. Adapter: construct prompt with full transcript + speaker names + mode ("meeting"/"debate"), call Gemini 1.5 Flash API, parse response into `ConversationSummary`. Handle 429 → raise `RateLimitError`, 5xx/network → raise `ServiceUnavailableError`. Compute `transcript_hash` (SHA-256 of concatenated segment texts)
- [ ] T065 [US5] Create MockSummarizationService in `backend/tests/fixtures/mock_summarization.py` — implements `SummarizationService` protocol, returns fixture summary data without API call
- [ ] T066 [US5] Integrate summarization into pipeline in `backend/app/pipeline.py` — add Summarizing step: call `summarization_service.summarize()`, store result in `summaries` table with `transcript_hash` and `model_used`. On rate limit: set status to `failed` with `RATE_LIMITED` error. On service unavailable: set status to `failed` with `SERVICE_UNAVAILABLE` error
- [ ] T067 [US5] Implement `POST /conversations/{id}/summary/regenerate` in `backend/app/routers/conversations.py` — regenerate summary using current transcript segments and speaker names. Return updated summary JSON. Handle rate limit and service unavailable errors per contracts/api.md
- [ ] T068 [US5] Create transcript hash utility in `frontend/src/lib/transcript-hash.ts` — `computeHash(segments: Segment[]): Promise<string>` using `crypto.subtle.digest('SHA-256', ...)` on concatenated segment texts
- [ ] T069 [US5] Create summary panel component in `frontend/src/components/summary/SummaryPanel.tsx` — display overview paragraph, key points (bulleted list), decisions (bulleted list), action items (with owner speaker name, colored badge). Show debate claims section when `isDebate=true`
- [ ] T070 [US5] Create regenerate summary button in `frontend/src/components/summary/RegenerateSummaryButton.tsx` — compare current `computeHash(segments)` with `summary.transcriptHash`. If different: show "Regenerate Summary" button. On click: call `regenerateSummary()` API, show loading spinner, replace summary content on success. Handle errors: rate-limited → show wait time; service unavailable → show error message with retry
- [ ] T071 [US5] Wire Summary tab in `frontend/src/app/conversations/[id]/page.tsx` — add Summary tab content: SummaryPanel + RegenerateSummaryButton. Speaker renames substitute instantly via `speaker-rename.ts` client-side (no API call)

**Checkpoint**: Summary tab shows AI-generated content → rename speaker → name substitutes instantly → edit transcript → "Regenerate Summary" appears → click regenerates

---

## Phase 8: User Story 6 — History, Deletion, and Export (Priority: P3)

**Goal**: User can browse past conversations, reopen them, delete them fully, and export as PDF or text

**Independent Test**: Process a conversation, close browser, reopen → find in history → export as PDF and text → delete → verify removed from list and disk

### Tests for User Story 6

- [ ] T072 [P] [US6] Integration test for history and delete in `backend/tests/integration/test_history_delete.py` — test `GET /conversations` returns list sorted by created_at desc; test `DELETE /conversations/{id}` returns 204, removes DB rows, removes audio file from disk
- [ ] T073 [P] [US6] Playwright E2E test in `frontend/tests/e2e/history_delete.spec.ts` — create conversation → navigate to History → verify listed → delete → verify removed from list

### Implementation for User Story 6

- [ ] T074 [US6] Implement `GET /conversations` (list) in `backend/app/routers/conversations.py` — accept `limit` (default 50), `offset` (default 0), `order` (default `created_at_desc`). Return paginated list with `id, title, created_at, duration_seconds, processing_status, speaker_display_names[]`
- [ ] T075 [US6] Implement `DELETE /conversations/{id}` in `backend/app/routers/conversations.py` — delete conversation row (cascades to all child tables), delete audio file from disk. Return 204. If audio file deletion fails, log warning but still return 204 (DB is source of truth)
- [ ] T076 [US6] Implement `GET /conversations/{id}/export` in `backend/app/routers/conversations.py` — accept `format=text|json`. Text format: header with title/date/speakers, then chronological transcript with speaker labels and timestamps, then summary. JSON format: full conversation JSON
- [ ] T077 [US6] Create history page in `frontend/src/app/history/page.tsx` — fetch conversations list via API client. Render sorted list: each card shows title, date, duration, speaker names (colored badges). Click opens `/conversations/{id}`. Show empty state ("No conversations yet") when list is empty. Include delete button per conversation with confirmation modal
- [ ] T078 [US6] Create client-side PDF export in `frontend/src/lib/export-pdf.ts` — generate PDF from transcript + summary using browser `window.print()` with a print-specific CSS stylesheet, or a lightweight library like `jspdf`. Include conversation title, date, speakers, full transcript with speaker labels, and summary
- [ ] T079 [US6] Add export buttons to results page in `frontend/src/app/conversations/[id]/page.tsx` — "Export as PDF" button (calls `exportPdf()`), "Export as text" button (calls API `/export?format=text` and triggers download)

**Checkpoint**: History page lists past conversations → reopen → full data displayed → export as PDF and text → delete removes all data and audio file

---

## Phase 9: User Story 7 — Multilingual Transcription (Priority: P2)

**Goal**: Transcription supports English, Hindi, Gujarati, and code-mixed speech

**Independent Test**: Upload Hindi/English code-mixed audio → transcript contains segments in both languages

### Implementation for User Story 7

- [ ] T080 [US7] Update WhisperService in `backend/app/services/whisper_service.py` — pass `language` hint parameter to faster-whisper when user selects a language; when not specified, use auto-detection. Map detected language to ISO 639-1 code (`en`, `hi`, `gu`) in output `TranscriptSegment.language` field. Document supported languages in API response
- [ ] T081 [US7] Add language selection to upload UI in `frontend/src/components/upload/FileUpload.tsx` — add optional language selector: English, Hindi, Gujarati, Auto-detect (default). Pass selected language to `createConversation()` API call
- [ ] T082 [US7] Display language indicator in transcript in `frontend/src/components/transcript/TranscriptPanel.tsx` — show small language badge (e.g., "EN", "HI", "GU") on segments where `language_code` is available. Use subtle styling that does not interfere with readability

**Checkpoint**: Hindi/English audio → transcript shows segments in correct languages → language badges displayed

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T083 [P] Implement retry endpoint `POST /conversations/{id}/retry` in `backend/app/routers/conversations.py` — re-run only the `last_completed_step + 1` through the end of the pipeline. Return 202 with stream URL. Validate conversation is in `failed` status
- [ ] T084 [P] Add service-unavailable banner logic in `frontend/src/app/layout.tsx` — on app load, ping `/health`. If unreachable, show persistent `Banner` component "Processing unavailable — service is unreachable". Existing conversations remain accessible (FR-029). Poll `/health` every 30 seconds to auto-dismiss when service recovers
- [ ] T085 [P] Implement consent notice content per privacy requirements — define exact consent text in `frontend/src/components/consent/ConsentModal.tsx`: explain local storage of audio/transcripts, disclose that transcript text is sent to Google Gemini API for summarization, note that audio is never sent to external services. Record `consent_granted_at` per conversation
- [ ] T086 [P] Add `prefers-reduced-motion` media query to `frontend/src/styles/global.css` — disable animations and transitions for users who prefer reduced motion
- [ ] T087 [P] Create empty states for all views in `frontend/src/components/shared/EmptyState.tsx` — reusable component with Lucide icon + message. Use for: History (no conversations), Analytics (not yet computed), Summary (not yet generated)
- [ ] T088 [P] Add form validation states to speaker count input — show inline error for non-numeric, 0, negative, and >10 values with specific messages per FR-004
- [ ] T089 [P] Add loading skeletons for all async content — transcript panel, analytics charts, summary panel, and history list show skeleton loaders while data fetches
- [ ] T090 [P] Create `colab_runner.ipynb` at repository root — notebook that installs backend dependencies, starts uvicorn, exposes via ngrok free tier. Include setup instructions per quickstart.md
- [ ] T091 Run full quickstart.md validation — execute all 10 validation scenarios (V-01 through V-10) from quickstart.md against running local setup. Document any issues
- [ ] T092 [P] Playwright smoke test in `frontend/tests/e2e/smoke.spec.ts` — automated happy-path: upload fixture WAV → pipeline completes → rename speaker → verify propagation → export → delete. Uses mocked backend for CI
- [ ] T093 Code cleanup, unused import removal, and final linting pass across both `frontend/` and `backend/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (Phase 2) — No dependencies on other stories
- **US2 (Phase 4)**: Depends on US1 (needs conversation + audio to process)
- **US3 (Phase 5)**: Depends on US2 (needs transcript + speakers to rename/edit)
- **US4 (Phase 6)**: Depends on US2 (needs analytics data from pipeline)
- **US5 (Phase 7)**: Depends on US2 (needs transcript for summarization)
- **US6 (Phase 8)**: Depends on US1 (needs conversations to list/delete/export); full export needs US5
- **US7 (Phase 9)**: Depends on US2 (extends transcription service)
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundation)
                        │
                        ├── Phase 3 (US1: Upload/Record) ──┐
                        │                                    │
                        │                              Phase 4 (US2: Transcript)
                        │                                    │
                        │                    ┌───────────────┼───────────────┐
                        │                    │               │               │
                        │              Phase 5 (US3)   Phase 6 (US4)  Phase 7 (US5)
                        │              Rename/Edit     Analytics      Summary
                        │                    │               │               │
                        │                    └───────────────┼───────────────┘
                        │                                    │
                        ├── Phase 8 (US6: History/Export) ←───┘
                        │
                        └── Phase 9 (US7: Multilingual) ←── Phase 4
                                                             │
                                                       Phase 10 (Polish)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation (constitution IV)
- Models / dataclasses before services
- Services before endpoints/routers
- Backend before frontend components that consume the API
- Core implementation before integration wiring

### Parallel Opportunities

- All Setup tasks marked [P] (T002–T010) can run in parallel
- All Foundational tasks marked [P] (T012–T016, T018, T020–T021) can run in parallel
- Tests within a user story marked [P] can run in parallel
- Once US2 is complete: US3, US4, US5 can be worked on in parallel by different developers
- All Polish tasks marked [P] (T083–T090, T092) can run in parallel

---

## Parallel Example: User Story 2

```bash
# Launch all tests for US2 together:
Task: T030 "Unit test for transcription service"
Task: T031 "Unit test for diarization service"
Task: T032 "Unit test for transcript merger"
Task: T033 "Unit test for analytics computation"

# Launch backend service implementations in parallel (after tests fail):
Task: T034 "Create TranscriptionService + WhisperService"
Task: T035 "Create DiarizationService + PyannoteService"
Task: T036 "Create transcript merger module"
Task: T037 "Create analytics module"

# Then sequential pipeline + frontend:
Task: T038 "Create pipeline orchestrator" (depends on T034–T037)
Task: T039–T048 "SSE, endpoints, frontend components" (sequential)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (Upload/Record)
4. **STOP and VALIDATE**: Test upload, consent, validation independently
5. Demo: "User can upload audio and see it stored with consent"

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (Upload/Record) → Test independently → **MVP!**
3. US2 (Transcript/Pipeline) → Test independently → Core product
4. US3 (Rename/Edit) → Test independently → Full interactivity
5. US4 + US5 in parallel (Analytics + Summary) → Test independently → Intelligence layer
6. US6 (History/Export) → Test independently → Persistence & sharing
7. US7 (Multilingual) → Test independently → Localization
8. Polish → Production-ready

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same phase
- [US#] label maps task to specific user story for traceability
- Each user story is independently completable and testable at its checkpoint
- Tests MUST fail before implementing (RED → GREEN → REFACTOR per constitution IV)
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence
