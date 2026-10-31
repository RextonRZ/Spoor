"use client";
/**
 * Voice notes (J4): floor staff with gloves on talk instead of typing ("found it on the bottom shelf"), and a complaint
 * call recording becomes case input. Record in the browser or pick a file; it is converted to 16 kHz mono WAV, the
 * backend keeps that original by its SHA-256 and Muse Voice Transcribe adds speaker turns. A paid call (US$0.18 per
 * audio hour), stated on the button. Without the key the control says so and nothing is uploaded.
 */
import { useRef, useState } from "react";
import { api, invalidate, signedUrl, useResource } from "@/lib/api";
import { toWav16k } from "@/lib/wav";
import "./voice.css";

export interface VoiceItem {
  voice_transcript_id: string; kind: "search_note" | "complaint_call"; area_id: string | null; audio_url: string;
  audio_sha256: string; audio_duration_ms: number; transcript: string; recorded_by: string; recorded_at: string;
  turns: { turn_id: number; speaker: string | null; start_ms: number; end_ms: number; text: string }[]; model: string;
}
export interface VoiceList { items: VoiceItem[]; available: boolean; estimate: { usd_per_minute: number } }

const secs = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}`;

export function Transcript({ v }: { v: VoiceItem }) {
  return (
    <div className="vn-tr" data-testid="voice-transcript">
      <audio controls preload="none" src={signedUrl(v.audio_url)} style={{ width: "100%", height: 32 }} />
      <ol className="vn-turns">
        {v.turns.length ? v.turns.map((t) => (
          <li key={t.turn_id}><span className="vn-t sp-num">{secs(t.start_ms)}</span>{t.speaker && <b>{t.speaker}</b>} {t.text}</li>
        )) : <li>{v.transcript || "No speech recognised."}</li>}
      </ol>
      <p className="sp-caption" style={{ margin: 0 }}>
        {secs(v.audio_duration_ms)} · {v.recorded_by} · machine transcript by {v.model}; the audio is the original (SHA-256 {v.audio_sha256.slice(0, 12)}…)
      </p>
    </div>
  );
}

export function VoiceRecorder({ caseId, kind, taskId, areaId, label }: {
  caseId: string; kind: "search_note" | "complaint_call"; taskId?: string; areaId?: string; label: string;
}) {
  const path = `/v1/cases/${caseId}/voice`;
  const list = useResource<VoiceList>(path);
  const [state, setState] = useState<"idle" | "recording" | "sending">("idle");
  const [err, setErr] = useState<string | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const available = list.data?.available ?? false;

  async function send(blob: Blob) {
    setState("sending"); setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", await toWav16k(blob), `${kind}.wav`);
      fd.append("kind", kind);
      if (taskId) fd.append("search_task_id", taskId);
      if (areaId) fd.append("area_id", areaId);
      await api(path, { method: "POST", body: fd });
      invalidate(path);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setState("idle"); }
  }
  async function toggle() {
    if (state === "recording") { rec.current?.stop(); return; }
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const r = new MediaRecorder(stream);
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = () => { stream.getTracks().forEach((t) => t.stop()); void send(new Blob(chunks, { type: r.mimeType })); };
      rec.current = r;
      r.start();
      setState("recording");
    } catch { setErr("The microphone is not available here. Pick a recording file instead."); }
  }
  return (
    <div className="vn">
      <div className="vn-row">
        <button className="sp-btn sp-btn-sm" onClick={toggle} disabled={!available || state === "sending"} aria-pressed={state === "recording"}>
          {state === "recording" ? "Stop and transcribe" : state === "sending" ? "Transcribing" : label}
        </button>
        <button className="sp-btn sp-btn-sm" onClick={() => file.current?.click()} disabled={!available || state !== "idle"}>Pick a recording</button>
        <input ref={file} type="file" accept="audio/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) void send(f); e.target.value = ""; }} />
      </div>
      <p className="sp-caption" style={{ margin: 0 }}>
        {available ? `Muse Voice Transcribe · about US$${(list.data?.estimate.usd_per_minute ?? 0.003).toFixed(3)} per minute of audio`
          : "Voice notes need the Model API key. Nothing is uploaded without it."}
      </p>
      {err && <p role="alert" className="sp-caption">{err}</p>}
    </div>
  );
}

export function useVoice(caseId: string) {
  return useResource<VoiceList>(`/v1/cases/${caseId}/voice`);
}
