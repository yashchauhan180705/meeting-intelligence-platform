# Data Model: Meeting & Debate Intelligence Platform

**Branch**: `001-meeting-debate-intelligence` | **Date**: 2026-10-13
**Source**: spec.md Key Entities + Clarifications Q1, Q2

---

## Entity Relationship Overview

```
Conversation ─── has one ───── AudioFile
     │
     ├── has many ──────────── Speaker (1–10)
     │                              │
     ├── has one ──────────── Transcript
     │                              │
     │                         has many ── Segment ──── references ── Speaker
     │
     ├── has one ──────────── Analytics
     │                              │
     │                         has many ── SpeakerMetric ─ references ── Speaker
     │
     └── has one ──────────── Summary
```

---

## SQLite Schema

### Table: `conversations`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `title` | TEXT | NOT NULL | Auto-generated from date+time; user-editable |
| `created_at` | TEXT | NOT NULL | ISO-8601 UTC |
| `duration_seconds` | REAL | NULL | Set after audio is loaded |
| `speaker_count_hint` | INTEGER | NULL | User-provided 1–10; NULL = unknown |
| `processing_status` | TEXT | NOT NULL | See state machine below |
| `is_debate` | INTEGER | NOT NULL DEFAULT 0 | Boolean (0/1); user-tagged |
| `consent_granted_at` | TEXT | NOT NULL | ISO-8601 UTC; recorded at consent modal acceptance |

**Processing status state machine** (Q1 clarification):

```
Uploading → Transcribing → Diarizing → Analyzing → Summarizing → Complete
     └──────────┴────────────┴───────────┴───────────┴─────────── Failed
```

Valid values: `uploading`, `transcribing`, `diarizing`, `analyzing`, `summarizing`, `complete`, `failed`

A `failed` conversation retains its `last_completed_step` to support partial recovery (FR-027).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `last_completed_step` | TEXT | NULL | Last successfully completed pipeline step |
| `error_message` | TEXT | NULL | Set when status = `failed` |

---

### Table: `audio_files`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `conversation_id` | TEXT | NOT NULL, FK → conversations.id ON DELETE CASCADE | |
| `file_path` | TEXT | NOT NULL | Absolute local path to audio file on disk |
| `original_filename` | TEXT | NOT NULL | Original upload filename |
| `format` | TEXT | NOT NULL | `wav`, `mp3`, `m4a`, `webm`, `ogg` |
| `size_bytes` | INTEGER | NOT NULL | |
| `duration_seconds` | REAL | NULL | Populated after audio is decoded |

---

### Table: `speakers`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `conversation_id` | TEXT | NOT NULL, FK → conversations.id ON DELETE CASCADE | |
| `system_label` | TEXT | NOT NULL | `Speaker 1` … `Speaker 10`; assigned by diarization |
| `display_name` | TEXT | NOT NULL | Initially equals `system_label`; updated on rename (FR-013) |
| `color_index` | INTEGER | NOT NULL | 0–9; maps to the 10-color palette (Q2 clarification) |
| `order_index` | INTEGER | NOT NULL | Rendering order in timeline and analytics |

**Validation rules**:
- `color_index` MUST be unique per `conversation_id`
- Maximum 10 speakers per conversation (FR-004, FR-008)
- `display_name` max 80 characters

---

### Table: `segments`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `conversation_id` | TEXT | NOT NULL, FK → conversations.id ON DELETE CASCADE | |
| `speaker_id` | TEXT | NOT NULL, FK → speakers.id | Updated on segment reassignment (FR-014) |
| `start_time` | REAL | NOT NULL | Seconds from audio start |
| `end_time` | REAL | NOT NULL | Seconds from audio start; > start_time |
| `text` | TEXT | NOT NULL | Transcript text; editable inline (FR-015) |
| `confidence` | REAL | NULL | 0.0–1.0; NULL if model does not provide |
| `is_low_confidence` | INTEGER | NOT NULL DEFAULT 0 | 1 if confidence < threshold or diarization unmatched |
| `language_code` | TEXT | NULL | ISO 639-1; `en`, `hi`, `gu`, or detected code |
| `order_index` | INTEGER | NOT NULL | Chronological order within conversation |

**Validation rules**:
- `end_time` > `start_time`
- `order_index` unique per `conversation_id`
- `text` max 4000 characters per segment

---

### Table: `analytics`

One row per conversation. Updated after diarization completes and after any segment reassignment.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `conversation_id` | TEXT | NOT NULL UNIQUE, FK → conversations.id ON DELETE CASCADE | |
| `computed_at` | TEXT | NOT NULL | ISO-8601 UTC |
| `total_duration_seconds` | REAL | NOT NULL | |
| `interruption_count` | INTEGER | NOT NULL DEFAULT 0 | Total across all speakers |

