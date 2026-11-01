"use client";
import { useEffect } from "react";

/** Adds .is-in to every [data-reveal] under root once it scrolls into view. The CSS owns the motion, and content is
 *  visible without JS (the hidden states only apply under html.js). */
export function useReveal(root: React.RefObject<HTMLElement | null>, again?: unknown) {
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    document.documentElement.classList.add("js");
    // `again`: content that arrives later (case data) is looked for once more when it changes
    const targets = Array.from(el.querySelectorAll<HTMLElement>("[data-reveal]:not(.is-in)"));
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        }
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.12 },
    );
    targets.forEach((t) => io.observe(t));
    return () => io.disconnect();
  }, [root, again]);
}
