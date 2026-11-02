"use client";
/**
 * Focus crops (Rexton, 2 Nov): an evidence image shows what matters (the outlined carton, the hands carrying it), not
 * the whole wide frame. The crop is computed from SAM's own box: the server pads it (crop.py MARGIN, 16:9, clamped to
 * the frame) and returns the rectangle it cut, so the outline can be drawn on the crop exactly. Never hand-tuned per
 * image; the full frame stays one click away wherever a crop is shown.
 */
import { useEffect, useState } from "react";
import { api, previewUrl } from "@/lib/api";

export interface FocusCrop { url: string; rect: [number, number, number, number] }

export function useFocusCrop(media: string | null | undefined, frame: number | null | undefined, box: number[] | null | undefined): FocusCrop | null {
  const [got, setGot] = useState<{ k: string; c: FocusCrop } | null>(null);
  const k = media && frame != null && box ? `${media}/${frame}/${box.map(Math.round).join(",")}` : "";
  useEffect(() => {
    if (!k || !box || !media || frame == null) return;
    let live = true;
    const b = box.map((v) => Math.max(0, Math.round(v))).join(",");
    api<{ crop_url: string; crop_rect_px: [number, number, number, number] }>(`/v1/media/${media}/frames/${frame}/crop?box=${b}`)
      .then((r) => live && setGot({ k, c: { url: previewUrl(r.crop_url, 560), rect: r.crop_rect_px } })).catch(() => {});
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed by media, frame and box
  }, [k]);
  return got?.k === k ? got.c : null;
}

/** the box in the crop's own pixels (for an SVG drawn over the crop with viewBox 0 0 w h) */
export function inCrop(box: number[], rect: [number, number, number, number]) {
  return { x: box[0] - rect[0], y: box[1] - rect[1], w: box[2] - box[0], h: box[3] - box[1], vw: rect[2] - rect[0], vh: rect[3] - rect[1] };
}
