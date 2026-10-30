"""Follow-cam crop (QUEUE I1 / H1): a cut of the ORIGINAL frame around a box, with its provenance.

The crop is the original decoded pixels inside a rectangle: no resampling, no enhancement, no AI upscale. Any zoom
happens in the viewer and is labelled there. The PNG is lossless and deterministic, so its SHA-256 identifies it, and
the response names the source media, its SHA-256 and the frame index it was cut from."""

import hashlib

import cv2
import numpy as np

from spoor.contracts import ObjectInstance, ReadOutcome, TrackAssociation
from spoor.store import CONFIRMED_STATUSES, EvidenceStore, latest_associations
from spoor.store.parcels import object_keys, scans_for

MARGIN = 0.6  # context around the box, as a share of the box's larger side on each edge
MIN_SIDE_PX = 64  # a crop never shrinks below this; a 300 px inset then shows the parcel at ~2.6x (H1: 2-4x)


def crop_rect(box: tuple[float, float, float, float], frame_wh: tuple[int, int], *, margin: float = MARGIN,
              min_side: int = MIN_SIDE_PX) -> tuple[int, int, int, int]:  # fmt: skip
    """16:9 rectangle around `box` (+margin, at least MIN_SIDE_PX tall), clamped inside the frame; integer edges."""
    x1, y1, x2, y2 = box
    w, h = frame_wh
    side = max(x2 - x1, y2 - y1)
    half = max(min_side / 2, side / 2 + margin * side)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    half_w, half_h = min(half * 16 / 9, w / 2), min(half, h / 2)  # 16:9 like the frame, so insets tile cleanly
    left = round(min(max(0, cx - half_w), w - 2 * half_w))
    top = round(min(max(0, cy - half_h), h - 2 * half_h))
    return left, top, round(left + 2 * half_w), round(top + 2 * half_h)


def crop_png(png: bytes, rect: tuple[int, int, int, int]) -> bytes:
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("frame is not a decodable image")
    x1, y1, x2, y2 = rect
    ok, out = cv2.imencode(".png", img[y1:y2, x1:x2])
    if not ok:
        raise ValueError("encoding failed")
    return out.tobytes()


def frame_size(png: bytes) -> tuple[int, int]:
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("frame is not a decodable image")
    return img.shape[1], img.shape[0]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity_chain(store: EvidenceStore, case_id: str, track_id: str) -> dict:
    """Why this track is the parcel: the object it is linked to (and how), and the scans that name that object."""
    for obj in store.find(ObjectInstance, case_id=case_id):
        assoc: TrackAssociation | None = latest_associations(store, obj.object_instance_id).get(track_id)
        if assoc is None:
            continue
        keys = object_keys(store, obj.object_instance_id)
        scans = [ts for ts in scans_for(store, keys, site_id=None).scans if ts.scan.read_outcome == ReadOutcome.READ]
        return {
            "object_instance_id": obj.object_instance_id, "label": obj.label, "identity_keys": sorted(keys),
            "association": {"status": assoc.status.value, "confirmed": assoc.status in CONFIRMED_STATUSES,
                            "reason": assoc.reason, "by": assoc.created_by, "version": assoc.version},
            "scans": [{"scan_event_id": ts.scan.scan_event_id, "t": ts.t.isoformat(timespec="milliseconds"),
                       "event_kind": ts.scan.event_kind.value, "raw_code": ts.scan.raw_code,
                       "raw_description": ts.scan.raw_description,
                       "station_id": ts.scan.station_id or ts.scan.device_id, "synchronized": ts.synced}
                      for ts in scans],
        }  # fmt: skip
    return {"object_instance_id": None, "association": None, "scans": [],
            "note": "this track is not linked to any object of the case: the crop shows a tracked thing, not the parcel"}
