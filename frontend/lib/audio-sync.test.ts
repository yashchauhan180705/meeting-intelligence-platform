import { describe, expect, it } from "vitest";
import { findActiveSegment, timelinePosition } from "./audio-sync";

describe("audio synchronization", () => {
  const segments = [
    { id: "first", start_time: 0, end_time: 3 },
    { id: "second", start_time: 3, end_time: 6 },
  ];

  it("selects the segment at the current playback time", () => {
    expect(findActiveSegment(segments, 0)).toBe("first");
    expect(findActiveSegment(segments, 3)).toBe("second");
    expect(findActiveSegment(segments, 8)).toBeNull();
  });

  it("clamps timeline percentages to the track", () => {
    expect(timelinePosition(5, 10)).toBe(50);
    expect(timelinePosition(-1, 10)).toBe(0);
    expect(timelinePosition(11, 10)).toBe(100);
    expect(timelinePosition(1, 0)).toBe(0);
  });
});
