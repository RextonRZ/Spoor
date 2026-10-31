# Mesh hygiene — "spiderweb" white lines (Rexton, 11:44) — P0, applies to the WHOLE scene

Rexton sees thin white lines radiating across surfaces, like a spiderweb (first seen on a grey wall panel behind a camera,
"sometimes" elsewhere). Radiating lines from one point are the classic sign of a **long n-gon fan-triangulated** (often left
by boolean door/window cut-outs) under smooth shading, or of **coplanar duplicate faces (z-fighting)**. Fix the geometry —
never hide it with materials, decals or post.

## 1. Detect (script, every mesh visible to any camera; CSV + crops of the worst 20)
Per object: n-gons (> 4 verts); non-planar faces (deviation > 0.1 mm); sliver triangles (min angle < 2° or aspect > 50);
zero-area faces; duplicate vertices (merge 0.1 mm); overlapping coplanar faces inside the object; **coplanar faces of
different objects within 1 mm of each other** (z-fighting: wall panels, decals, signs, plates on walls); flipped/inconsistent
normals; non-manifold edges; loose verts/edges; smooth shading on flat hard-surface objects.

## 2. Fix at the source (build_hub.py / dress_hub.py / make_signs.py), so rebuilds don't bring it back
- Merge by distance; dissolve degenerate; delete loose; recalc normals outside.
- Walls/panels with cut-outs: rebuild as clean quads around the openings (grid/bridge), or triangulate the n-gons with
  Beauty; no long fans.
- Hard-surface objects: flat shading or Smooth by Angle ~30°; no smooth shading across 90° edges.
- Remove duplicate/overlapping faces. Things mounted on walls (panels, signs, boxes, frames) sit **2–5 mm proud of the wall**,
  never coplanar and never intersecting each other.
- If streaks remain only in lighting, check EEVEE shadow settings on those surfaces (shadow resolution / soft shadows /
  light threshold) — report which it was.

## 3. Guarantee nothing else changes
Before/after diff of every object: name, bounding box (±1 mm), material slots, transforms → must be identical except the
cleaned topology. Report the diff.

## 4. Proof
Final-settings renders, before/after, of: the panel Rexton saw, every object in the worst-20 list, and full CCTV stills
of the cameras that see them. Add `mesh_hygiene` (counts must be 0 for z-fighting, slivers in camera view, flipped normals)
to `qa_gate.py`.

## Also found by the reviewer on the B2 stills (same family — two objects in one place)
- CAM_14 and CAM_16: the **grey electrical box overlaps the wooden-framed cabinet/window** beside it (box intersects the frame).
  Move apart or resize; both flush-mounted 2–5 mm proud of the wall.
- CAM_14: a yellow warning sign on a stand **leaning against nothing** near the floor (bottom-left of the panel view) — stand it
  upright or remove.
- CAM_15: speckled black/white noise patch at the wall base by the red fire-alarm button (dithered decal — covered by your
  blended-alpha fix; verify).

## Rexton's exact spot (11:46) — `review/evidence/rexton_spiderweb_dock01.png`
Dock **D01**: the big grey slanted panel under the "01" sign (the closed roller door / door shelter next to the boom, with the
two bollards and the red/grey door control box). White dotted lines fan out across it toward the lower right. Workbench
look (QA follow-cam), but the final CAM_01 still (b2/CAM_01.png, top-left) shows the same door with noisy line aliasing
at its lower-left.
Two candidate causes — test both, report which:
1. **Topology:** boolean/n-gon fan on that panel (see sections 1–2).
2. **Moiré / aliasing of fine repeated detail** — roller-shutter slats or wall-cladding ribs (geometry or normal map) at a
   grazing angle and 2 spp produce dotted radiating lines. Test: render the same frame at 2 / 16 / 64 spp and with the
   camera moved 5 cm. Lines that move with the camera = moiré → slat/rib spacing at a real size (shutter slats ~75–100 mm,
   cladding ribs ~250 mm), proper mipmapped/filtered normal map or real bevelled geometry, no sub-pixel detail. Lines fixed
   on the surface = topology → clean the mesh.
Then check **every roller door (D01–D12) and every ribbed wall panel** from every camera that sees them.
