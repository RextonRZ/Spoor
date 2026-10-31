# Spoor brand

- **Logo (FINAL, Rexton 31 Oct 08:13):** the fingerprint parcel box: "every parcel leaves a trace", so the box carries
  its own print. Never present it as fingerprinting people.
  - Source PNGs from Rexton (transparent):
    - `spoor_logo_fingerprint_light.png`: indigo mark, near-black wordmark;
    - `spoor_logo_fingerprint_dark.png`: indigo mark, white wordmark.
- **Production logo:** rebuilt by hand as exact SVG geometry in `frontend/scripts/build_logo.py`, not traced from the
  PNGs.
  - The geometry: an isometric box with three faces of evenly spaced rounded ridges (straight on the top face,
    nested rounded L-ridges on the side faces), one stroke weight, round caps, the same thin gap along every box
    edge.
  - Outputs go to `frontend/public/brand/`:
    - `spoor-logo.svg` / `spoor-logo-dark.svg`: mark + wordmark;
    - `spoor-mark*.svg`: mark only;
    - `spoor-mark-small.svg` + `spoor-icon.svg` (= `frontend/src/app/icon.svg`, the favicon): the simplified mark
      for ≤ 32 px, with 3 ridges per face and a heavier stroke.
  - Proof sheet: `node frontend/scripts/logo-proof.mjs <repo> <out.png>` shows the PNGs next to the SVGs, with the
    marks at 16 / 32 / 64 / 256 px on both themes.
- **Wordmark:** "Spoor" in Google Sans Flex, weight 700, tracking −2 % (SIL Open Font License 1.1,
  `@fontsource-variable/google-sans-flex`), outlined to paths.
- **Colours:**
  - mark #4F46E5 (light) / #6366F1 (dark);
  - wordmark #0E1116 / #FFFFFF.

  Indigo is the brand accent only. It never carries an evidence meaning.
- **Tagline:** "Every parcel leaves a trail." Two-beat for the video / X end card: "Every parcel leaves a trail.
  Spoor reads it."
- **Retired:** `logo_concept_chatgpt.png` (the earlier "S as an evidence trail" concept, ChatGPT image) and its trail SVG
  set. They are no longer used anywhere; the file is kept only as history.
