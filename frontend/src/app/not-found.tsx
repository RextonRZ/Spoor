import Link from "next/link";
import "@/app/hub/hub.css";

/** A page that is not there: say so plainly and offer the way back (the bare framework 404 read as broken). */
export default function NotFound() {
  return (
    <div className="nf">
      <p className="nf-k">Not found</p>
      <h1 className="nf-h">This page isn&apos;t here.</h1>
      <p className="nf-p">The link may be old, or the case was closed. Every parcel still has its trail on the Hub.</p>
      <div className="nf-acts">
        <Link className="hb-btn hb-btn-primary" href="/hub">Go to the Hub</Link>
        <Link className="hb-btn" href="/wall">Cameras</Link>
      </div>
      <style>{`
        .nf { min-height: 60vh; display: grid; align-content: center; justify-items: start; gap: 12px; padding: 48px clamp(20px, 6vw, 72px); }
        .nf-k { margin: 0; font-size: 12px; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--tb-mute, #8b909b); }
        .nf-h { margin: 0; font-size: clamp(28px, 4vw, 40px); font-weight: 750; letter-spacing: -.03em; color: var(--tb-ink, #f4f5f7); }
        .nf-p { margin: 0; max-width: 46ch; font-size: 15px; line-height: 1.55; color: var(--tb-ink-2, #c9ccd3); }
        .nf-acts { display: flex; gap: 8px; margin-top: 6px; }
      `}</style>
    </div>
  );
}
