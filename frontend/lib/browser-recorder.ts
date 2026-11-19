const recordingMimeTypes = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
];

export const fallbackRecordingMimeType = "audio/webm";

export function chooseRecordingMimeType(
  isTypeSupported?: (mimeType: string) => boolean,
): string {
  if (!isTypeSupported) return fallbackRecordingMimeType;

  return (
    recordingMimeTypes.find((mimeType) => isTypeSupported(mimeType)) ??
    fallbackRecordingMimeType
  );
}

export function createRecordingFile(
  chunks: Blob[],
  mimeType: string,
  filename = "browser-recording.webm",
): File {
  const type = mimeType || fallbackRecordingMimeType;
  return new File([new Blob(chunks, { type })], filename, { type });
}
