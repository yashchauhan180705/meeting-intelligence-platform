"""Analytics computation module.

Pure function — no I/O. Computes per-speaker talk-time, turns,
average turn length, and interruptions from labelled segments.
"""

from __future__ import annotations

from collections import defaultdict

from app.models import Analytics, LabelledSegment, SpeakerMetric


def compute_analytics(
    labelled_segments: list[LabelledSegment],
    total_duration: float,
) -> Analytics:
    """Compute per-speaker analytics from labelled transcript segments.

    Args:
        labelled_segments: Merged segments with speaker labels.
        total_duration: Total audio duration in seconds.

    Returns:
        Analytics with per-speaker metrics.
    """
    if not labelled_segments or total_duration <= 0:
        return Analytics(
            total_duration_seconds=max(total_duration, 0.0),
            interruption_count=0,
            speaker_metrics=[],
        )

    # Accumulate per-speaker data
    talk_time: dict[str, float] = defaultdict(float)
    turn_count: dict[str, int] = defaultdict(int)

    for seg in labelled_segments:
        duration = seg.segment.end - seg.segment.start
        talk_time[seg.speaker_label] += max(duration, 0.0)
        turn_count[seg.speaker_label] += 1

    # Count interruptions (overlapping segments from different speakers)
    interruptions: dict[str, int] = defaultdict(int)
    total_interruptions = 0
    sorted_segs = sorted(labelled_segments, key=lambda s: s.segment.start)

    for i in range(1, len(sorted_segs)):
        prev = sorted_segs[i - 1]
        curr = sorted_segs[i]
        if (
            curr.speaker_label != prev.speaker_label
            and curr.segment.start < prev.segment.end
        ):
            interruptions[curr.speaker_label] += 1
            total_interruptions += 1

    # Build metrics
    total_talk = sum(talk_time.values()) or 1.0  # avoid div-by-zero
    metrics: list[SpeakerMetric] = []

    for speaker in sorted(talk_time.keys()):
        tt = talk_time[speaker]
        tc = turn_count[speaker]
        metrics.append(
            SpeakerMetric(
                speaker_label=speaker,
                talk_time_seconds=round(tt, 2),
                talk_time_pct=round((tt / total_talk) * 100, 1),
                turn_count=tc,
                avg_turn_length_seconds=round(tt / tc, 2) if tc > 0 else 0.0,
                interruption_count=interruptions.get(speaker, 0),
            )
        )

    return Analytics(
        total_duration_seconds=round(total_duration, 2),
        interruption_count=total_interruptions,
        speaker_metrics=metrics,
    )
