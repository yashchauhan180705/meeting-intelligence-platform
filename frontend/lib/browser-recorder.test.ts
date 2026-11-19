import { describe, expect, it } from "vitest";
import {
  chooseRecordingMimeType,
  createRecordingFile,
  fallbackRecordingMimeType,
} from "./browser-recorder";

describe("browser recording helpers", () => {
  it("prefers an Opus WebM format supported by the browser", () => {
    const supported = chooseRecordingMimeType((mimeType) =>
      mimeType === "audio/webm;codecs=opus",
    );

    expect(supported).toBe("audio/webm;codecs=opus");
  });

  it("falls back to plain WebM when MIME support is unavailable", () => {
    expect(chooseRecordingMimeType()).toBe(fallbackRecordingMimeType);
    expect(chooseRecordingMimeType(() => false)).toBe(
      fallbackRecordingMimeType,
    );
  });

  it("creates an uploadable file from recorded chunks", async () => {
    const file = createRecordingFile(
      [new Blob(["first"]), new Blob(["second"])],
      "audio/webm",
    );

    expect(file.name).toBe("browser-recording.webm");
    expect(file.type).toBe("audio/webm");
    expect(file.size).toBe(11);
    await expect(file.text()).resolves.toBe("firstsecond");
  });
});
