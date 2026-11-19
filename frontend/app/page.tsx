"use client";

import { useEffect, useRef, useState } from "react";
import { findActiveSegment, timelinePosition } from "../lib/audio-sync";
import {
  chooseRecordingMimeType,
  createRecordingFile,
} from "../lib/browser-recorder";

type Speaker = {
  id: string;
  system_label: string;
  display_name: string;
  color_index: number;
};

type Segment = {
  id: string;
  speaker_id: string;
  start_time: number;
  end_time: number;
  text: string;
  speaker_display_name: string;
  speaker_color_index: number;
  is_low_confidence: boolean;
};

type ActionItem = {
  text: string;
  owner?: string | null;
};

type DebateClaim = {
  speaker: string;
  claim: string;
};

type Summary = {
  overview: string;
  key_points: string[];
  decisions?: string[];
  action_items?: ActionItem[];
  debate_claims?: DebateClaim[] | null;
  transcript_hash?: string;
};

type SpeakerMetric = {
  speaker_display_name: string;
  speaker_color_index?: number;
  talk_time_seconds: number;
  talk_time_pct: number;
  turn_count: number;
  avg_turn_length_seconds: number;
  interruption_count: number;
};

type Analytics = {
  total_duration_seconds: number;
  interruption_count: number;
  speaker_metrics: SpeakerMetric[];
};

type Conversation = {
  id: string;
  title: string;
  created_at?: string;
  processing_status: string;
  error_message?: string | null;
  is_debate?: boolean;
  speakers?: Speaker[];
  segments?: Segment[];
  summary?: Summary | null;
  analytics?: Analytics | null;
};

