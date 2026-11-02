"use client";
/**
 * Focus crops (Rexton, 2 Nov): an evidence image shows what matters (the outlined carton, the hands carrying it), not
 * the whole wide frame. The crop is computed from SAM's own box: the server pads it (crop.py MARGIN, 16:9, clamped to
 * the frame) and returns the rectangle it cut, so the outline can be drawn on the crop exactly. Never hand-tuned per
 * image; the full frame stays one click away wherever a crop is shown.
 */
import { useEffect, useState } from "react";
import { api, previewUrl, useResource } from "@/lib/api";

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

/** SAM's mask edge on each frame of a track (frame index -> polygon in frame pixels); frames without one keep the box */
export function useContours(media: string | null | undefined, track: string | null | undefined): Map<number, number[][]> {
  const r = useResource<{ contours: [number, number[][]][] }>(media && track ? `/v1/media/${media}/tracks/${track}/contours` : null);
  return new Map(r.data?.contours ?? []);
}

/** the frame of a track to SHOW (not the frame an event was measured on): where its box is largest and wholly inside
 *  the picture, so the outline is not cut at the edge. Returns that frame, its box and how far (ms) it is from `at`. */
export function useBestView(media: string | null | undefined, track: string | null | undefined, atFrame: number | null | undefined,
  wh: [number, number] = [1920, 1086]): { frame: number; box: number[]; dms: number } | null {
  const r = useResource<{ boxes: number[][] }>(media && track ? `/v1/media/${media}/tracks/${track}/boxes` : null);
  const boxes = r.data?.boxes ?? [];
  if (!boxes.length || atFrame == null) return null;
  const inside = boxes.filter((b) => b[2] > 4 && b[3] > 4 && b[4] < wh[0] - 4 && b[5] < wh[1] - 4);
  if (!inside.length) return null;
  const best = inside.reduce((a, b) => ((b[4] - b[2]) * (b[5] - b[3]) > (a[4] - a[2]) * (a[5] - a[3]) ? b : a));
  const at = boxes.find((b) => b[0] === atFrame) ?? boxes[boxes.length - 1];
  return { frame: best[0], box: best.slice(2), dms: best[1] - at[1] };
}

/** a polygon as SVG points, shifted into a crop's own pixels */
export const pointsIn = (poly: number[][], rect: [number, number, number, number] | null = null) =>
  poly.map(([x, y]) => `${(x - (rect?.[0] ?? 0)).toFixed(1)},${(y - (rect?.[1] ?? 0)).toFixed(1)}`).join(" ");

/** the box in the crop's own pixels (for an SVG drawn over the crop with viewBox 0 0 w h) */
export function inCrop(box: number[], rect: [number, number, number, number]) {
  return { x: box[0] - rect[0], y: box[1] - rect[1], w: box[2] - box[0], h: box[3] - box[1], vw: rect[2] - rect[0], vh: rect[3] - rect[1] };
}
