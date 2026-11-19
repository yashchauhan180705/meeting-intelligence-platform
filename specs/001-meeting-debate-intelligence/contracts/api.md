# API Contract: Audio Processing Service

**Service**: Meeting & Debate Intelligence Platform — Python/FastAPI backend
**Base URL**: `http://localhost:8000` (local) | `$NEXT_PUBLIC_API_URL` (Colab fallback)
**Date**: 2026-10-13

---

## General Conventions

- All request/response bodies are JSON unless noted (multipart for file upload).
- All timestamps are ISO-8601 UTC strings.
- All IDs are UUID v4 strings.
- HTTP status codes follow REST conventions; see Error Format below.
- SSE endpoints use `Content-Type: text/event-stream`.

---

## Error Format

```json
{
  "error": "RATE_LIMITED",
  "message": "Gemini API rate limit reached. Retry after 60 seconds.",
  "retry_after_seconds": 60
}
```

Error codes: `VALIDATION_ERROR`, `FILE_TOO_LARGE`, `UNSUPPORTED_FORMAT`,
`RATE_LIMITED`, `SERVICE_UNAVAILABLE`, `NOT_FOUND`, `PROCESSING_FAILED`

---

## Endpoints

### POST `/conversations`

Create a new conversation record and upload audio.

**Request**: `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `audio_file` | file | ✅ | WAV, MP3, M4A, WEBM, OGG; max size enforced by config |
| `speaker_count_hint` | integer | ❌ | 1–10; omit for "unknown" |
| `is_debate` | boolean | ❌ | Default false |
| `title` | string | ❌ | Auto-generated if omitted |

**Response `201 Created`**:
```json
{
  "id": "conv-uuid",
  "title": "Meeting 2026-10-13 21:00",
  "created_at": "2026-10-13T15:30:00Z",
  "processing_status": "uploading",
  "speaker_count_hint": 3,
  "is_debate": false
}
```

**Errors**: `VALIDATION_ERROR` (missing file), `FILE_TOO_LARGE`, `UNSUPPORTED_FORMAT`

---

### POST `/conversations/{id}/process`

Start the processing pipeline for an uploaded conversation.
Returns immediately; progress is streamed via SSE (see below).

**Response `202 Accepted`**:
```json
{ "conversation_id": "conv-uuid", "stream_url": "/conversations/conv-uuid/progress" }
```

**Errors**: `NOT_FOUND`, `PROCESSING_FAILED` (already processing or complete)

---

### GET `/conversations/{id}/progress`

Server-Sent Events stream for pipeline progress.

**Response**: `text/event-stream`

Each event:
```
event: progress
data: {"step": "transcribing", "status": "running", "progress_pct": 45}

event: progress
data: {"step": "diarizing", "status": "complete", "progress_pct": 100}

event: error
data: {"step": "diarizing", "error": "PROCESSING_FAILED", "message": "pyannote model load failed"}

