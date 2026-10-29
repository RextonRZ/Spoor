# Reply to review 006 (builder)

Fixes and numbers are in request 009. Two answers that need evidence rather than a fix:

## P0 #3: the "brown pole jumping between positions" is the XO-1 crossover stair's handrail, not a prop
- **Evidence:**
  - `assets/hub/build/qa/review/req009/p0_3_pole_is_xo1_handrail.png`: the bagger's frames f27/f81/f163/f190, re-rendered with the fixed follow-cam. The diagonal member is the stair's yellow rail, and it stays put.
  - A scene query found no thin, long, animated object within 4 m of the bag-change route: no prop, no broom, no hook.
  - The bagger's only children are body, vest and hard hat.
- **Cause:** the old follow-cam put its near clip plane 0.7 m in front of the head. As the camera moved, that plane sliced the static rail at different points, so the visible piece seemed to jump.
- **Fix:** follow-cam placement. The rig's facing is now measured from the hips; the old value was ~90° off. There are 8 angles plus high views, and positions enclosed by walls or lorry bodies are scored down, so dock follow-cams now stand in the hall (`dock_followcam_new.png`).
- **In the CCTV renders nothing changes:** the rail is static and was always there.

## P2 #12: break table
- It sits 3.35 m north of the collector's tail at (4.55, 31.35), in Z11.
- I checked moving it to the free floor beside the supervisor office (Z13). No camera sees that spot, so the break pair would just vanish from the footage.
- The blind corner BLIND_NW (y ≥ 33.6) is the S2 story area and must stay empty of incidental people.
- Proposal: keep it, and add a yellow pedestrian barrier between the table and the collector/dock lane in the next build pass. Say if you'd rather I move it out of view.

## P2 #11: follow-cam `clip: ?`
- Not done yet. Contact workers have no source clip per frame (one solved action); the right label is the station phase (reach / pull / hold / turn / place, walk, push...).
- This needs every station to write its phase per frame. It's queued after the scenario renders start.
