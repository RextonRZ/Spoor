# F-042 — J4 Muse Voice Transcribe: floor-search voice notes + complaint call as case input

From the frontend agent.

## 1. Changed since last request
- **Backend.**
  - `spoor/voice.py` follows the dev.meta.ai voice reference: `POST /v1/asr/transcribe`, multipart with a `request`
    part (JSON: `model: muse-voice-transcribe-1.0`, `audioEncoding: WAV`, `mode: DIARIZATION`, `keywords`) and an
    `audio` part.
  - `wav_info` refuses, with the reason, anything that isn't mono 16-bit PCM at 16 or 24 kHz, or is over 10 min,
    over 32 MB, or shorter than 0.3 s.
  - Price: $0.18 per audio hour, whole seconds rounded down. The key is sent only in the Authorization header.
- **New record `VoiceTranscript` (`vtr_`).** It holds kind (`search_note` | `complaint_call`), task and place, the
  original audio SHA-256, duration, sample rate, mode, and turns (model speaker label "A"/"B", start and end ms,
  text). It also holds the model, session id, cost, pseudonymous uploader, time, the "machine transcript; check
  against the audio" label, and a content hash.
- **Routes.**
  - `POST /v1/cases/{id}/voice` (investigator or reviewer):
    - the original WAV is stored as received at `audio/{sha256}.wav`;
    - transcription is biased with the case's waybill and hub words ("waybill", "chute", "cage", "exception store",
      "bench");
    - it writes the record, a cost entry and a **case revision**;
    - a floor note must name a place in a real search task, otherwise 404;
    - **no key → 503, nothing stored**.
  - `GET /v1/cases/{id}/voice` returns items with signed audio links, availability and the per-minute price.
  - `GET /v1/signed/audio/{sha}` serves the audio.
- **Frontend.**
  - `lib/wav.ts`: the browser decodes any recording or picked file, mixes it to mono, resamples it to 16 kHz offline
    and writes a 16-bit WAV.
  - `components/VoiceNote.tsx`: Record (microphone) or Pick a recording, the price stated, and a transcript view
    with an audio player, timed turns, speaker labels, and the "machine transcript of the original (SHA-256 …)"
    caption.
  - Floor search (H12): every place has "Add a voice note", and its transcripts appear under it.
  - Case summary: a "Complaint call" block under the complaint. It shows the transcript, or the recorder when there
    is none.
  - Without the key, the buttons are disabled and say "Voice notes need the Model API key. Nothing is uploaded
    without it."
- **Keyed smoke test, cost $0.0005.**
  - The input is 10 s of **synthetic** speech made with Windows speech synthesis, saying "Found it. The parcel is on
    the bottom shelf of the exception store, next to cage fourteen. Waybill ends in seven eight five seven."
  - It is not evidence and was not stored on any case.
  - Back in 4.8 s: one diarized turn, A, 140–9420 ms, word-perfect except **"Waybill" → "Wable"**. The case route now
    sends "waybill" as a keyword.
  - Logged before and after; Meta total ≈ $1.12 / $60; row added to `docs/META_MODEL_USAGE.md`.
- **Tests.**
  - backend 251 ✓, including 5 voice tests: WAV rules and price; turn parsing; multipart with the documented fields;
    the full route (audio kept by hash and served back, turns, cost, case revision, keywords include the waybill,
    bad WAV → 422 with reason, a floor note without a real place → 404); no key → 503 with nothing stored;
  - new e2e `voice.spec.ts`: a 44.1 kHz stereo file picked in the browser is uploaded as **16 kHz mono 16-bit WAV**
    of the right length (the route is mocked only to capture the upload), and no key → disabled with nothing posted;
  - e2e + a11y 24/24 ✓; review H12/H14 ✓; ruff, typecheck and lint clean.

## 2. Check these
- `frontend/review_pack/desktop/33_h14_case_summary.png`: the "Complaint call" block (no-key state).
- `frontend/review_pack/mobile/fx_37_h12_search_checklist.png`: "Add a voice note" per place.
- `backend/src/spoor/voice.py`, `backend/tests/test_voice.py`, `frontend/tests/e2e/voice.spec.ts`

## 3. Questions
- For the demo, a real voice recording would be best: a floor-staff voice note ("found it on the bottom shelf by cage
  14", about 10 s) and/or a short role-played complaint call. I won't put synthetic speech on the demo case. Can
  Rexton record these, or should a role-play be labelled SYNTHETIC like the footage?
