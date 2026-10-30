# Deploying Spoor at a real hub: scan once, then the cameras keep it live

A real hub has no Blender model. Spoor does not need one.

## Day one: a floor plan is enough
What the hub already has is all Spoor reads:
- **Floor plan** (CAD or PDF, traced once): walls, doors, zones, racks, benches, walkways. It is imported as a versioned
  site plan (`POST /v1/sites/{id}/plan`), and every answer cites the plan version it was computed on.
- **Conveyor layout from the machine spec:** centrelines, deck heights and belt speeds. This is what lets Spoor infer
  the only physical route between two scans and check the scan times against belt time.
- **Scan points:** where each scanner, tunnel or PLC event happens.
- **Camera mounting plan + a 10-minute calibration per camera:** click 4 or more known floor points to get a floor
  homography.

From these, Spoor draws:
- the 2D journey;
- the missing moment (where it should have appeared next);
- the "could be here" area;
- the camera moment grid;
- a **plan-built 3D view** that extrudes walls, zones, conveyor decks at their real heights, and racks. Open the 3D
  tab and choose "Plan-built 3D".

## Optional upgrade: a one-time 3D scan
A site that wants a realistic twin scans the building once:
- **Small areas:** phone LiDAR.
- **A whole hub:** a terrestrial laser scanner (e.g. Leica BLK360), Matterport Pro3, or a walk-through mobile scanner
  (e.g. NavVis).
- **Alternative:** Gaussian splatting from a walk-through video.

The scan replaces the extruded blocks as the 3D backdrop. It is registered to the same site frame as the plan (metres,
X east, Y north, Z up), so cameras, scan points and the journey line up without other changes.

## "Live" comes from the hub's own data, never from re-scanning
The static model (plan or scan) stays fixed. What moves is laid on top of it:
- **CCTV:** the existing cameras. Clips are analysed only when a case or an exception needs them.
- **The scan log:** tunnel reads, carrier assignments, diverts, bagging and loading scans. This is also the source of
  the stalled-parcel alerts in the Hub inbox: a parcel is flagged when its next expected scan is overdue **and** the next
  point on its route kept scanning other parcels.
- **Conveyor / PLC status** where available.

Re-scan only when the building changes (a new line, racks moved), then import a new plan version.

## What stays on site
Raw CCTV can stay on the hub's own hardware. The plan is that an edge model watches each camera and sends only flagged
moments onward (see PRIVACY.md and the open-weights notes). Personal data is limited to the tracking number, size,
weight and route. Anything else is masked by default.
