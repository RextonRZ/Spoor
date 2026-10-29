"""Camera clock synchronization from a shared observable event (PRD §8.3, §13.2 step 2).

normalized_time = camera_time + offset. We never assume feeds are synchronous; each offset carries uncertainty.
"""

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from spoor.contracts import ClockSync, FrameRef, new_id


def sync_from_shared_event(
    *,
    camera_id: str,
    camera_event_time: datetime,
    reference_event_time: datetime,
    camera_frame_interval_ms: float,
    reference_frame_interval_ms: float,
    annotation_uncertainty_ms: float = 0.0,
    anchor_description: str,
    now: datetime,
) -> ClockSync:
    """Offset from one event seen by both clocks (e.g. a hand clap visible in both views).

    Each side can only localize the event to within one frame interval; uncertainties add.
    """
    offset_ms = (reference_event_time - camera_event_time) / timedelta(milliseconds=1)
    uncertainty = camera_frame_interval_ms + reference_frame_interval_ms + annotation_uncertainty_ms
    return ClockSync(
        sync_id=new_id("sync"), camera_id=camera_id, offset_ms=offset_ms, uncertainty_ms=uncertainty,
        method="shared_visible_event", anchor_description=anchor_description, created_at=now,
    )  # fmt: skip


def normalize(ref: FrameRef, *, clip_start_camera_time: datetime, sync: ClockSync) -> FrameRef:
    """Attach the normalized timestamp to a frame reference (returns a new FrameRef)."""
    camera_time = clip_start_camera_time + timedelta(milliseconds=ref.pts_ms)
    return ref.model_copy(update={
        "camera_clock_utc": camera_time,
        "normalized_utc": camera_time + timedelta(milliseconds=sync.correction_ms(camera_time)),
        "sync_id": sync.sync_id,
        "time_uncertainty_ms": sync.uncertainty_ms,
    })  # fmt: skip


def ordering_is_determined(a: FrameRef, b: FrameRef) -> bool | None:
    """True if a is before b beyond combined uncertainty, False if after, None if the order cannot be told."""
    if a.normalized_utc is None or b.normalized_utc is None:
        return None
    gap_ms = (b.normalized_utc - a.normalized_utc) / timedelta(milliseconds=1)
    tolerance = (a.time_uncertainty_ms or 0.0) + (b.time_uncertainty_ms or 0.0)
    if gap_ms > tolerance:
        return True
    if gap_ms < -tolerance:
        return False
    return None


# --- fitted clock domains -------------------------------------------------------------------------------------------
# A CCTV recorder can drift by seconds per week while parcels on a 2.5 m/s belt are ~200 ms apart, so offsets are
# fitted from matched anchor events (tunnel passages seen by the tunnel-exit camera, divert confirmations seen by a
# chute camera, door RFID reads seen by a dock camera) instead of being trusted from NTP or the on-screen clock.


@dataclass(frozen=True)
class AnchorPair:
    """One event timestamped by two clocks: the device being fitted, and the reference timeline."""

    device_time: datetime
    reference_time: datetime
    anchor_id: str = ""


@dataclass(frozen=True)
class ClockFit:
    offset_ms: float  # at reference instant `t0`
    drift_ppm: float
    t0: datetime  # device-clock reference instant for drift
    residual_ms_p95: float
    n_used: int
    n_rejected: int
    used_anchor_ids: tuple[str, ...]
    rejected_anchor_ids: tuple[str, ...]


class ClockFitError(ValueError):
    pass


def _linear_fit(xs: list[float], ys: list[float], with_drift: bool) -> tuple[float, float]:
    """Least squares y = a + b*x (b = 0 when drift is not fitted)."""
    if not with_drift:
        return statistics.fmean(ys), 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    return my - b * mx, b


def fit_clock(anchors: list[AnchorPair], *, fit_drift: bool | None = None, min_anchors: int = 3,
              outlier_floor_ms: float = 40.0) -> ClockFit:  # fmt: skip
    """Robust fit of `reference - device = offset + drift * (device - t0)`.

    Mismatched anchors (a camera event paired with the wrong parcel's scan) are rejected by a median-absolute-deviation
    test before refitting. Drift is fitted only when anchors span enough time to estimate it (> 10 minutes by default).
    """
    if len(anchors) < min_anchors:
        raise ClockFitError(f"need at least {min_anchors} anchors, got {len(anchors)}")
    anchors = sorted(anchors, key=lambda a: a.device_time)
    t0 = anchors[0].device_time
    xs = [(a.device_time - t0).total_seconds() * 1000.0 for a in anchors]
    ys = [(a.reference_time - a.device_time).total_seconds() * 1000.0 for a in anchors]
    if fit_drift is None:
        fit_drift = xs[-1] - xs[0] > 10 * 60 * 1000
    keep = list(range(len(anchors)))
    for _ in range(3):
        a, b = _linear_fit([xs[i] for i in keep], [ys[i] for i in keep], fit_drift)
        residuals = {i: ys[i] - (a + b * xs[i]) for i in range(len(anchors))}
        mad = statistics.median(abs(residuals[i]) for i in keep) or 0.0
        limit = max(outlier_floor_ms, 3 * 1.4826 * mad)
        new_keep = [i for i in range(len(anchors)) if abs(residuals[i]) <= limit]
        if len(new_keep) < min_anchors:
            raise ClockFitError("anchors disagree too much to fit a clock (too many mismatches)")
        if new_keep == keep:
            break
        keep = new_keep
    a, b = _linear_fit([xs[i] for i in keep], [ys[i] for i in keep], fit_drift)
    res = sorted(abs(ys[i] - (a + b * xs[i])) for i in keep)
    p95 = res[min(len(res) - 1, round(0.95 * (len(res) - 1)))]
    rejected = [i for i in range(len(anchors)) if i not in keep]
    return ClockFit(a, b * 1e6, t0, p95, len(keep), len(rejected), tuple(anchors[i].anchor_id for i in keep),
                    tuple(anchors[i].anchor_id for i in rejected))  # fmt: skip


def sync_from_fit(fit: ClockFit, *, clock_domain_id: str | None = None, camera_id: str | None = None,
                  base_uncertainty_ms: float = 0.0, now: datetime, method: str = "fitted_from_anchor_events",
                  anchor_description: str = "") -> ClockSync:  # fmt: skip
    """Turn a fit into a ClockSync. Uncertainty = fit residual p95 + the anchors' own timing uncertainty."""
    return ClockSync(
        sync_id=new_id("sync"), camera_id=camera_id, clock_domain_id=clock_domain_id, offset_ms=fit.offset_ms,
        drift_ppm=fit.drift_ppm, uncertainty_ms=fit.residual_ms_p95 + base_uncertainty_ms, drift_reference=fit.t0,
        anchor_event_ids=[a for a in fit.used_anchor_ids if a], residual_ms_p95=fit.residual_ms_p95, method=method,
        anchor_description=anchor_description or f"{fit.n_used} anchors, {fit.n_rejected} rejected", created_at=now,
    )  # fmt: skip


def normalize_device_time(device_time: datetime, sync: ClockSync) -> datetime:
    return device_time + timedelta(milliseconds=sync.correction_ms(device_time))
