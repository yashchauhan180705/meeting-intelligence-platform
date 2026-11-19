# Feature Specification: Meeting & Debate Intelligence Platform

**Feature Branch**: `001-meeting-debate-intelligence`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Build a Meeting and Debate Intelligence Platform that turns a recorded conversation into a speaker-separated transcript, visual analysis and summary."

## Clarifications

### Session 2026-10-13

- Q: What processing states should a conversation move through from audio submission to results? → A: Multi-step pipeline — Uploading → Transcribing → Diarizing → Analyzing → Summarizing → Complete. Each step is visible to the user. Partial failure recovery is supported (e.g., transcription succeeds but diarization fails → show raw transcript with an option to retry the failed step).
- Q: What is the maximum number of speakers the system should support in a single conversation? → A: Up to 10 speakers. This covers virtually all meeting and debate scenarios without overcomplicating the UI or pushing diarization models beyond their reliable range.
- Q: When the user edits transcript text or renames a speaker, should the AI summary regenerate automatically or manually? → A: Manual trigger. Speaker renames substitute instantly in the existing summary text (no API call). Transcript text edits surface a "Regenerate Summary" button; full re-summarization only runs when the user clicks it. This conserves free-tier API quota.
- Q: What should happen when the AI service is completely unavailable (not rate-limited, but down)? → A: Combine immediate error with offline browsing. New processing shows a clear "Service unavailable" error with a "Retry" button; audio is saved locally so no data is lost. Existing already-processed conversations remain fully browsable with a banner indicating that new processing is temporarily unavailable.
- Q: How should the application be structured for navigation? → A: Single page with tabs. A landing screen handles upload/record. After processing, a results page displays Transcript, Analytics, and Summary as switchable tabs. A History page is accessible from the main navigation bar.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Record or Upload a Conversation (Priority: P1)

A student finishes a group discussion and wants to capture what was said. They open the platform, choose to either record directly in the browser or upload an existing audio file. Before processing, they optionally enter the number of speakers. The system validates the file, shows progress, and moves on to transcription.

**Why this priority**: Without audio input the platform has no data to work with. This is the entry point for every other capability.

**Independent Test**: Can be fully tested by uploading a short sample audio file (or recording a few seconds) and confirming the file is accepted, progress is shown, and unsupported or oversized files are rejected with a clear message.

**Acceptance Scenarios**:

1. **Given** the user is on the home screen, **When** they click "Record", **Then** a consent notice is displayed, and recording begins only after the user grants consent.
2. **Given** the user is on the home screen, **When** they click "Upload" and select a supported audio file under the size limit, **Then** the file is accepted and upload progress is shown.
3. **Given** the user selects an unsupported file type, **When** they confirm the upload, **Then** the system rejects the file with a clear message listing supported formats.
4. **Given** the user selects a file that exceeds the size limit, **When** they confirm the upload, **Then** the system rejects the file with a message stating the maximum allowed size.
5. **Given** the user is uploading or recording, **When** they optionally enter a speaker count (or leave it as "unknown"), **Then** the value is stored and passed as a hint to the speaker-separation step.

---

### User Story 2 — View Speaker-Separated Transcript (Priority: P1)

After audio is processed, the user sees a transcript where each segment is attributed to a speaker, color-coded, and timestamped. A timeline shows when each speaker was talking.

**Why this priority**: The speaker-separated transcript is the core deliverable — every downstream feature (analytics, summary, export) depends on it.

**Independent Test**: Process a sample 2-speaker file and verify that the transcript displays segments with distinct speaker labels, per-speaker colors, and start/end timestamps, and that a timeline with per-speaker lanes is rendered.

**Acceptance Scenarios**:

1. **Given** audio processing is complete, **When** the results screen loads, **Then** the transcript displays each segment with a speaker label, start time, end time, and speaker-specific color.
2. **Given** the results screen is displayed, **When** the user views the timeline, **Then** each speaker has a dedicated lane and spoken intervals are shown as blocks.
3. **Given** the transcript is displayed, **When** the user clicks a transcript line, **Then** audio playback begins from that segment's start time.
4. **Given** the timeline is displayed, **When** the user clicks a block on the timeline, **Then** audio playback begins from that block's start time and the corresponding transcript line is scrolled into view.
5. **Given** speaker-separation confidence is low for one or more segments, **When** the results screen loads, **Then** those segments are visually marked as low-confidence and a notice informs the user.

---

### User Story 3 — Rename Speakers and Correct Transcript (Priority: P1)

The user recognises the voices and wants to replace "Speaker 1" with "Rahul". They also notice a wrongly attributed segment and a transcription error, and want to fix both.

