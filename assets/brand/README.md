# Spoor brand

- **Logo concept:** `logo_concept_chatgpt.png`, generated with ChatGPT (image) and chosen by Rexton on 31 Oct 2026
  (concept 1: an "S" drawn as an evidence trail).
- **Production logo:** rebuilt by hand as exact SVG geometry in `frontend/scripts/build_logo.py`. It is not traced from
  the raster: one stroke weight, rounded caps, evenly spaced dots, equal nodes. Outputs go to
  `frontend/public/brand/`:
  - `spoor-logo.svg` / `spoor-logo-dark.svg`: symbol + wordmark;
  - `spoor-mark*.svg`: symbol only;
  - `spoor-mark-small.svg` + `spoor-icon.svg`: simplified mark for ≤ 32 px and the favicon (fewer, larger dots).
- **Wordmark:** "Spoor" in Google Sans Flex, weight 700 (SIL Open Font License 1.1, `@fontsource-variable/google-sans-flex`),
  outlined to paths.
- **Colours:** symbol #4F46E5 (light) / #6366F1 (dark); wordmark #0E1116 / #FFFFFF. Indigo is the brand accent only. It
  never carries an evidence meaning.
