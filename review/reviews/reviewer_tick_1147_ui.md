last commit reviewed: 17450e8

UI review of the live app (reviewer screenshots 11:15, 1440x900: Hub, case Answer, moments, checkpoints/passport).
Do these in step D (consistency pass), with emil-design-eng + design-taste, after the control re-run:
1. Hub side panel for the story parcel is stale: "Put in a cage at 14:21. Not loaded onto a truck since" and "CAM 13 ...
   no footage of 14:21 yet". The truck RFID says loaded at D07 14:33:25 and 14:21 footage now exists (CHK_CAGE_W).
   Panel must read from the latest verified run (e.g. "Records say loaded on D07 at 14:33. Cameras say it never left.").
2. Hub table: no "Customer asked" chip visible on the CTX334048419302 row (11:13 log says it exists); check it renders.
   The 3 control parcels show as open "Lost track" cases: keep them out of the demo Hub (separate control case set or
   a filter), or label them clearly as test cases.
3. Answer hero uses the far CAM_19. Use the close-up CHK_STORE (doorway + unused SCAN IN handheld) as the hero; keep
   CAM_19 as a smaller second view. Map inset labels still collide ("Bag opening" under "CAM 19", "Exception..." cut).
4. The 5 moments are all CAM_19 thumbnails that look identical. Use the best camera per moment: pick from the cage
   (CHK_CAGE_W 14:32:10-13, the alert), carried in (CHK_STORE 14:32:30-32), out empty-handed (CHK_STORE ~14:32:48),
   cage leaves without it (CHK_DOCK 14:33:25). Each thumbnail should show the outlined carton/person, not empty floor.
5. Passport ("On camera at its scans"): "Unloaded" and "On the sorter" are empty grey boxes. Show the clip frame
   anyway with the reason as a caption ("Two cartons scanned 0.2 s apart here"). Chute uses wide CAM 11: prefer the
   CHK_CHUTE close-up when it was labelled there. The outlined carton is too small: crop/zoom each tile on the outline.
6. Add the story's two best close-ups to the passport row after the cage: store door (carried in, not scanned) and
   dock D07 (cage leaves without it), marked red, so the row reads as the whole journey.
Save before/after screenshots in review/shots/mon/ and write READY.md.
