"""Transcript–speaker merging module.

Pure function — no I/O, no side effects. Independently testable.
Assigns each TranscriptSegment to the speaker with the maximum time overlap.
"""

from __future__ import annotations

from app.models import LabelledSegment, SpeakerInterval, TranscriptSegment


def _overlap(seg_start: float, seg_end: float, iv_start: float, iv_end: float) -> float:
    """Return the duration of overlap between two time intervals."""
    start = max(seg_start, iv_start)
    end = min(seg_end, iv_end)
    return max(0.0, end - start)


def merge(
    segments: list[TranscriptSegment],
    diarization: list[SpeakerInterval],
    low_confidence_threshold: float = 0.5,
) -> list[LabelledSegment]:
    """Merge transcript segments with diarization speaker intervals.

    For each transcript segment, find the speaker interval with the largest
    time overlap. If no overlap is found, label as "UNKNOWN" with low
    confidence.

    Args:
        segments: Timestamped transcript segments from Whisper.
        diarization: Speaker-labelled intervals from pyannote.
        low_confidence_threshold: Minimum overlap ratio to consider confident.

    Returns:
        A list of LabelledSegment with speaker assignments.
    """
    result: list[LabelledSegment] = []

    for seg in segments:
        seg_duration = seg.end - seg.start
        if seg_duration <= 0:
            result.append(
                LabelledSegment(segment=seg, speaker_label="UNKNOWN", is_low_confidence=True)
            )
            continue

        best_speaker = "UNKNOWN"
        best_overlap = 0.0

        for iv in diarization:
            ov = _overlap(seg.start, seg.end, iv.start, iv.end)
            if ov > best_overlap:
                best_overlap = ov
                best_speaker = iv.speaker_label

        overlap_ratio = best_overlap / seg_duration if seg_duration > 0 else 0.0
        is_low = best_speaker == "UNKNOWN" or overlap_ratio < low_confidence_threshold

        result.append(
            LabelledSegment(
                segment=seg,
                speaker_label=best_speaker,
                is_low_confidence=is_low,
            )
        )

    return result
