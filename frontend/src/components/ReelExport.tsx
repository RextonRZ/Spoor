"use client";
/** Evidence reel export (QUEUE H7): one button builds the MP4 from stored evidence (backend I8) and plays it here. */
import { useState } from "react";
import { api, signedUrl } from "@/lib/api";

interface Reel { reel_id: string; cards: number; seconds: number; url: string; sources: { kind: string; sha256?: string | null }[] }

export default function ReelExport({ caseId }: { caseId: string }) {
  const [reel, setReel] = useState<Reel | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function make() {
    setBusy(true);
    setErr(null);
    try { setReel(await api<Reel>(`/v1/cases/${caseId}/reel`, { method: "POST" })); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <div className="sp-stack" style={{ gap: 8 }} data-testid="reel">
      <button className="sp-btn sp-btn-sm" onClick={make} disabled={busy}>{busy ? "Building the reel" : reel ? "Build again" : "Export evidence reel (MP4)"}</button>
      {reel && <>
        <video controls src={signedUrl(reel.url)} style={{ width: "100%", borderRadius: 10, background: "#07080b" }} aria-label="Evidence reel" />
        <p className="sp-caption" style={{ margin: 0 }}>{reel.cards} cards · {reel.seconds} s · {reel.sources.filter((s) => s.sha256).length} source frames, each with its SHA-256 in the manifest.
          {" "}<a href={signedUrl(reel.url)} download={`${reel.reel_id}.mp4`}>Download</a></p>
      </>}
      {err && <p role="alert" className="sp-caption">{err}</p>}
    </div>
  );
}