**Why this priority**: Speaker names give the transcript real-world meaning. Correction ability is essential because AI output is imperfect (constitution principle VIII).

**Independent Test**: Rename "Speaker 1" to "Rahul" and verify the name updates across the transcript, timeline, analytics, and summary instantly. Reassign a segment and edit text, then confirm changes are reflected everywhere.

**Acceptance Scenarios**:

1. **Given** the results screen is displayed, **When** the user renames "Speaker 1" to "Rahul", **Then** the name "Rahul" replaces "Speaker 1" in the transcript, timeline, analytics, and summary without a page reload.
2. **Given** a segment is attributed to Speaker 2, **When** the user reassigns it to Speaker 1, **Then** the segment's speaker label, color, and analytics update immediately.
3. **Given** a transcript segment contains an error, **When** the user edits the text inline, **Then** the corrected text is saved and reflected in the summary and export.

---

### User Story 4 — View Analytics (Priority: P2)

After reviewing the transcript, the user wants to understand speaking patterns: who dominated, how often people took turns, and (for debates) what each person argued.

**Why this priority**: Analytics add insight beyond the raw transcript, but the platform delivers value without them.

**Independent Test**: Process a multi-speaker file and verify that talk-time percentages, turn counts, average turn lengths, and interruption counts are displayed per speaker. For debate mode, verify that key claims per speaker are listed.

**Acceptance Scenarios**:

1. **Given** transcription and diarization are complete, **When** the user switches to the Analytics tab on the results page, **Then** talk-time share per speaker is displayed as a percentage with a visual chart.
2. **Given** analytics are displayed, **When** the user examines turn metrics, **Then** number of turns, average turn length, and interruption count per speaker are shown.
3. **Given** the conversation is tagged as a debate, **When** the user views debate analytics, **Then** key claims or arguments per speaker are listed.
4. **Given** the user renames a speaker, **When** they return to analytics, **Then** all metrics reflect the updated speaker name immediately.

---

### User Story 5 — View Summary, Key Points, and Action Items (Priority: P2)

The user wants a concise summary to share with teammates who missed the meeting, including decisions made and action items with owners.

**Why this priority**: Summaries save the user time and provide shareable value, but depend on the transcript being available first.

**Independent Test**: Process a sample conversation and verify a summary, list of key points, decisions, and action items (with assigned owners where mentioned) are generated using the renamed speaker names.

**Acceptance Scenarios**:

1. **Given** transcript processing is complete, **When** the user switches to the Summary tab on the results page, **Then** a concise paragraph summary of the conversation is displayed.
2. **Given** the summary is displayed, **When** the user reviews it, **Then** key points, decisions, and action items are listed separately.
3. **Given** action items are extracted, **When** a speaker's name was mentioned as the owner, **Then** the action item shows the (renamed) speaker as the owner.
4. **Given** a speaker has been renamed, **When** the summary view refreshes, **Then** the renamed speaker name is substituted instantly in the existing summary text without an API call.
5. **Given** the user has edited transcript text after the summary was generated, **When** they view the summary, **Then** a "Regenerate Summary" button is visible, and clicking it triggers a new AI summarization using the updated transcript.

---

### User Story 6 — History, Deletion, and Export (Priority: P3)

The user returns the next day to review a past conversation, exports it for a report, and deletes an old one they no longer need.

**Why this priority**: History and export are convenience features. The core value is delivered in a single session even without them.

**Independent Test**: Process a conversation, close the app, reopen it, find the conversation in history, export it as PDF and as text, then delete it and verify it (including audio) is removed completely.

**Acceptance Scenarios**:

1. **Given** the user has processed conversations previously, **When** they navigate to the History page via the main navigation, **Then** past conversations are listed with date, duration, and speaker names.
2. **Given** the user selects a past conversation, **When** they open it, **Then** the full transcript, timeline, analytics, and summary are displayed.
3. **Given** the user is viewing a conversation, **When** they choose "Export as PDF", **Then** a PDF containing the transcript and summary is downloaded.
4. **Given** the user is viewing a conversation, **When** they choose "Export as text", **Then** a plain-text file containing the transcript and summary is downloaded.
5. **Given** the user selects a conversation from history, **When** they choose "Delete", **Then** the conversation and its audio are permanently removed and no longer appear in history.

---

### User Story 7 — Multilingual Transcription (Priority: P2)

A user records a group discussion conducted in Hindi with some English and Gujarati mixed in. They expect the transcript to reflect the actual languages spoken.

**Why this priority**: Multilingual support (English, Hindi, Gujarati, and code-mixed speech) is a stated requirement and differentiates the platform for its target audience.

**Independent Test**: Upload a sample Hindi/English code-mixed audio file and verify the transcript contains segments in the appropriate languages rather than forcing everything into one language.

