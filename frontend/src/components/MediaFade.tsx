"use client";
/**
 * One loading treatment for every camera picture and video in the app (Rexton 3 Nov: pictures "stuck" then popping in).
 * While an <img> or <video> inside the app is still loading it carries data-ld: it is transparent and its frame shows a
 * soft shimmer (CSS in shell.css); when it arrives it fades in (200 ms ease-out). Reduced motion: no shimmer, no fade.
 * Applied by observing the DOM once, so each component keeps its own markup.
 */
import { useEffect } from "react";

const loaded = (el: Element) =>
  el instanceof HTMLImageElement ? el.complete && el.naturalWidth > 0
    : el instanceof HTMLVideoElement ? el.readyState >= 1 || el.preload === "none" || (!el.src && !el.querySelector("source")) : true;

function mark(el: Element) {
  if (!(el instanceof HTMLImageElement || el instanceof HTMLVideoElement)) return;
  if (el.closest("[data-no-fade]")) return;
  if (loaded(el)) { el.removeAttribute("data-ld"); return; }
  el.setAttribute("data-ld", "");
  window.setTimeout(() => el.removeAttribute("data-ld"), 8000); // never hidden for good: a slow picture shows when it can
}

export function MediaFade() {
  useEffect(() => {
    const root = document.body;
    const done = (e: Event) => { const t = e.target as Element; if (t?.hasAttribute?.("data-ld")) t.removeAttribute("data-ld"); };
    root.querySelectorAll(".sb-main img, .sb-main video").forEach(mark);
    const mo = new MutationObserver((muts) => {
      for (const m of muts) {
        if (m.type === "attributes") { if (m.target instanceof Element && m.target.closest(".sb-main")) mark(m.target); continue; }
        m.addedNodes.forEach((n) => {
          if (!(n instanceof Element) || !n.closest(".sb-main")) return;
          if (n.matches("img, video")) mark(n);
          n.querySelectorAll?.("img, video").forEach(mark);
        });
      }
    });
    mo.observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ["src", "poster"] });
    // load / loadeddata / error do not bubble: listen in the capture phase (an error ends the wait too, never a stuck shimmer)
    root.addEventListener("load", done, true);
    root.addEventListener("loadeddata", done, true);
    root.addEventListener("loadedmetadata", done, true);
    root.addEventListener("error", done, true);
    return () => { mo.disconnect(); root.removeEventListener("load", done, true); root.removeEventListener("loadeddata", done, true);
      root.removeEventListener("loadedmetadata", done, true); root.removeEventListener("error", done, true); };
  }, []);
  return null;
}