type HistoryItem = {
  id: string;
  title: string;
  created_at: string;
  duration_seconds: number | null;
  processing_status: string;
  is_debate?: boolean;
  speaker_display_names: string[];
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const allowedTypes = ".wav,.mp3,.m4a,.webm,.ogg";
const PIPELINE_STEPS = ["uploading", "transcribing", "diarizing", "analyzing", "summarizing", "complete"];

function extractErrorMessage(caught: unknown, fallback: string): string {
  if (caught instanceof Error) return caught.message;
  if (typeof caught === "string") return caught;
  return fallback;
}

async function parseApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (data.detail?.message) return data.detail.message;
    if (Array.isArray(data.detail)) {
      return data.detail.map((e: { msg?: string }) => e.msg || "Invalid input").join(", ");
    }
    if (data.message) return data.message;
    if (data.error) return String(data.error);
  } catch {
    // If not JSON
  }
  return `${fallback} (HTTP ${response.status})`;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [recordedAudioUrl, setRecordedAudioUrl] = useState<string | null>(null);
  const [speakerCount, setSpeakerCount] = useState("");
  const [customTitle, setCustomTitle] = useState("");
  const [isDebate, setIsDebate] = useState(false);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState<"transcript" | "analytics" | "summary" | "export">("transcript");
  const [activeSegmentId, setActiveSegmentId] = useState<string | null>(null);
  const [audioDuration, setAudioDuration] = useState(0);
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [segmentDraft, setSegmentDraft] = useState("");
  const [segmentSpeakerDraft, setSegmentSpeakerDraft] = useState("");
  const [speakerDrafts, setSpeakerDrafts] = useState<Record<string, string>>({});
  const [summaryDirty, setSummaryDirty] = useState(false);
  const [view, setView] = useState<"landing" | "history">("landing");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [consentOpen, setConsentOpen] = useState(false);
  const [consentAction, setConsentAction] = useState<"upload" | "record">("upload");
  const [consentGranted, setConsentGranted] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function clearPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function clearRecordingTimer() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  useEffect(() => {
    return () => {
      clearPolling();
      clearRecordingTimer();
      mediaRecorderRef.current?.stop();
      recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
      if (recordedAudioUrl) URL.revokeObjectURL(recordedAudioUrl);
    };
  }, [recordedAudioUrl]);

  function startPolling(conversationId: string) {
    clearPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${apiUrl}/conversations/${conversationId}`);
        if (!res.ok) {
          throw new Error("Could not check processing status.");
        }
        const data: Conversation = await res.json();
        setConversation(data);
        if (data.processing_status === "complete" || data.processing_status === "failed") {
          clearPolling();
          setBusy(false);
          if (data.processing_status === "failed") {
            setError(data.error_message || "Processing encountered an issue.");
          }
        }
      } catch (caught) {
        clearPolling();
        setBusy(false);
        setError(extractErrorMessage(caught, "Status polling failed."));
      }
    }, 1200);
  }

  async function startProcessing() {
    if (!file) {
      setError("Please choose or record an audio file first.");
      return;
    }
    if (!consentGranted) {
      setConsentAction("upload");
      setConsentOpen(true);
      return;
    }
    await uploadAndProcess(file);
  }

  async function uploadAndProcess(selectedFile: File) {
    clearPolling();
    setError("");
    setBusy(true);

    try {
      const form = new FormData();
      form.append("audio_file", selectedFile);
      if (speakerCount) form.append("speaker_count_hint", speakerCount);
      if (customTitle.trim()) form.append("title", customTitle.trim());
      form.append("is_debate", isDebate ? "true" : "false");

      const uploadRes = await fetch(`${apiUrl}/conversations`, { method: "POST", body: form });
      if (!uploadRes.ok) {
        const msg = await parseApiError(uploadRes, "Upload failed");
        throw new Error(msg);
      }
      const uploadData = await uploadRes.json();
      setConversation(uploadData);

      const processRes = await fetch(`${apiUrl}/conversations/${uploadData.id}/process`, { method: "POST" });
      if (!processRes.ok) {
        const msg = await parseApiError(processRes, "Could not start AI pipeline");
        throw new Error(msg);
      }

      startPolling(uploadData.id);
    } catch (caught) {
      clearPolling();
      setBusy(false);
      setError(extractErrorMessage(caught, "Processing failed."));
    }
  }

  async function beginRecording() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("In-browser recording is not supported in this environment. Please upload an audio file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = chooseRecordingMimeType(
        typeof MediaRecorder.isTypeSupported === "function"
          ? MediaRecorder.isTypeSupported.bind(MediaRecorder)
          : undefined,
      );
      const recorder = new MediaRecorder(stream, { mimeType });
      recordingChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordingChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const createdFile = createRecordingFile(recordingChunksRef.current, recorder.mimeType);
        setFile(createdFile);
        const url = URL.createObjectURL(createdFile);
        setRecordedAudioUrl(url);
        setRecording(false);
        clearRecordingTimer();
        stream.getTracks().forEach((track) => track.stop());
        recordingStreamRef.current = null;
      };
      mediaRecorderRef.current = recorder;
      recordingStreamRef.current = stream;
      recorder.start(500);
      setRecording(true);
      setRecordSeconds(0);
      setError("");

      timerRef.current = setInterval(() => {
        setRecordSeconds((prev) => prev + 1);
      }, 1000);
    } catch {
      setError("Microphone permission was denied or no recording device was found.");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
  }

  function discardRecording() {
    setFile(null);
    if (recordedAudioUrl) {
      URL.revokeObjectURL(recordedAudioUrl);
      setRecordedAudioUrl(null);
    }
    setRecordSeconds(0);
  }

  function confirmConsent() {
    setConsentGranted(true);
    setConsentOpen(false);
    if (consentAction === "record") {
      void beginRecording();
    } else if (file) {
      void uploadAndProcess(file);
    }
  }

  async function updateSpeaker(speakerId: string) {
    const displayName = speakerDrafts[speakerId]?.trim();
    if (!displayName || !conversation) return;
    try {
      const response = await fetch(
        `${apiUrl}/conversations/${conversation.id}/speakers/${speakerId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ display_name: displayName }),
        },
      );
      if (!response.ok) {
        const msg = await parseApiError(response, "Could not rename speaker");
        throw new Error(msg);
      }
      const refetch = await fetch(`${apiUrl}/conversations/${conversation.id}`);
      if (refetch.ok) setConversation(await refetch.json());
    } catch (caught) {
      setError(extractErrorMessage(caught, "Speaker rename failed."));
    }
  }

  async function saveSegment(segmentId: string) {
    if (!conversation) return;
    try {
      const response = await fetch(
        `${apiUrl}/conversations/${conversation.id}/segments/${segmentId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: segmentDraft, speaker_id: segmentSpeakerDraft }),
        },
      );
      if (!response.ok) {
        const msg = await parseApiError(response, "Could not save transcript correction");
        throw new Error(msg);
      }
      const refetch = await fetch(`${apiUrl}/conversations/${conversation.id}`);
      if (refetch.ok) setConversation(await refetch.json());
      setEditingSegmentId(null);
      setSummaryDirty(true);
    } catch (caught) {
      setError(extractErrorMessage(caught, "Segment update failed."));
    }
  }

  async function regenerateSummary() {
    if (!conversation) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/conversations/${conversation.id}/summary/regenerate`, {
        method: "POST",
      });
      if (!response.ok) {
        const msg = await parseApiError(response, "Could not regenerate summary");
        throw new Error(msg);
      }
      const refetch = await fetch(`${apiUrl}/conversations/${conversation.id}`);
      if (refetch.ok) setConversation(await refetch.json());
      setSummaryDirty(false);
    } catch (caught) {
      setError(extractErrorMessage(caught, "Summary regeneration failed."));
    } finally {
      setBusy(false);
    }
  }

  async function retryProcessing(conversationId: string) {
    setError("");
    setBusy(true);
    try {
      const processRes = await fetch(`${apiUrl}/conversations/${conversationId}/process`, { method: "POST" });
      if (!processRes.ok) {
        const msg = await parseApiError(processRes, "Could not restart AI pipeline");
        throw new Error(msg);
      }
      startPolling(conversationId);
    } catch (caught) {
      setBusy(false);
      setError(extractErrorMessage(caught, "Retry failed."));
    }
  }

  async function showHistory() {
    setView("history");
    setError("");
    try {
      const response = await fetch(`${apiUrl}/conversations`);
      if (response.ok) {
        const data = await response.json();
        setHistory(data.items || []);
      } else {
        const msg = await parseApiError(response, "Could not load history");
        setError(msg);
      }
    } catch (caught) {
      setError(extractErrorMessage(caught, "Could not connect to backend server."));
    }
  }

  async function openConversation(id: string) {
    setError("");
    try {
      const response = await fetch(`${apiUrl}/conversations/${id}`);
      if (!response.ok) {
        const msg = await parseApiError(response, "Could not open conversation");
        throw new Error(msg);
      }
      const item: Conversation = await response.json();
      setConversation(item);
      setView("landing");
      if (item.processing_status !== "complete" && item.processing_status !== "failed") {
        setBusy(true);
        startPolling(item.id);
      }
    } catch (caught) {
      setError(extractErrorMessage(caught, "Could not open conversation."));
    }
  }

  async function deleteConversation(id: string) {
    if (!window.confirm("Permanently delete this conversation, its audio, and AI analytics?")) return;
    try {
      const response = await fetch(`${apiUrl}/conversations/${id}`, { method: "DELETE" });
      if (response.ok) {
        setHistory(history.filter((item) => item.id !== id));
      } else {
        const msg = await parseApiError(response, "Delete failed");
        setError(msg);
      }
    } catch (caught) {
      setError(extractErrorMessage(caught, "Delete operation failed."));
    }
  }

  function downloadExport(format: "text" | "json") {
    if (!conversation) return;
    window.open(`${apiUrl}/conversations/${conversation.id}/export?format=${format}`, "_blank");
  }

  const currentStepIndex = conversation ? PIPELINE_STEPS.indexOf(conversation.processing_status) : -1;

  // Render Completed Conversation Results (or partial if segments exist)
  if (conversation?.processing_status === "complete" || (conversation?.segments && conversation.segments.length > 0)) {
    const segments = conversation.segments ?? [];
    const speakerMap = new Map((conversation.speakers ?? []).map((s) => [s.id, s]));

    const seekTo = (time: number, segmentId: string) => {
      if (!audioRef.current) return;
      audioRef.current.currentTime = time;
      void audioRef.current.play();
      setActiveSegmentId(segmentId);
    };

    return (
      <main className="shell">
        <header className="top-header">
          <div className="brand-group">
            <div className="logo-badge">🎙️</div>
            <div className="brand-text">
              <h1>Meeting & Debate Intelligence</h1>
              <span className="brand-sub">Speaker Diarization & Insights</span>
            </div>
          </div>
          <nav className="nav">
            <button className="nav-button" onClick={() => { setConversation(null); setFile(null); setView("landing"); }}>
              + New Conversation
            </button>
            <button className="nav-button" onClick={showHistory}>
              History
            </button>
          </nav>
        </header>

        <div className="results-header">
          <div>
            <h1 style={{ fontSize: "2rem", marginBottom: "8px" }}>{conversation.title}</h1>
            <div className="results-meta">
              <span className="mode-badge">{conversation.is_debate ? "Debate Mode" : "Meeting Mode"}</span>
              <span>•</span>
              <span>{segments.length} segments</span>
              <span>•</span>
              <span>{conversation.speakers?.length || 0} speakers</span>
              {conversation.analytics && (
                <>
                  <span>•</span>
                  <span>{conversation.analytics.total_duration_seconds.toFixed(1)}s duration</span>
                </>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <button className="btn-secondary btn-sm" onClick={() => downloadExport("text")}>Export Text</button>
            <button className="btn-secondary btn-sm" onClick={() => downloadExport("json")}>Export JSON</button>
          </div>
        </div>

        {error && <div className="alert-error"><span>⚠️</span> {error}</div>}

        {/* Audio Player */}
        <section className="card player-card">
          <audio
            ref={audioRef}
            controls
            preload="metadata"
            src={`${apiUrl}/conversations/${conversation.id}/audio`}
            onLoadedMetadata={(event) => setAudioDuration(event.currentTarget.duration)}
            onTimeUpdate={(event) => {
              setActiveSegmentId(findActiveSegment(segments, event.currentTarget.currentTime));
            }}
          />
        </section>

        {/* Tabs Bar */}
        <div className="tabs-bar">
          <button
            className={`tab-btn ${activeTab === "transcript" ? "active" : ""}`}
            onClick={() => setActiveTab("transcript")}
          >
            🎙️ Transcript & Timeline
          </button>
          <button
            className={`tab-btn ${activeTab === "analytics" ? "active" : ""}`}
            onClick={() => setActiveTab("analytics")}
          >
            📊 Analytics & Talk Time
          </button>
          <button
            className={`tab-btn ${activeTab === "summary" ? "active" : ""}`}
            onClick={() => setActiveTab("summary")}
          >
            🧠 AI Intelligence & Summary
          </button>
          <button
            className={`tab-btn ${activeTab === "export" ? "active" : ""}`}
            onClick={() => setActiveTab("export")}
          >
            💾 Export
          </button>
        </div>

        {/* Tab 1: Transcript & Timeline */}
        {activeTab === "transcript" && (
          <>
            {/* Timeline */}
            <section className="card timeline-card">
              <h2><span>⏱️</span> Speaker Timeline</h2>
              <div className="timeline">
                {(conversation.speakers ?? []).map((speaker) => (
                  <div className="timeline-lane" key={speaker.id}>
                    <div className="lane-speaker-tag">
                      <span className="speaker-color-dot" style={{ backgroundColor: `var(--speaker-${speaker.color_index})` }} />
                      <span>{speaker.display_name}</span>
                    </div>
                    <div className="lane-track">
                      {segments
                        .filter((s) => s.speaker_id === speaker.id)
                        .map((seg) => (
                          <button
                            key={seg.id}
                            className="timeline-block"
                            title={`${speaker.display_name} (${seg.start_time.toFixed(1)}s - ${seg.end_time.toFixed(1)}s)`}
                            style={{
                              left: `${timelinePosition(seg.start_time, audioDuration)}%`,
                              width: `${Math.max(0.6, timelinePosition(seg.end_time, audioDuration) - timelinePosition(seg.start_time, audioDuration))}%`,
                              backgroundColor: `var(--speaker-${speaker.color_index})`,
                            }}
                            onClick={() => seekTo(seg.start_time, seg.id)}
                          />
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Speaker Renaming */}
            <section className="card">
              <h2><span>👥</span> Identified Speakers</h2>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", marginBottom: "16px" }}>
                Edit speaker names below to update timestamps, analytics, and summaries across the platform:
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "12px" }}>
                {(conversation.speakers ?? []).map((speaker) => (
                  <div key={speaker.id} style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <span className="speaker-color-dot" style={{ backgroundColor: `var(--speaker-${speaker.color_index})` }} />
                    <input
                      style={{
                        background: "var(--bg-input)",
                        border: "1px solid var(--border-subtle)",
                        color: "var(--text-primary)",
                        padding: "8px 12px",
                        borderRadius: "8px",
                        flex: 1,
                        fontSize: "0.88rem",
                      }}
                      value={speakerDrafts[speaker.id] ?? speaker.display_name}
                      onChange={(e) => setSpeakerDrafts({ ...speakerDrafts, [speaker.id]: e.target.value })}
                    />
                    <button className="btn-secondary btn-sm" onClick={() => updateSpeaker(speaker.id)}>
                      Save
                    </button>
                  </div>
                ))}
              </div>
            </section>

            {/* Transcript */}
            <section className="card">
              <h2><span>📝</span> Diarized Transcript</h2>
              {segments.some((s) => s.is_low_confidence) && (
                <div className="alert-warning">
                  <span>ℹ️</span> Some segments have lower speaker-attribution confidence. Check the highlighted entries below.
                </div>
              )}
              <div className="transcript-card">
                {segments.map((seg, idx) => {
                  const speaker = speakerMap.get(seg.speaker_id);
                  const colorIdx = speaker?.color_index ?? seg.speaker_color_index ?? 0;
                  const isEditing = editingSegmentId === seg.id;

                  return (
                    <article
                      key={`${seg.id}-${idx}`}
                      className={`segment-item ${activeSegmentId === seg.id ? "active-segment" : ""}`}
                      onClick={() => seekTo(seg.start_time, seg.id)}
                    >
                      <div className="segment-header">
                        <div>
                          <span
                            className="speaker-badge"
                            style={{
                              borderLeftColor: `var(--speaker-${colorIdx})`,
                              color: `var(--speaker-${colorIdx})`,
                            }}
                          >
                            {seg.speaker_display_name}
                          </span>
                          {seg.is_low_confidence && <span className="low-confidence-tag">Review attribution</span>}
                        </div>
                        <span className="segment-time">
                          {seg.start_time.toFixed(1)}s - {seg.end_time.toFixed(1)}s
                        </span>
                      </div>

                      {isEditing ? (
                        <div className="segment-edit-box" onClick={(e) => e.stopPropagation()}>
                          <textarea
                            value={segmentDraft}
                            onChange={(e) => setSegmentDraft(e.target.value)}
                            placeholder="Transcript correction..."
                          />
                          <select
                            value={segmentSpeakerDraft}
                            onChange={(e) => setSegmentSpeakerDraft(e.target.value)}
                          >
                            {(conversation.speakers ?? []).map((spk) => (
                              <option key={spk.id} value={spk.id}>
                                {spk.display_name}
                              </option>
                            ))}
                          </select>
                          <div className="segment-actions">
                            <button className="btn-secondary btn-sm" onClick={() => setEditingSegmentId(null)}>
                              Cancel
                            </button>
                            <button className="btn-primary btn-sm" style={{ width: "auto" }} onClick={() => saveSegment(seg.id)}>
                              Save correction
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
                          <p className="segment-text">{seg.text}</p>
                          <button
                            className="btn-secondary btn-sm"
                            style={{ flexShrink: 0, opacity: 0.7 }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingSegmentId(seg.id);
                              setSegmentDraft(seg.text);
                              setSegmentSpeakerDraft(seg.speaker_id);
                            }}
                          >
                            Edit
                          </button>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          </>
        )}

        {/* Tab 2: Analytics */}
        {activeTab === "analytics" && (
          <section className="card">
            <h2><span>📊</span> Conversation Dynamics & Metrics</h2>
            {conversation.analytics ? (
              <>
                <div className="analytics-summary-cards">
                  <div className="stat-card">
                    <div className="stat-label">Total Duration</div>
                    <div className="stat-value">{conversation.analytics.total_duration_seconds.toFixed(1)}s</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Interruption Count</div>
                    <div className="stat-value">{conversation.analytics.interruption_count}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Active Speakers</div>
                    <div className="stat-value">{conversation.analytics.speaker_metrics.length}</div>
                  </div>
                </div>

                <h3 style={{ fontSize: "1.1rem", marginBottom: "14px" }}>Speaker Talk-Time Distribution</h3>
                <div className="speakers-metrics-list">
                  {conversation.analytics.speaker_metrics.map((metric, idx) => {
                    const colorIndex = idx % 10;
                    return (
                      <div className="speaker-metric-row" key={metric.speaker_display_name}>
                        <div className="metric-row-header">
                          <div>
                            <strong style={{ fontSize: "1rem", color: `var(--speaker-${colorIndex})` }}>
                              {metric.speaker_display_name}
                            </strong>
                            <span style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginLeft: "12px" }}>
                              {metric.turn_count} turns • {metric.avg_turn_length_seconds.toFixed(1)}s avg • {metric.interruption_count} interruptions
                            </span>
                          </div>
                          <span style={{ fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                            {metric.talk_time_pct.toFixed(1)}% ({metric.talk_time_seconds.toFixed(1)}s)
                          </span>
                        </div>
                        <div className="metric-progress-track">
                          <div
                            className="metric-progress-fill"
                            style={{
                              width: `${metric.talk_time_pct}%`,
                              backgroundColor: `var(--speaker-${colorIndex})`,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No analytics computed for this conversation.</p>
            )}
          </section>
        )}

        {/* Tab 3: AI Intelligence Summary */}
        {activeTab === "summary" && (
          <section className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2><span>🧠</span> Executive AI Intelligence</h2>
              {summaryDirty && (
                <button className="btn-primary btn-sm" style={{ width: "auto" }} onClick={regenerateSummary} disabled={busy}>
                  {busy ? "Regenerating..." : "Regenerate Summary"}
                </button>
              )}
            </div>

            {summaryDirty && (
              <div className="alert-warning">
                <span>⚠️</span> The transcript has been edited since this summary was created. Click "Regenerate Summary" to update.
              </div>
            )}

            {conversation.summary ? (
              <>
                <div className="summary-block">
                  <h3>Overview</h3>
                  <div className="summary-overview-box">{conversation.summary.overview}</div>
                </div>

                <div className="summary-block">
                  <h3>Key Discussion Points</h3>
                  <ul className="bullet-list">
                    {conversation.summary.key_points.map((pt, i) => (
                      <li key={i}>{pt}</li>
                    ))}
                  </ul>
                </div>

                {conversation.summary.decisions && conversation.summary.decisions.length > 0 && (
                  <div className="summary-block">
                    <h3>Decisions & Agreements</h3>
                    <ul className="bullet-list">
                      {conversation.summary.decisions.map((dec, i) => (
                        <li key={i}>{dec}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {conversation.summary.action_items && conversation.summary.action_items.length > 0 && (
                  <div className="summary-block">
                    <h3>Action Items</h3>
                    <div className="items-grid">
                      {conversation.summary.action_items.map((action, i) => (
                        <div className="item-badge-card" key={i}>
                          <span className="item-owner">{action.owner ? `👤 ${action.owner}` : "Unassigned"}</span>
                          <p style={{ fontSize: "0.92rem", color: "#e2e8f0" }}>{action.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {conversation.summary.debate_claims && conversation.summary.debate_claims.length > 0 && (
                  <div className="summary-block">
                    <h3>Debate Arguments & Claims</h3>
                    <div className="items-grid">
                      {conversation.summary.debate_claims.map((claim, i) => (
                        <div className="item-badge-card" key={i}>
                          <span className="item-owner">🗣️ {claim.speaker}</span>
                          <p style={{ fontSize: "0.92rem", color: "#e2e8f0" }}>{claim.claim}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={{ padding: "28px 20px", background: "rgba(99, 102, 241, 0.08)", border: "1px solid rgba(99, 102, 241, 0.2)", borderRadius: "12px", textAlign: "center" }}>
                <p style={{ color: "var(--text-secondary)", marginBottom: "16px", fontSize: "0.95rem" }}>
                  {conversation.error_message || "Summary is pending or was delayed due to AI rate limits."}
                </p>
                <button
                  className="btn-primary"
                  style={{ width: "auto", display: "inline-flex", margin: "0 auto", padding: "10px 24px" }}
                  onClick={regenerateSummary}
                  disabled={busy}
                >
                  {busy ? "Generating AI Summary..." : "⚡ Generate AI Summary Now"}
                </button>
              </div>
            )}
          </section>
        )}

        {/* Tab 4: Export */}
        {activeTab === "export" && (
          <section className="card">
            <h2><span>💾</span> Export Conversation Data</h2>
            <p style={{ color: "var(--text-secondary)", marginBottom: "20px" }}>
              Download complete conversation records including speaker attribution, timestamps, analytics, and summaries:
            </p>
            <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
              <button className="btn-primary" style={{ width: "auto" }} onClick={() => downloadExport("text")}>
                📄 Download Formatted Text (.txt)
              </button>
              <button className="btn-secondary" style={{ width: "auto" }} onClick={() => downloadExport("json")}>
                📦 Download Complete JSON (.json)
              </button>
            </div>
          </section>
        )}
      </main>
    );
  }

  // Render History View
  if (view === "history") {
    return (
      <main className="shell">
        <header className="top-header">
          <div className="brand-group">
            <div className="logo-badge">🎙️</div>
            <div className="brand-text">
              <h1>Meeting & Debate Intelligence</h1>
              <span className="brand-sub">Conversation Archive</span>
            </div>
          </div>
          <nav className="nav">
            <button className="nav-button" onClick={() => setView("landing")}>
              + New Conversation
            </button>
            <button className="nav-button active-nav">History</button>
          </nav>
        </header>

        <section className="card">
          <h2><span>📂</span> Conversation History</h2>
          {error && <div className="alert-error"><span>⚠️</span> {error}</div>}
          {history.length === 0 && !error && (
            <p style={{ color: "var(--text-muted)", padding: "20px 0" }}>No processed conversations found yet.</p>
          )}
          {history.map((item) => (
            <article className="history-item" key={item.id}>
              <div>
                <h3 className="history-title">{item.title}</h3>
                <div className="history-meta">
                  <span>{new Date(item.created_at).toLocaleString()}</span>
                  <span>•</span>
                  <span>{item.speaker_display_names?.join(", ") || "Speakers pending"}</span>
                  <span>•</span>
                  <span style={{ textTransform: "capitalize", color: item.processing_status === "complete" ? "var(--accent-emerald)" : "var(--accent-amber)" }}>
                    {item.processing_status}
                  </span>
                </div>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                {item.processing_status === "failed" && (
                  <button className="btn-secondary btn-sm" onClick={() => retryProcessing(item.id)}>
                    Retry
                  </button>
                )}
                <button className="btn-primary btn-sm" style={{ width: "auto" }} onClick={() => openConversation(item.id)}>
                  Open
                </button>
                <button className="btn-secondary btn-sm" onClick={() => deleteConversation(item.id)}>
                  Delete
                </button>
              </div>
            </article>
          ))}
        </section>
      </main>
    );
  }

  // Landing / Upload Page
  return (
    <main className="shell">
      <header className="top-header">
        <div className="brand-group">
          <div className="logo-badge">🎙️</div>
          <div className="brand-text">
            <h1>Meeting & Debate Intelligence</h1>
            <span className="brand-sub">Local First • AI Powered</span>
          </div>
        </div>
        <nav className="nav">
          <button className="nav-button active-nav">New Conversation</button>
          <button className="nav-button" onClick={showHistory}>
            History
          </button>
        </nav>
      </header>

      <section className="hero">
        <div className="hero-pill">⚡ Faster-Whisper & Gemini 1.5 Intelligence</div>
        <h2>Turn voice recordings into structured clarity.</h2>
        <p className="hero-lede">
          Automatic speaker diarization, word-synchronized transcripts, meeting action items, and debate argument extraction.
        </p>
      </section>

      {/* Mode Switcher */}
      <div className="mode-toggle-group">
        <div
          className={`mode-option ${!isDebate ? "active" : ""}`}
          onClick={() => setIsDebate(false)}
        >
          <span className="mode-icon">💼</span>
          <div>
            <div className="mode-title">Meeting Mode</div>
            <div className="mode-desc">Optimized for action items, decisions, and participation distribution.</div>
          </div>
        </div>
        <div
          className={`mode-option ${isDebate ? "active" : ""}`}
          onClick={() => setIsDebate(true)}
        >
          <span className="mode-icon">⚖️</span>
          <div>
            <div className="mode-title">Debate Mode</div>
            <div className="mode-desc">Extracts key claims, arguments per speaker, and resolution agreements.</div>
          </div>
        </div>
      </div>

      <section className="card">
        {/* Browser Recording Option */}
        <div className="recording-panel">
          <div className="recording-info">
            <h3>Record In-Browser Audio</h3>
            <p>Direct microphone recording with zero file conversion required.</p>
          </div>
          <div className="recording-controls">
            {recording ? (
              <>
                <div className="recording-badge">
                  <span className="pulse-dot" />
                  <span>{String(Math.floor(recordSeconds / 60)).padStart(2, "0")}:{String(recordSeconds % 60).padStart(2, "0")}</span>
                </div>
                <button className="record-btn-stop" onClick={stopRecording}>
                  Stop Recording
                </button>
              </>
            ) : (
              <button
                className="record-btn-start"
                onClick={() => {
                  setConsentAction("record");
                  setConsentOpen(true);
                }}
              >
                <span>🔴</span> Start Recording
              </button>
            )}
          </div>
        </div>

        {/* Audio Preview if Recorded */}
        {recordedAudioUrl && (
          <div style={{ background: "rgba(99, 102, 241, 0.08)", border: "1px solid rgba(99, 102, 241, 0.2)", borderRadius: "12px", padding: "14px 18px", marginBottom: "20px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "1.2rem" }}>🎵</span>
              <div>
                <strong style={{ fontSize: "0.92rem", display: "block" }}>Recording Ready</strong>
                <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{file?.name} ({(file ? file.size / 1024 : 0).toFixed(0)} KB)</span>
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <audio src={recordedAudioUrl} controls style={{ height: "36px" }} />
              <button className="btn-secondary btn-sm" onClick={discardRecording}>
                Discard
              </button>
            </div>
          </div>
        )}

        {/* File Upload Dropzone */}
        <label className="dropzone">
          <span className="dropzone-icon">📁</span>
          {file && !recordedAudioUrl ? (
            <div className="file-pill">
              <span>✓ Selected:</span>
              <strong>{file.name}</strong> ({(file.size / (1024 * 1024)).toFixed(2)} MB)
            </div>
          ) : (
            <>
              <strong>Choose an audio recording or drag & drop here</strong>
              <span>WAV, MP3, M4A, WEBM, or OGG • up to 25 MB</span>
            </>
          )}
          <input
            type="file"
            accept={allowedTypes}
            onChange={(event) => {
              const selected = event.target.files?.[0];
              if (selected) {
                setFile(selected);
                setRecordedAudioUrl(null);
              }
            }}
          />
        </label>

        {/* Optional Form Inputs */}
        <div className="fields-grid">
          <div className="field-group">
            <label>Conversation Title (optional)</label>
            <input
              type="text"
              placeholder={isDebate ? "e.g. Oxford Union Debate on AI" : "e.g. Weekly Product Sync"}
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
            />
          </div>
          <div className="field-group">
            <label>Speaker Count Hint (optional)</label>
            <input
              type="number"
              min="1"
              max="10"
              placeholder="Auto-detect"
              value={speakerCount}
              onChange={(e) => setSpeakerCount(e.target.value)}
            />
          </div>
        </div>

        {error && <div className="alert-error"><span>⚠️</span> {error}</div>}

        <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", margin: "14px 0" }}>
          By continuing, you consent to local audio storage and processing via speech-to-text and AI summarization.
        </p>

        <button className="btn-primary" onClick={startProcessing} disabled={busy || recording}>
          {busy ? "Processing conversation..." : "Upload & Analyze Audio"}
        </button>

        {/* Processing Stepper */}
        {busy && (
          <div className="stepper-card">
            <div className="stepper">
              {PIPELINE_STEPS.slice(0, 5).map((step, idx) => {
                const isActive = conversation?.processing_status === step;
                const isCompleted = currentStepIndex > idx;
                return (
                  <div key={step} className={`step-item ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""}`}>
                    <div className="step-indicator">
                      {isCompleted ? "✓" : idx + 1}
                    </div>
                    <span className="step-label">{step}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {/* Consent Modal */}
      {consentOpen && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal" role="dialog" aria-modal="true">
            <h2>User Consent Required</h2>
            <p>
              Your audio recording is stored securely in your local environment.
              During processing, audio is transcribed and the resulting transcript is analyzed
              by the configured AI service to generate summaries and speaker analytics.
            </p>
            <p>Do you consent to proceed with this operation?</p>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setConsentOpen(false)}>
                Cancel
              </button>
              <button className="btn-primary" style={{ width: "auto" }} onClick={confirmConsent}>
                I Consent & Continue
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
