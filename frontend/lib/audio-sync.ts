export type TimedSegment = {
  id: string;
  start_time: number;
  end_time: number;
};

export function findActiveSegment(
  segments: TimedSegment[],
  currentTime: number,
): string | null {
  const active = segments.find(
    (segment) =>
      currentTime >= segment.start_time && currentTime < segment.end_time,
  );
  return active?.id ?? null;
}

export function timelinePosition(
  time: number,
  duration: number,
): number {
  if (duration <= 0) return 0;
  return Math.min(100, Math.max(0, (time / duration) * 100));
}