**Acceptance Scenarios**:

1. **Given** the user uploads an English audio file, **When** transcription completes, **Then** the transcript is in English.
2. **Given** the user uploads a Hindi audio file, **When** transcription completes, **Then** the transcript is in Hindi (Devanagari or romanized, matching model output).
3. **Given** the user uploads a Gujarati audio file, **When** transcription completes, **Then** the transcript is in Gujarati.
4. **Given** the user uploads audio with mixed English and Hindi, **When** transcription completes, **Then** segments reflect the language switches as accurately as the underlying model allows.

---

### Edge Cases

- What happens when a user uploads a zero-length or corrupted audio file? The system MUST reject it with a clear error message before any processing begins.
- What happens when the audio contains only one speaker but the user entered "3"? The system MUST still produce a valid transcript; the speaker count is a hint, not a hard constraint.
- What happens when the free-tier API limit is exhausted during processing? The system MUST notify the user with an actionable message (e.g., estimated wait time or suggestion to retry later) and MUST NOT fail silently.
- What happens when the browser tab is closed during recording? The system SHOULD attempt to save any captured audio and inform the user upon return that an incomplete recording exists.
- What happens when the audio is very long (e.g., 60+ minutes)? The system MUST NOT block the UI; it MUST show progress and allow the user to continue using other parts of the app.
- What happens when the user tries to export a conversation with no summary yet? The system MUST either generate the summary first or export only the available content with a note that the summary is pending.
- What happens when a pipeline step fails (e.g., diarization errors out after transcription succeeds)? The system MUST show results from completed steps, clearly indicate the failed step, and offer a "Retry" action for the failed step without re-running earlier successful steps.
- What happens when the user enters a speaker count above 10? The system MUST reject the value and display a message stating that the supported range is 1–10 speakers.
- What happens when the AI service is completely down (not just rate-limited)? The system MUST display a clear "Service unavailable — please try again later" message with a "Retry" button for new processing. Audio MUST be saved locally so no data is lost. Already-processed conversations MUST remain fully browsable, with a banner indicating that new processing is temporarily unavailable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow the user to record audio directly in the browser using a built-in recorder.
- **FR-002**: System MUST allow the user to upload audio files in common formats (WAV, MP3, M4A, WEBM, OGG at minimum).
- **FR-003**: System MUST display a consent notice before recording begins or before an uploaded file is processed, per constitution principle VII.
- **FR-004**: System MUST allow the user to optionally enter a speaker count (1–10) before processing; the default MUST be "unknown". The system MUST reject values above 10 with a message explaining the supported range.
- **FR-005**: System MUST validate uploaded files for type and size, rejecting unsupported types and files exceeding the size limit with a clear, specific error message.
- **FR-006**: System MUST convert audio to a full transcript with word-level or segment-level timestamps.
- **FR-007**: System MUST support transcription in English, Hindi, and Gujarati, including mixed-language (code-switched) speech where the underlying model supports it.
- **FR-008**: System MUST separate the transcript into speaker-attributed segments (diarization) for up to 10 speakers, using the user-provided speaker count as a hint.
- **FR-009**: System MUST display each transcript segment with a speaker label, speaker-specific color, and start/end timestamps.
- **FR-010**: System MUST render a timeline visualization with one lane per speaker showing spoken intervals.
- **FR-011**: System MUST allow audio playback from any point by clicking a transcript segment or timeline block.
- **FR-012**: System MUST visually indicate segments where speaker-separation confidence is low.
- **FR-013**: System MUST allow the user to rename any speaker; the new name MUST propagate instantly to the transcript, timeline, analytics, and summary without a page reload.
- **FR-014**: System MUST allow the user to reassign a segment to a different speaker.
- **FR-015**: System MUST allow the user to edit transcript text inline.
- **FR-016**: System MUST compute and display per-speaker analytics: talk-time share (percentage), number of turns, average turn length, and interruption count.
- **FR-017**: System MUST, when the conversation is identified or tagged as a debate, extract and display key claims or arguments per speaker.
- **FR-018**: System MUST generate a conversation summary including key points, decisions, and action items with owners when mentioned. After initial generation, speaker renames MUST be substituted instantly in the existing summary text without an API call.
- **FR-028**: System MUST display a "Regenerate Summary" button when the transcript text has been edited after the last summary generation. Full re-summarization MUST only occur when the user clicks this button.
- **FR-019**: System MUST persist conversations locally so the user can revisit them in a history view.
- **FR-020**: System MUST allow the user to permanently delete a conversation and its associated audio from local storage.
- **FR-021**: System MUST allow the user to export a conversation's transcript and summary as a PDF document.
- **FR-022**: System MUST allow the user to export a conversation's transcript and summary as a plain-text file.
- **FR-023**: System MUST show a multi-step progress indicator reflecting the pipeline states (Uploading → Transcribing → Diarizing → Analyzing → Summarizing → Complete), with each step's status visible to the user, and MUST NOT block the UI during long operations.
- **FR-027**: System MUST support partial failure recovery: if any pipeline step fails after a previous step succeeded, the system MUST display the results produced so far and offer the user an option to retry the failed step.
- **FR-024**: System MUST support light mode and dark mode with a consistent design system.
- **FR-025**: System MUST handle free-tier API rate limits gracefully, notifying the user with estimated wait time or retry guidance.
- **FR-029**: System MUST, when the AI service is completely unreachable, display a clear "Service unavailable" error with a "Retry" button for any pending processing. Audio MUST be preserved locally. Already-processed conversations MUST remain fully accessible. A persistent banner MUST indicate that new processing is temporarily unavailable.
- **FR-030**: System MUST use a single-page navigation structure with three views: (1) a Landing screen for recording or uploading audio, (2) a Results page with switchable tabs for Transcript (including timeline), Analytics, and Summary, and (3) a History page listing past conversations. A persistent navigation bar MUST provide access to the Landing and History views.
- **FR-026**: System MUST store all data locally by default and MUST NOT send data to third-party services beyond the chosen AI API without explicit disclosure and consent.

