# Spoor

**Lost parcels, found with proof.**

A parcel hub's scan log says where a parcel was *scanned*. When a customer says it never arrived, nobody can say where
it *went*. Spoor reads the hub's own CCTV and scan records together, follows the parcel from scanner to scanner on
camera, finds where it went missing, and hands the supervisor the clip that proves it, with every claim checked by a
deterministic verifier before it reaches the screen.

Built for the Meta Global AI Developer Hackathon 2026. Footage is synthetic (a fictional hub, CONTOH Express, rendered
in Blender with mocap workers); the scan log is simulated and labelled `scan_simulated`. No real people, no faces.

> Investigative decision support. Spoor never claims anyone's identity, intent or wrongdoing.

## The case it solves (what the demo shows)

Parcel CTX334048419302: the records say it was put in cage RC-760 at 14:21 and loaded on truck D07 at 14:33. The
customer says it never arrived. Spoor's answer: **most likely in the Exception store (Z11)**. The cameras show it
taken out of the cage at 14:32:13 (no scan), carried into the exception store at 14:32:32 past the unused scan-in
post, the carrier coming out empty-handed, and the cage leaving through D07 without it. The truck record is wrong.

## How it works

```
scan log + CCTV (19 wide cameras, 6 checkpoint close-ups, the tunnel's own label camera)
   |
   |- Muse Glimmer (open weights, on the hub's GPU via Modal): watches all footage, flags parcel handling;
   |  only flagged moments (17 % of it) go to the cloud models
   |- Scan-to-camera handshake: each scan's identity + scan point + time -> the camera that sees it -> SAM 3.1
   |  outlines THAT carton (its mask edge); a number goes on an outline only when no other carton could be it
   |- Live alert: a carton seen leaving a cage area with no scan -> "could be <parcel>" before anyone complains
   |
   |- Muse Wonder 1.0 (lead investigator): plans which cameras and windows to check first
   |- Muse Spark Open on Baseten (evidence + hypothesis agents): run the checks with tools (SAM 3.1, door crossings,
   |  carrier check, scan history) and propose explanations
   |- Deterministic verifier: every claim is tested against the evidence store; only verified findings form the answer
   |
   answer + proof timeline + floor search task + customer update draft (a person approves; nothing is sent)
```

## The loop: every case makes the next one easier

A case ends on the floor: staff mark **Found here** or **Not here** on Go look. A miss goes straight back to the
lead agent (Muse Wonder re-plans where it went next, with the staff's check in its evidence, so nobody is sent back to
the same place). A find is remembered by the hub as a prior: where parcels of earlier cases turned up, used only to
order options the evidence leaves equal, never as evidence for a new case. **Hub insights** shows the loop from stored
records only (cases opened, answered, checked on the floor, resolved), where the trail breaks and the fix in plain words,
the records the cameras contradicted, and, over the whole scan log, which hops leave parcels overdue. With real hub data
this ranks the places that lose parcels most. The demo's numbers are labelled "Demo hub data"; its 30-day view is a
seeded simulated history and its live feed is the recorded shift played back ([LIMITATIONS](docs/LIMITATIONS.md)).

## Measured (details and method in [EVALUATION](docs/EVALUATION.md))

| What | Result |
|---|---|
| The S2 parcel, keyed runs | "Most likely in the Exception store (Z11)": right in every completed run (6/6, plus the re-runs after each change today) |
| Control parcels (look-alike, belt parcel, unload only) | 0 false locations; 2 confirmed on camera at their chute, 1 located by scan |
| Handshake labels on screen, checked against the render truth | 51 of 51 right (100 %); 63 % of the right outlines carry a number (77 % at the diverts), the rest are shown as scan records |
| Live alert "left without a scan" | fires once, at the real pick; on no control |
| On-site triage (Muse Glimmer, Modal A100) | 17 % of the footage sent on (83 % less), the key pick moment kept; US$0.62 |
| Cost of one investigation | Muse Wonder US$0.12 to 0.38, 54k to 129k Spark Open tokens, 2 to 5 minutes |

## Run it

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), Node 20, FFmpeg on PATH.

```bash
cd backend && uv sync && uv run pytest     # 294 tests, no keys needed
cd ../frontend && npm install
npm run backend:keys                        # needs MODEL_API_KEY (Meta) and BASETEN_* in backend/.env
npm run dev                                 # http://localhost:3000
```

The demo store and the rendered footage are not in the repository (size). [DEMO_SCRIPT](docs/DEMO_SCRIPT.md) has the
path through the app; [DEPLOYMENT](docs/DEPLOYMENT.md) the setup.

## Real vs simulated

| Item | What it is |
|---|---|
| CCTV footage | Synthetic: Blender render of a fictional hub, CCTV look and on-screen clocks, every clip marked SYNTHETIC |
| Scan log | Simulated (`scan_simulated`), from the same simulation as the render |
| SAM 3.1 outlines, Muse Wonder plans, Spark Open agents, Glimmer flags | Real model calls on that footage |
| Floor positions | Estimated from calibrated camera geometry (held-out error 1 to 2 cm) |
| Camera clocks | Fitted from sorter events by Spoor, never read from the render |
| Ground truth | Read only by the evaluator, after a run; never by the app or in a prompt |

## Docs

[EVALUATION](docs/EVALUATION.md) · [LIMITATIONS](docs/LIMITATIONS.md) · [DEMO_SCRIPT](docs/DEMO_SCRIPT.md) ·
[META_MODEL_USAGE](docs/META_MODEL_USAGE.md) · [DECISIONS](docs/DECISIONS.md) · [CALIBRATION](docs/CALIBRATION.md) ·
[EVIDENCE_SCHEMA](docs/EVIDENCE_SCHEMA.md) · [PRIVACY](docs/PRIVACY.md) · [DATA_RIGHTS](docs/DATA_RIGHTS.md) ·
[DEPLOYMENT](docs/DEPLOYMENT.md)
