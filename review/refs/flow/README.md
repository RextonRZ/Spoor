# Reviewer reference: the supervisor's flow (Rexton asked 08:51 Sat)

Screens, in order: Main (Hub) → Investigate (the agents at work) → Case (Answer) → Proof (Video | 3D hub) → Search (phone "Go look") → Report. Plus Cameras (top menu): all 19 cameras on one synced clock, Camera wall | 3D hub, zone filter.
UPDATED 09:15: Hub rows redesigned (thumbnail of the last sighting, a mini trail of how far it got, why it matters, Investigate button with time + cost); Investigating screen shows each agent step live (scan log → Muse Wonder plan → Muse Spark per camera → SAM 3.1 tracking → verifier) with the camera being checked and the running cost; 3D = the real Blender hub (the tilted plan in the mockup is only a stand-in).
Source = the `.dc.html` files here (plain HTML with inline styles; image URLs `/_blob/<id>` map to the files in this
folder: fcb4… = cam19_in.jpg, 6bed… = cam19_out.jpg, f474… = cam04.jpg, 8fbf… = cam07.jpg, 5010… = cam10.jpg,
604b… = the logo mark, 91ff… = plan_s2.png).

Copy the FLOW, NAVIGATION, HIERARCHY and WORDING — not the pixels:
- top bar: logo · Hub / Cases / Cameras · search · one "Synthetic demo hub" chip · avatar menu (role switch lives here);
- in a case: breadcrumb + 4 numbered steps (Answer · Proof · Go look · Report), one primary button per screen;
- Answer: status pill, one-sentence answer (≤ 2 lines), "How sure" with 3 plain reasons, timeline of moments;
- Proof: big player with real controls, camera strip in route order (seen / came out / records disagree),
  a side card that explains the selected moment in two sentences, Evidence details folded;
- Go look: phone, one task, what to look for, Found it / Not here, voice note;
- Report: the answer, 4 key frames, what to fix, for the customer, actions.
The story data (S2: cage RC-864, CAM 13/19, D07) is the keyed demo state, illustrative. The app must render it from
the typed journey; in no-key mode it shows only what is really known.
CCTV frames other than CAM 19 are old QA renders given a quick CCTV grade for the mockup; the app must use the
builder's final-look frames once S2 renders.
