/** Motion system for the landing page (Reelism's, with Emil Kowalski's curves): one strong ease-out for things that
 *  enter, one strong ease-in-out for things that move on screen. Never ease-in. */
import { cubicBezier } from "animejs";

export const EASE_OUT_CSS = "cubic-bezier(0.23, 1, 0.32, 1)";
export const EASE_IN_OUT_CSS = "cubic-bezier(0.77, 0, 0.175, 1)";
export const easeOut = cubicBezier(0.23, 1, 0.32, 1);
export const easeInOut = cubicBezier(0.77, 0, 0.175, 1);

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function hasFinePointer(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}