### Key Entities

- **Conversation**: Represents a single recorded or uploaded audio session. Attributes: unique identifier, title (auto-generated or user-defined), creation date, duration, speaker count hint, processing status. Processing status follows a state machine: Uploading → Transcribing → Diarizing → Analyzing → Summarizing → Complete. A conversation may also enter a Failed state from any processing step, retaining results from prior completed steps.
- **AudioFile**: The raw audio data associated with a conversation. Attributes: format, size, duration, local storage reference.
- **Transcript**: The complete text output of transcription. Composed of an ordered list of Segments.
- **Segment**: A single contiguous spoken interval. Attributes: speaker reference, start time, end time, text content, confidence score, language detected.
- **Speaker**: A participant in the conversation. Attributes: system-assigned identifier (Speaker 1, 2, …, up to Speaker 10), user-assigned display name, associated color. The system MUST maintain a palette of at least 10 visually distinct colors.
- **Analytics**: Computed metrics for a conversation. Attributes: per-speaker talk-time, turn count, average turn length, interruption count, debate claims (when applicable).
- **Summary**: AI-generated summary of the conversation. Attributes: overview paragraph, key points list, decisions list, action items with owners.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A 10-minute conversation with 2–4 speakers processes end-to-end (upload → transcript → diarization → analytics → summary) without manual intervention.
- **SC-002**: Renaming a speaker updates all views (transcript, timeline, analytics, summary) within 1 second with no page reload.
- **SC-003**: The user is clearly informed whenever speaker-separation confidence is low for any segment.
- **SC-004**: The system rejects unsupported or oversized files before processing begins, with a user-readable error message that names the specific issue.
- **SC-005**: Audio processing for a 10-minute file does not freeze or block the UI at any point; the user can see progress and interact with other parts of the application.
- **SC-006**: The consent notice appears before any audio capture or processing begins, and processing does not start until the user grants consent.
- **SC-007**: A user can record, process, review, correct, and export a conversation in a single session without encountering a dead-end or ambiguous state.
- **SC-008**: Deleting a conversation removes all associated data (audio, transcript, analytics, summary) permanently, with nothing recoverable from local storage.
- **SC-009**: The interface is usable on screen widths from 360 px (mobile) to 1920 px (desktop) without loss of functionality.
- **SC-010**: Light and dark modes are both fully styled; no unstyled or unreadable elements exist in either mode.

## Assumptions

- Users have a modern browser (Chrome, Firefox, Edge, Safari latest two major versions) with Web Audio API and MediaRecorder support.
- The platform runs entirely in the browser with local storage; no user accounts or server-side databases are needed for the initial version.
- Audio files up to 25 MB (approximately 30 minutes of compressed audio) are within the expected usage range; the exact limit will be determined by the free-tier constraints of the chosen transcription service.
- The underlying transcription and diarization models are accessed via free-tier AI APIs; quality of multilingual and code-mixed transcription depends on model capabilities and is disclosed to the user.
- Real-time live transcription, user accounts, team sharing, and video processing are explicitly out of scope.
- Debate detection (whether a conversation is a "debate") will initially rely on user tagging rather than automatic detection.
- Export as PDF will use a client-side generation approach; no server-side rendering is required.
