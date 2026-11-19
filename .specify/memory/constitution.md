<!--
## Sync Impact Report
- Version change: 0.0.0 (template) → 1.0.0 (initial ratification)
- Added principles:
  1. Professional Product Quality
  2. Zero-Cost Constraint
  3. Library-First Architecture
  4. Test-Driven Development
  5. Automation at Every Level
  6. Functional Programming Preference
  7. Privacy and Consent by Design
  8. Honest AI Output
  9. World-Class UI/UX
  10. Security and Performance by Design
  11. AI-Assisted Development
  12. Simplicity and Maintainability
- Added sections: Security & Performance Constraints, Development Workflow
- Removed sections: none (initial constitution)
- Follow-up TODOs: none
-->

# Meeting Intelligence Platform Constitution

## Core Principles

### I. Professional Product Quality

All code MUST be production-quality, maintainable, secure, and performant.
Every module MUST be easy to evolve without cascading rewrites.
Over-engineering MUST be avoided — build only what is needed now, with
clear extension points for what is needed next.

### II. Zero-Cost Constraint

Every external dependency MUST have a genuinely free option (no credit
card required, no trial-only tiers). Free-tier limits (API rate limits,
file-size caps, storage quotas) MUST be handled gracefully with clear,
actionable user messages. If a free tier is exhausted, the application
MUST degrade visibly rather than fail silently.

### III. Library-First Architecture

Each significant feature — transcription, speaker diarization, transcript
merging, speaker renaming, analytics, and summarization — MUST be a
standalone, reusable, independently testable module. Business logic MUST
live in these library modules, never in UI components or route handlers.
A module MUST NOT depend on framework internals outside its boundary.

### IV. Test-Driven Development

The RED → GREEN → REFACTOR cycle MUST be followed where practical. Tests
MUST be written before or alongside the implementation they verify. AI
model calls MUST be wrapped behind interfaces so tests can substitute
mocks and small fixture audio files. Untested code MUST NOT be merged
into the main branch.

### V. Automation at Every Level

Automated unit, module, integration, API, and end-to-end tests MUST
exist for every feature. Critical user journeys (record → transcribe →
review → correct → export) MUST have automated tests. Quality checks
(linting, type-checking, test suites) MUST run automatically on every
commit or pull request.

### VI. Functional Programming Preference

Pure functions, immutability, composition, and explicit inputs/outputs
MUST be preferred over mutable state and side effects. Side effects
(network, file I/O, recording) MUST be isolated at the boundary of the
system and MUST NOT be interleaved with business logic.

### VII. Privacy and Consent by Design

A clear consent notice MUST be displayed before any recording or file
upload begins. Data MUST be stored locally by default. Users MUST be
able to permanently delete any conversation and its associated audio at
any time. Data MUST NOT be sent to third-party services beyond the
user-chosen AI API without explicit disclosure and consent.

### VIII. Honest AI Output

Speaker diarization and transcription are inherently imperfect. The UI
MUST NOT present AI-generated output as certain or final. Confidence
indicators SHOULD be shown where the underlying model provides them.
Users MUST be able to correct speaker labels and edit transcript text
directly.

### IX. World-Class UI/UX

The interface MUST be modern, polished, responsive, and accessible
(WCAG 2.1 AA minimum). A consistent design system with design tokens
MUST be maintained. Light and dark modes MUST both be supported. Every
async operation MUST have clear loading, error, and empty states. A
consistent icon set MUST be used — emojis MUST NOT be used as icons.

### X. Security and Performance by Design

All uploads MUST be validated for type and size before processing. Long
audio processing MUST NOT block the UI thread. Input sanitization and
output encoding MUST be applied to prevent injection attacks.
Accessibility (keyboard navigation, screen-reader labels, sufficient
contrast) MUST be considered from the start, not retrofitted.

### XI. AI-Assisted Development

AI-generated code MUST follow the same architecture, testing, security,
and quality standards as manually written code. No exception is granted
for code origin — every contribution MUST pass the same review and
automation gates.

### XII. Simplicity and Maintainability

Simple, clear, modular solutions MUST be preferred over clever or
abstract ones. If a simpler approach satisfies the requirements, the
simpler approach MUST be chosen. Code MUST be readable by a developer
unfamiliar with the project within a reasonable time.

## Security & Performance Constraints

- **Upload validation**: MIME type whitelist and maximum file-size
  enforcement MUST reject invalid uploads before any processing begins.
- **Non-blocking processing**: Audio transcription and diarization MUST
  run in background workers or Web Workers to keep the UI responsive.
- **Rate-limit handling**: When a free-tier API rate limit is hit, the
  application MUST queue or retry with exponential back-off and notify
  the user with estimated wait time.
- **Data at rest**: Locally stored audio and transcripts MUST reside in
  user-controlled storage (IndexedDB / filesystem). No sensitive data
  MUST be written to shared or world-readable locations.
- **Dependency hygiene**: All third-party packages MUST be audited for
  known vulnerabilities before adoption and MUST be kept up to date.

## Development Workflow

- **Branching**: Feature branches MUST be created for every change.
  Direct pushes to the main branch MUST NOT occur.
- **Commit standards**: Conventional Commits format MUST be used.
- **Quality gates**: Linting, type-checking, and the full test suite
  MUST pass before a branch is eligible for merge.
- **Code review**: Every pull request MUST be reviewed (self-review
  minimum for solo work) against this constitution's principles before
  merge.
- **Documentation**: Public APIs and non-obvious design decisions MUST
  be documented in code or in companion docs at the time of
  implementation, not deferred.

## Governance

This constitution is the supreme governing document for the Meeting
Intelligence Platform project. All code, reviews, and architectural
decisions MUST comply with the principles defined above.

- **Amendments**: Any change to this constitution MUST be documented
  with a rationale, reviewed, and accompanied by a migration plan if
  existing code is affected.
- **Versioning**: The constitution follows semantic versioning —
  MAJOR for principle removals or incompatible redefinitions, MINOR for
  new principles or material expansions, PATCH for clarifications and
  wording fixes.
- **Compliance review**: Every pull request or code review MUST verify
  alignment with these principles. Deviations MUST be justified in
  writing and approved before merge.

**Version**: 1.0.0 | **Ratified**: 2026-10-13 | **Last Amended**: 2026-10-13
