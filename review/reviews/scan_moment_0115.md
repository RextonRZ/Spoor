# OWNER IDEA 01:10 Sat (Rexton): "where do I SEE the parcel get scanned — screen says scan successful + details?"

No new camera needed: CAM_05 already films the DWS-01 tunnel exit at ~277 px/m. Two parts:

## 1. In the hub (what CCTV can authentically see) — P1, with S1/S2 builds
Real DWS / scan tunnels show the result as light, not readable text, at CCTV distance:
- **Stack light** (green / amber / red tower) on top of DWS-01 and arch DWS-B: green ~0.5 s on every good read,
  red on a no-read (S1's REJECT is then visible on video), driven by the scan log events at the device clock.
- **The DWS screen** (today a blank box beside the tunnel, build_hub.py `tun["screen"]`): an emissive UI texture that
  changes per read — green banner "READ OK", red banner "NO READ", with weight / size / destination chute in small text
  (fictional UI, CONTOH Express). It is unreadable at CCTV scale on purpose; only the colour change shows.
- Handheld scans (rework bench, bag scan): the scanner's red aiming light for ~0.3 s at each scan event.
- Keep all of it in sync with events_scan_simulated (same times), never with truth-only events.

## 2. In the app (where the user actually reads the details) — frontend H13 + backend
- **Scan cards**: when the playhead reaches a scan, a card pops on the video at the scanner's position and on the
  2D/3D map at the scan bead: "✓ Tunnel read · CTX… · 1.2 kg · 30×20×12 cm · → chute C12 · 14:32:12 (scanner clock,
  drift +0.4 s corrected)". Red card for a no-read. Source = the scan log record (with its id), not the video.
- The card links to the frames where the stack light flashed — the video confirms the scan happened at that moment.