event: done
data: {"conversation_id": "conv-uuid", "processing_status": "complete"}
```

Steps: `uploading`, `transcribing`, `diarizing`, `analyzing`, `summarizing`

---

### POST `/conversations/{id}/retry`

Retry the failed pipeline step (partial recovery, FR-027).

**Response `202 Accepted`**:
```json
{ "conversation_id": "conv-uuid", "retrying_step": "diarizing", "stream_url": "/conversations/conv-uuid/progress" }
```

---

### GET `/conversations`

List all conversations (history view).

**Query params**: `limit` (default 50), `offset` (default 0), `order` (`created_at_desc` default)

**Response `200 OK`**:
```json
{
  "items": [
    {
      "id": "conv-uuid",
      "title": "Meeting 2026-10-13",
      "created_at": "2026-10-13T15:30:00Z",
      "duration_seconds": 623.4,
      "processing_status": "complete",
      "speaker_display_names": ["Rahul", "Priya"]
    }
  ],
  "total": 12,
  "limit": 50,
  "offset": 0
}
```

---

### GET `/conversations/{id}`

Get full conversation details including speakers, segments, analytics, and summary.

**Response `200 OK`**:
```json
{
  "id": "conv-uuid",
  "title": "Meeting 2026-10-13",
  "created_at": "2026-10-13T15:30:00Z",
  "duration_seconds": 623.4,
  "processing_status": "complete",
  "last_completed_step": null,
  "is_debate": false,
  "speaker_count_hint": 2,
  "speakers": [
    { "id": "spk-uuid-1", "system_label": "Speaker 1", "display_name": "Rahul", "color_index": 0 }
  ],
  "segments": [
    {
      "id": "seg-uuid",
      "speaker_id": "spk-uuid-1",
      "start_time": 0.0,
      "end_time": 4.32,
      "text": "Let's start with the agenda.",
      "is_low_confidence": false,
      "language_code": "en",
      "order_index": 0
    }
  ],
  "analytics": {
    "total_duration_seconds": 623.4,
    "interruption_count": 3,
    "speaker_metrics": [
      {
        "speaker_id": "spk-uuid-1",
        "talk_time_pct": 58.2,
        "turn_count": 21,
        "avg_turn_length_seconds": 17.3,
        "interruption_count": 1
      }
    ]
  },
  "summary": {
    "overview": "The team discussed Q4 priorities...",
    "key_points": ["Budget approved", "Launch date moved to November"],
    "decisions": ["Use Figma for design handoff"],
    "action_items": [{ "text": "Send calendar invite", "owner_speaker_id": "spk-uuid-1" }],
    "debate_claims": null,
    "generated_at": "2026-10-13T16:00:00Z",
    "transcript_hash": "abc123...",
    "model_used": "gemini-1.5-flash"
  }
}
```

---

### PATCH `/conversations/{id}/speakers/{speaker_id}`

Rename a speaker (FR-013).

**Request**:
```json
{ "display_name": "Rahul" }
```

**Response `200 OK`**:
```json
{ "id": "spk-uuid-1", "display_name": "Rahul" }
```

**Note**: Frontend updates summary text via client-side name substitution (no AI call). No summary regeneration endpoint is triggered by this action (Q3 clarification).

---

### PATCH `/conversations/{id}/segments/{segment_id}`

Edit segment text or reassign speaker (FR-014, FR-015).

**Request** (all fields optional):
```json
{
  "text": "Corrected transcript text.",
  "speaker_id": "spk-uuid-2"
}
```

**Response `200 OK`**:
```json
{
  "id": "seg-uuid",
  "text": "Corrected transcript text.",
  "speaker_id": "spk-uuid-2",
  "is_low_confidence": false
}
```

**Note**: If `speaker_id` is updated, analytics are recomputed server-side and returned in the response under `updated_analytics`.

---

### POST `/conversations/{id}/summary/regenerate`

Trigger manual summary regeneration after transcript edits (FR-028).

**Response `202 Accepted`** (summary generated synchronously for short transcripts, async for long):
```json
{
  "summary": { "overview": "...", "key_points": [], "decisions": [], "action_items": [], "generated_at": "...", "transcript_hash": "..." }
}
```

**Errors**: `RATE_LIMITED`, `SERVICE_UNAVAILABLE`

---

### DELETE `/conversations/{id}`

Permanently delete conversation, all associated data, and the audio file from disk (FR-020).

**Response `204 No Content`**

---

### GET `/conversations/{id}/audio`

Stream the audio file for browser playback.

**Response**: `audio/*` with `Content-Range` support for seeking.

---

### GET `/conversations/{id}/export`

Export transcript and summary.

**Query params**: `format` = `text` | `json`

**Response `200 OK`**: Plain text or JSON export. PDF export is handled client-side.

---

## Library Module Interfaces (Python)

```python
# transcription_service.py
class TranscriptionService(Protocol):
    def transcribe(self, audio_path: str, language: str | None = None) -> list[TranscriptSegment]: ...

# diarization_service.py
class DiarizationService(Protocol):
    def diarize(self, audio_path: str, num_speakers: int | None = None) -> list[SpeakerInterval]: ...

# transcript_merger.py
def merge(
    segments: list[TranscriptSegment],
    diarization: list[SpeakerInterval],
    low_confidence_threshold: float = 0.5
) -> list[LabelledSegment]: ...

# analytics_service.py
def compute_analytics(
    labelled_segments: list[LabelledSegment],
    total_duration: float
) -> Analytics: ...

# summarization_service.py
class SummarizationService(Protocol):
    def summarize(
        self,
        segments: list[LabelledSegment],
        speaker_names: dict[str, str],
        mode: Literal["meeting", "debate"]
    ) -> ConversationSummary: ...

# speaker_renaming.py  (pure function — no DB)
def apply_rename(
    summary_text: str,
    old_name: str,
    new_name: str
) -> str: ...
```