---

### Table: `speaker_metrics`

One row per speaker per conversation (child of `analytics`).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `analytics_id` | TEXT | NOT NULL, FK → analytics.id ON DELETE CASCADE | |
| `speaker_id` | TEXT | NOT NULL, FK → speakers.id ON DELETE CASCADE | |
| `talk_time_seconds` | REAL | NOT NULL | |
| `talk_time_pct` | REAL | NOT NULL | 0.0–100.0 |
| `turn_count` | INTEGER | NOT NULL | |
| `avg_turn_length_seconds` | REAL | NOT NULL | |
| `interruption_count` | INTEGER | NOT NULL DEFAULT 0 | Times this speaker interrupted another |

---

### Table: `summaries`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | TEXT | PRIMARY KEY | UUID v4 |
| `conversation_id` | TEXT | NOT NULL UNIQUE, FK → conversations.id ON DELETE CASCADE | |
| `overview` | TEXT | NOT NULL | Paragraph summary |
| `key_points` | TEXT | NOT NULL | JSON array of strings |
| `decisions` | TEXT | NOT NULL | JSON array of strings |
| `action_items` | TEXT | NOT NULL | JSON array of `{ text, owner_speaker_id \| null }` |
| `debate_claims` | TEXT | NULL | JSON array of `{ speaker_id, claim }` — only for debate conversations |
| `generated_at` | TEXT | NOT NULL | ISO-8601 UTC |
| `transcript_hash` | TEXT | NOT NULL | SHA-256 of transcript text at generation time; used to detect staleness (FR-028) |
| `model_used` | TEXT | NOT NULL | e.g., `gemini-1.5-flash`; for provenance |

**Staleness detection (Q3 clarification)**:
When transcript text changes, the frontend computes the current hash and compares it to `transcript_hash`. If different, a "Regenerate Summary" button is shown. Speaker rename substitution is applied client-side without updating `transcript_hash`.

---

## Cascade Delete

When a `Conversation` row is deleted:
- `audio_files` rows deleted → application layer also removes the file from disk (FR-020)
- `speakers`, `segments`, `analytics`, `speaker_metrics`, `summaries` rows deleted via `ON DELETE CASCADE`

---

## Indexes

```sql
CREATE INDEX idx_segments_conversation ON segments(conversation_id, order_index);
CREATE INDEX idx_speaker_metrics_analytics ON speaker_metrics(analytics_id);
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);
```

---

## Python Dataclasses (Service Layer)

```python
# Illustrative only — types, not full implementation
@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    confidence: float | None
    language: str | None

@dataclass
class SpeakerInterval:
    speaker_label: str  # "SPEAKER_00", "SPEAKER_01", …
    start: float
    end: float

@dataclass
class LabelledSegment:
    segment: TranscriptSegment
    speaker_label: str
    is_low_confidence: bool

@dataclass
class ConversationSummary:
    overview: str
    key_points: list[str]
    decisions: list[str]
    action_items: list[dict]     # { "text": str, "owner": str | None }
    debate_claims: list[dict] | None  # { "speaker": str, "claim": str }
```

---

## Frontend TypeScript Types

```typescript
// Illustrative only — types, not full implementation
type ProcessingStatus =
  | 'uploading' | 'transcribing' | 'diarizing'
  | 'analyzing' | 'summarizing' | 'complete' | 'failed';

interface Conversation {
  id: string;
  title: string;
  createdAt: string;       // ISO-8601
  durationSeconds: number | null;
  speakerCountHint: number | null;
  processingStatus: ProcessingStatus;
  lastCompletedStep: ProcessingStatus | null;
  isDebate: boolean;
}

interface Speaker {
  id: string;
  systemLabel: string;    // "Speaker 1"
  displayName: string;    // user-editable
  colorIndex: number;     // 0–9
}

interface Segment {
  id: string;
  speakerId: string;
  startTime: number;
  endTime: number;
  text: string;
  isLowConfidence: boolean;
  languageCode: string | null;
}

interface SpeakerMetric {
  speakerId: string;
  talkTimePct: number;
  turnCount: number;
  avgTurnLengthSeconds: number;
  interruptionCount: number;
}

interface Summary {
  overview: string;
  keyPoints: string[];
  decisions: string[];
  actionItems: Array<{ text: string; ownerSpeakerId: string | null }>;
  debateClaims: Array<{ speakerId: string; claim: string }> | null;
  generatedAt: string;
  transcriptHash: string;
  modelUsed: string;
}
```
