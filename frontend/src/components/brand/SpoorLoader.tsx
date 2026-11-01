/**
 * The Spoor loader: Rexton's exact mark (public/brand/spoor-mark.png, cut from assets/brand/spoor_logo_fingerprint_dark.png)
 * read like a fingerprint on a scanner. The box presses down; a thin light sweeps from top to bottom and the ridges
 * light up as it crosses them while the ink settles behind it (soft to sharp); the whole print glows once ("match"),
 * then it lifts and fades back to its ghost (2.4 s loop; the scan starts on the first frame). For big loads only: the app opening, a page switching, the 3D
 * hub model. Content inside a page loads as skeletons. Reduced motion: the still mark, a slow fade.
 */
import "./spoor-loader.css";

const SRC = "/brand/spoor-mark.png";

export function SpoorLoader({ label = "Loading", size = 64, fill = false }: { label?: string; size?: number; fill?: boolean }) {
  return (
    <div className={`sl${fill ? " sl-fill" : ""}`} role="status" aria-live="polite">
      <span className="sl-stage" style={{ "--sl-size": `${size}px` } as React.CSSProperties} aria-hidden="true">
        <span className="sl-shadow" />
        <span className="sl-mark">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="sl-ghost" src={SRC} alt="" width={288} height={306} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="sl-ink" src={SRC} alt="" width={288} height={306} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="sl-glow" src={SRC} alt="" width={288} height={306} />
          <span className="sl-line" />
        </span>
      </span>
      <span className="sl-label">{label}</span>
    </div>
  );
}
