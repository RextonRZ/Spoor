# Spoor Parcel Hub — Reference & Asset Pack

Oct 28, 2026 · @Rexgent

## How to use this pack

Pick the looks you like in each section, then hand the whole pack to your Claude before it draws the 2D plan. It is a shopping list, not a build plan: nothing here goes into Blender yet.

1. Read *Look references* and watch two or three of the videos. Mark the hub that looks most like what you want.
2. In *Building shell*, *Area-by-area* and *Props*, pick one asset per item. Where two options are listed, the first is the default.
3. Paste the *Copy-paste brief* to your Claude together with this doc.

Ground rules for the build:

- **Find real models, don't model from scratch.** Your Claude builds only what no asset covers (walls, floor, sorter loop path).
- **Licences: CC0 first, CC BY second.** CC BY needs a credit line in the README. Skip "editorial only" and unclear licences, because the repo is public.
- **Real sizes in metres.** Every asset is checked against the sizes listed here before placing.
- **Fictional brand only.** No real courier logos, colours or names on walls, bags or lorries.
- **Label the footage honestly.** Rendered CCTV is *synthetic footage of a fictional hub*, not a real recording. Your PRD's real-vs-simulated table needs a new row for it.

## Why this hub fits the hackathon

The hub is Spoor's **physical system**: Spoor gets the new ability to work out where a real object went, across many cameras and scanners. That is the *Push the Frontier* theme ("understand and control a physical system"). Every design choice in this pack should earn a point on the rubric below.

### Project themes

| Theme | What the judges want | How the hub shows it |
| --- | --- | --- |
| **Push the Frontier** (PRD's main theme) | "Give a machine a new capability… understand and control a physical system" | Real hub physics: a sorter loop, reject chute, bags inside cages inside trucks, relabels. Spoor rebuilds a parcel's path through all of it from video + scans, and says where it *can't* know |
| **Build for Your World** (supporting angle) | "Solve a problem you know firsthand" | A Malaysian hub: Klang Valley setting, chutes named Penang, Johor, Kuching. Lost parcels are an everyday Malaysian problem; J&T alone handles [30.5 million parcels a day in Southeast Asia](https://www.logisticsmatters.co.uk/?p=39169) |

### Judging rubric

The kickoff slide shows Impact 30%, Meta AI tooling 25%, Technical depth 20%, Demo 25%. Your PRD notes the written guide says 25% each, so keep confirming on Discord.

| Criterion | What the hub must make possible |
| --- | --- |
| **Impact (30%)** | Every scenario copies a real loss point (no-read, wrong bag, wrong truck, relabel, fall-off). The CCTV framework section lets *any* hub adopt Spoor, so the impact goes beyond one demo |
| **Use of Meta AI tooling (25%)** | Problems only SAM 3.1 + Muse Spark can crack: look-alike parcels, occlusion behind the sorter, cross-camera handoffs, and an agent asking for more footage when a camera is out. Muse Image stays out of evidence, as the PRD says |
| **Technical depth (20%)** | Blender knows the truth: exact camera positions and every parcel's real path. That gives **measured accuracy numbers** (tracking, timing, location error) instead of claims |
| **Demo (25%)** | "A demo video worth watching": a cinematic fly-through of the hub, then the CCTV wall, then Spoor drawing the parcel's path in 3D |

### Bonus prizes

| Prize | How the hub helps |
| --- | --- |
| **Most Viral Project** ($20K) | Render a separate **cinematic camera** pass (not the CCTV cameras) for a 20–30 s clip made for X. Post by Nov 8, 11:59 PM ET |
| **Community Vote** ($10K) | The same clip; a hub people recognise from their own parcel tracking pages wins votes |
| **Best Agentic Use-Case** ($5K) | Scenarios that force multi-step work: camera outage, relabel, phantom containment. The agent has to plan, ask for evidence and abstain |
| **Best Build on Meta Open Weights** ($10K) | Not affected by the hub; depends on running Muse Glimmer or Muse Spark Open |
| **Best Creative Build** ($5K) | Low priority: it rewards builds *made with* Muse Image or Muse Wonder. Using Muse Image for fictional brand signs in the hub would be set dressing only, and must be disclosed |

### Rules the hub must follow

- **New work only (Oct 26 – Nov 4).** Build the hub inside the window and commit often; git history is your proof.
- **Public repo + asset rights.** Only CC0 or CC BY assets go in the repo, listed in a `CREDITS.md`. No paid, editorial-only or real-brand assets.
- **Demo only what you built.** Add a README table and an end card in the video: *built by us* (layout, sorter, cameras, scenarios, all Spoor code) vs *third-party assets* (models, textures, HDRIs).
- **Stay clear of the anti-project list.** The demo's star is the agent reconstructing a physical event, not a CCTV dashboard or a "simple image analyzer".

## Look references

Aim for a **mid-size Klang Valley e-commerce hub**: steel portal-frame shed about 12 m high, one cross-belt loop on a single raised level, rows of chutes with bags on frames, and roll cages lined up at the docks. The rows below are the real sites worth copying from.

| Site | Why it matters | What to copy |
| --- | --- | --- |
| [PosLaju IPC, Shah Alam](https://www.koreatimes.co.kr/business/tech-science/20151122/lg-cns-sets-sights-on-logistics-automation) | Malaysian cross-belt hub (LG CNS), replaced a manual system | Single cross-belt loop, Malaysian context. Building uses [BlueScope Zincalume / Colorbond](https://www.nsbluescope.com/my/project/pos-malaysia-intergrated-parcel-centres) steel cladding |
| [GDEX Auto Hub, PJ](https://gdexpress.com/?p=9363) | 145,000 sq ft, double-deck cross-belt, 350,000 shipments a day | Scale reference. Copy the cladding and floor look, **not** the double deck (it hides the action from cameras) |
| [Ninja Van, Shah Alam](https://www.parcelandpostaltechnologyinternational.com/?p=18377) | 260,000 sq ft hub with DWS scan machines, rollers, handheld scanners | Scan tunnel at inbound, workers with handhelds |
| [J&T Setia Alam](https://www.nst.com.my/amp/business/corporate/2025/06/1229628/jt-unveils-logistics-hub-daily-capacity-12mil-parcels) | 40,000 parcels an hour, 300+ truck movements a day | Busy truck yard, many dock doors |
| [J&T Singapore (Penjuru)](https://thesmartlocal.com/read/jt-express-behind-the-scenes/) | Photo story of a SEA hub: cross-belt for small parcels, separate machine for big ones | Best "inside" photos of a SEA hub; separate oversize flow |
| [Pitney Bowes, Lockport](https://www.mmh.com/article/sortation_and_robotics_layout_at_pitney_bowes/Automation) | Numbered layout drawing: receive → unload → induct → scan → sort → ship | Use as the **2D plan template** for zone order |
| [DHL Brussels hub](https://www.beumergroup.com/app/uploads/2019/11/DHL-Brussels-hub.pdf) | Full equipment list: telescopic unloaders, inducts with scales, chutes, exception shoe sorter | Equipment checklist and counts (scale them down) |
| [Skynet, Hounslow](https://logisticsmatters.co.uk/Crossbelt-sorter-boosts-parcel-throughput) | Small 4,000 parcel/hour hub, chutes on one side only | Closest in **size** to a demo hub: compact, readable on camera |

**Size anchor for the building:** a modern Shah Alam logistics shed lists [12 m clear height and 18 dock bays with levellers](https://www.mudah.my/shah-alam-u10-logistics-park-140-000-sqft-modern-warehouse-116027931.htm). Use 10–12 m eaves.

**Videos to watch (search these on YouTube):** I couldn't confirm stable video links, so use these exact searches and pick what looks right.

- `BEUMER Hermes Rugby` — telescopic unloading, cross-belt, chutes in one take ([described here](https://www.paketda.de/logistik-paketsortierung.php))
- `LG CNS PosLaju cross belt sorter` — the Malaysian hub
- `GDEX Auto Hub launch` — Malaysian double-deck hub
- `Ninja Van Malaysia automated hub` — DWS and rollers
- `J&T Express sorting centre Malaysia` — busy floor, roll cages, bags
- `cross belt sorter chute bagging` — close-ups of the chute-to-bag step

While watching, note four things: floor colour and markings, lighting (warm or cool, how even), how messy the floor is, and where the existing cameras are mounted.

## Building shell

Build the shell yourself from CC0 textures, because no free warehouse model fits. A plain box shell with good materials looks real at CCTV distance. Only the sizes with a link are sourced; the rest are **our design assumptions**, marked as such for your Claude.

**Legend:** PH = Poly Haven (CC0, page checked). aCG = ambientCG (CC0, page checked). SF = Sketchfab: **licence not confirmed**, so open each page and drop anything marked NC (non-commercial).

| Element | Size | Asset / material | Note |
| --- | --- | --- | --- |
| Floor plan | About 60 × 40 m (assumption) | Built | Small enough for about 11 cameras; real hubs are 5–10× bigger |
| Eaves height | 10–12 m | Built | A Shah Alam shed lists [12 m clear height](https://www.mudah.my/shah-alam-u10-logistics-park-140-000-sqft-modern-warehouse-116027931.htm) |
| Steel columns + roof trusses | Grid about 12 × 24 m (assumption); I-beams | Built (array of I-beam profiles); ref: SF [Metal Frame of the Warehouse](https://sketchfab.com/3d-models/metal-frame-of-the-warehouse-05937c3272b548dfaef68b2094a97786), SF [Steel Beam A](https://sketchfab.com/3d-models/steel-beam-a-3e20dd0a445f4ce49aa6495d08641f19) | Columns are where cameras mount, so place them first |
| Wall + roof cladding | Box-profile metal sheet | PH [Box Profile Metal Sheet](https://polyhaven.com/a/box_profile_metal_sheet); aCG [Corrugated Steel 005](https://ambientcg.com/view?id=CorrugatedSteel005) | Matches the steel cladding of [Pos Malaysia's IPC](https://www.nsbluescope.com/my/project/pos-malaysia-intergrated-parcel-centres) |
| Painted steel (columns, guard rails) | — | aCG [Painted Metal 016](https://ambientcg.com/view?id=PaintedMetal016), [Painted Metal 006](https://ambientcg.com/view?id=PaintedMetal006) | Yellow or grey columns; add scuffs at forklift height |
| Floor | Concrete slab | PH [Smooth Concrete Floor](https://polyhaven.com/a/smooth_concrete_floor) (8K); aCG [Concrete 047 A](https://ambientcg.com/view?id=Concrete047A); PH [Concrete Floor Painted](https://polyhaven.com/a/concrete_floor_painted) | No free epoxy found: lower roughness on the smooth concrete to fake it |
| Floor markings | 100 mm lines (assumption) | Yellow decal mixed over the concrete; aCG [Road Lines 001](https://ambientcg.com/view?id=RoadLines001) as a reference | Walkways, cage bays, forklift lanes |
| Dock doors | About 3.0 × 3.0 m openings (assumption); centres 3.7–4.3 m apart ([Blue Giant](https://www.bluegiant.com/architects/planning-and-design/truck-berths/)) | SF [Rolling Shutter](https://sketchfab.com/3d-models/rolling-shutter-bd01deecf45d4b429e97c0cb23116f06), SF [Roll Up Door](https://sketchfab.com/3d-models/free-garage-door-roll-up-door-1ee7db5a3d1b4237948d0c03bbda317a); texture PH [Painted Metal Shutter](https://polyhaven.com/a/painted_metal_shutter) | 6 inbound (west) + 6 outbound (north) is plenty for the demo |
| Dock platform + leveller | Dock about 1.2 m high (assumption) | SF [Loading dock](https://sketchfab.com/3d-models/loading-dock-84a7db0502a34121a0d2c8e481345b08), SF [Loading Docks](https://sketchfab.com/3d-models/loading-docks-da3471de4c7740aab2af9a06ef3c25b3); or a built ramp plate | The only leveller model found is paid; a flat steel plate is enough |
| High-bay lights | Rows at about 8–10 m | Built (disc + emission); PH [Mounted Fluorescent Lights](https://polyhaven.com/a/mounted_fluorescent_lights) for the office | No free UFO-style LED found; simple discs read fine from below |
| Outside light | — | PH [Overcast Industrial Courtyard](https://polyhaven.com/a/overcast_industrial_courtyard), PH [Factory Yard](https://polyhaven.com/a/factory_yard) | Nothing tropical found; overcast suits Malaysian daylight |
| Inside light reference | — | PH [Empty Warehouse 01](https://polyhaven.com/a/empty_warehouse_01) | Use to check how real warehouse light falls, not as the main light |
| Fire extinguishers, signs | — | PH [Korean Fire Extinguisher 01](https://polyhaven.com/a/korean_fire_extinguisher_01); signs are built decals | One per column bay near exits |

## Area-by-area asset list

The key machines have no free model: no cross-belt sorter, scan tunnel, telescopic conveyor, bag frame or logistics roll cage. **Your Claude builds those five** from simple parts, using the sizes below. Everything else is found.

### Machines to build (with real sizes)

| Machine | Real sizes to copy | Build it from |
| --- | --- | --- |
| **Cross-belt loop (Z05)** | Carriers 1500 × 540 mm at 800 mm pitch, or 850 × 440 mm at 700 mm pitch; curve radius 4 m; speed up to 3 m/s; parcels up to 50 kg ([FORTNA datasheet](https://fortna.com/wp-content/uploads/2024/10/DS-FORTNA-Cross-Belt-Sorter-1-EN.pdf)) | A closed curve path + one carrier mesh repeated along it (Array + Curve modifiers); a small black belt (aCG [Rubber 001](https://ambientcg.com/view?id=Rubber001)) on a galvanised frame (PH [Galvanized Sheet Metal](https://polyhaven.com/a/galvanized_sheet_metal)). Deck at 1.0–1.5 m so chutes slope down (assumption) |
| **Chutes (Z06) + reject chute (Z07)** | About 0.8–1.0 m wide (assumption), sloped down to the bag frame | Bent plane + Solidify, galvanised texture, destination sign on top. Refs: SF [Chute](https://sketchfab.com/3d-models/chute-98d4616410b347439ed0f7457424fec3), SF [chute 3D](https://sketchfab.com/3d-models/chute-3d-d5202c88124f41bdad4b6cf9ef61d03b) (check they are slides) |
| **Scan tunnel (Z04)** | Box over the belt, a little wider than the max parcel (100 × 70 × 70 cm) | Sheet-metal box with an open front and back, light bars inside, a small display, a weighing section before it |
| **Telescopic conveyor (Z01)** | Reaches into the truck from the dock door | 2–3 nested belt sections; belt refs below |
| **Bag frame (Z06)** | One per chute, holds an open sack at the chute end | Steel tube frame + sack (PH [Compost Bags](https://polyhaven.com/a/compost_bags) or SF [big bag](https://sketchfab.com/3d-models/big-bag-groer-sack-8db0bd844c68446ca0afcaf32078aaa7) as shape reference) |
| **Roll cage (Z10, Z11)** | 720 × 800 × 1800 mm, 2 fixed + 2 swivel castors, 3 mesh sides ([AJ Products](https://www.ajproducts.co.uk/p/3-sided-roll-cage-246786-246784)) | Tube frame + aCG [Fence 006](https://ambientcg.com/view?id=Fence006) wire-mesh opacity map. Paid fallback: [Mesh Trolley, RenderHub](https://www.renderhub.com/artemcg/mesh-trolley) ($19, wrong size, needs rescaling) |

### Found assets per zone

| Zone | Assets |
| --- | --- |
| **Z01 Inbound dock** | Telescopic conveyor (built); lorry or trailer at the door (see props); dock plate; shutter doors (see shell) |
| **Z02 Bag opening** | Bench: PH [Steel Frame Shelves 01](https://polyhaven.com/a/steel_frame_shelves_01) or SF [Workbench](https://sketchfab.com/3d-models/workbench-1f749d9458d7497e956991033ba827e2); a pile of opened sacks; short belt to induction |
| **Z03 Induction** | Straight belts: SF [Belt Conveyor](https://sketchfab.com/3d-models/belt-conveyor-b789d1fda888440387ae7750c852ade3), SF [Simple rubber conveyor](https://sketchfab.com/3d-models/simple-rubber-conveyor-0819b51c59c3407cb98f0e2c75029e30), SF [Conveyor Modular Pack](https://sketchfab.com/3d-models/conveyor-modular-pack-bf86b7433e824efeba77166d01f5e368); 2–3 standing workers |
| **Z04 Scan tunnel** | Built tunnel; roller section: SF [Industrial Conveyer Roller](https://sketchfab.com/3d-models/industrial-conveyer-roller-modular-4736d0c18e7047969639988883f0ad56); curve into the loop: SF [Curved conveyor belt system](https://sketchfab.com/3d-models/curved-conveyor-belt-system-39ff85715a134cd2a09f6e78a9dce232) |
| **Z05 Cross-belt loop** | Built (above); guard rails in painted steel; maintenance walkway |
| **Z06 Chutes + bagging** | Built chutes + bag frames; destination signs; handheld scanners: SF [Handheld Barcode Scanner with Keypad](https://sketchfab.com/3d-models/handheld-barcode-scanner-with-keypad-79d132dc44b344f7a019921e1b31c1b6) |
| **Z07 Reject chute** | Built chute with a red "REJECT / NO READ" sign; a crate of rework parcels under it |
| **Z08 Exception bench** | Desk: PH [Metal Office Desk](https://polyhaven.com/a/metal_office_desk); PH [Tool Cart](https://polyhaven.com/a/tool_cart); PH [Drawer Cabinet](https://polyhaven.com/a/drawer_cabinet); scanner; label printer (none found: model a small box with a paper slot); one **locked** roll cage for damaged parcels |
| **Z09 Oversize area** | Pallets: SF [Wooden Pallets – CC0](https://sketchfab.com/3d-models/wooden-pallets-cc0-game-asset-a9f841eab92b460f939a115dab968351), SF [Euro Pallet](https://sketchfab.com/3d-models/euro-pallet-a38a3c7ac5894db6957bebcd400a7e75), SF [Plastic Pallet](https://sketchfab.com/3d-models/plastic-pallet-0699da1b0dd04c13b5c6731c8dda75d1); big boxes; hand pallet jack |
| **Z10 Cage staging** | Rows of built roll cages with floor-marked bays and bay numbers |
| **Z11 Empty cage / bag store** | Cages pushed tightly together; stacks of folded sacks on PH [Steel Frame Shelves 02](https://polyhaven.com/a/steel_frame_shelves_02) / [03](https://polyhaven.com/a/steel_frame_shelves_03) |
| **Z12 Outbound dock** | Same doors and dock plates as Z01; cages at the door; trucks outside |
| **Z13 Supervisor office** | PH [Metal Office Desk](https://polyhaven.com/a/metal_office_desk); PH [Plastic Monobloc Chair 01](https://polyhaven.com/a/plastic_monobloc_chair_01) or SF [Office Chair](https://sketchfab.com/3d-models/office-chair-95160ce5a52f4e379f66527d2735d96c); SF [Computer Desk and Monitor](https://sketchfab.com/3d-models/computer-desk-and-monitor-cdb5226d2c3a4fc89e9b422307f81ce5); PH [Mounted Fluorescent Lights](https://polyhaven.com/a/mounted_fluorescent_lights); glass wall facing the floor |
| **Z14 Truck yard** | Vehicles (see props); SF [Bollards](https://sketchfab.com/3d-models/bollards-b5ae04dfd20b404f8a3d2e887f997c8b); PH [Concrete Road Barrier](https://polyhaven.com/a/concrete_road_barrier); cones; outdoor HDRI |
| **CCTV cameras (all zones)** | Bullet: PH [Security Camera 02](https://polyhaven.com/a/security_camera_02) (has a hood); wall mount: PH [Security Camera 01](https://polyhaven.com/a/security_camera_01); dome: SF [Dome Security Camera](https://sketchfab.com/3d-models/dome-security-camera-a5c49eefb2564c76b09aba0dc7a4d203), SF [Dome Camera \[FREE\]](https://sketchfab.com/3d-models/dome-camera-free-ab8d2a64d3894deba9af23203ba0368d). Visible camera bodies help the "cameras watch each other" rule |

## Props, people and vehicles

Parcels are the stars of every clip, so they get the most variety. Vehicles and people only need to look right from 5–8 m up.

| Item | Size to respect | Asset | Note |
| --- | --- | --- | --- |
| Cardboard boxes | 15 cm up to 100 × 70 × 70 cm, 30 kg max ([EasyParcel](https://blog.easyparcel.com/my/parcel-size-and-weight/)) | PH [Cardboard Box 01](https://polyhaven.com/a/cardboard_box_01) (worn, taped); SF [\[CC0\] Free Cardboard Box](https://sketchfab.com/3d-models/cc0-free-cardboard-box-e7a46c7b163c477296a3986323ccc826); SF [Cardboard Boxes Pack (16 sizes)](https://sketchfab.com/3d-models/cardboard-boxes-set-16-sizes-e2bfa6f3822241a49553b44c55ef3082); texture aCG [Cardboard 001](https://ambientcg.com/view?id=Cardboard001), [004](https://ambientcg.com/view?id=Cardboard004) | Randomise size, rotation, tape and label position |
| Poly flyers | A4 to A3-ish flat bags (assumption) | None free. Build: a flattened "pillow" (or a quick cloth-sim plane), grey/black/white plastic. Paid: [Poly Mailer, Free3D](https://free3d.com/3d-model/poly-mailer-plastic-bag-black-empty-9299.html) ($19) | Most Malaysian e-commerce parcels are flyers, so make lots |
| Shipping labels | \~10 × 15 cm (assumption) | Built decal: fictional brand, fake barcode, fake address | Must not be readable from CCTV anyway (see the PPM maths) |
| Look-alike pair | Two identical boxes | Same asset, different label | For the look-alike scenario |
| Sacks (full) | Waist-high when full (assumption) | PH [Compost Bags](https://polyhaven.com/a/compost_bags); PH Cement Bag; SF [big bag](https://sketchfab.com/3d-models/big-bag-groer-sack-8db0bd844c68446ca0afcaf32078aaa7); SF [Mail Bag](https://sketchfab.com/3d-models/mail-bag-1310de4c577b4e17ace4e2cafd6fdf97) | Woven-sack texture in one fictional brand colour; add a bag tag |
| Pallets | — | See Z09 | Stretch-wrapped stacks add realism |
| Forklift (electric) | — | SF [Forklift Truck](https://sketchfab.com/3d-models/forklift-truck-1567f5f71c1a40eebe487b1b8f570250), SF [forklift](https://sketchfab.com/3d-models/forklift-4438235cea46432aa9ce0c6bdacbc848) | Remove any exhaust if it isn't electric |
| Pallet jacks | — | SF [Hand pallet jack](https://sketchfab.com/3d-models/hand-pallet-jack-9db0a4f5bd6e4b35b46f86ff272387c1); SF [Electric Pallet Jack](https://sketchfab.com/3d-models/electric-pallet-jack-with-controls-acc0b7593fc9469f9ee3fd5949cd6909) | Also used to move roll cages in some hubs |
| Lorry (3–5 t box) | 9–26 ft cargo lorries are common in Malaysia ([TheLorry](https://thelorry.com/my/blog/11-types-of-lorries-you-see-in-malaysia)) | SF [Lorry](https://sketchfab.com/3d-models/lorry-3fb4343374304f51ae190d2a3625a302); SF [Box Truck](https://sketchfab.com/3d-models/box-truck-game-asset-959e25ad21014bcf9066d3f6f7e7ecb2); SF [Lorry with cargo container](https://sketchfab.com/3d-models/lorry-truck-with-cargo-container-f3651bc895224e6199eace68efa14144) | Malaysian plates (fictional) and fictional livery; right-hand drive |
| Trailer (linehaul) | 35–40 ft ([TheLorry](https://thelorry.com/my/blog/11-types-of-lorries-you-see-in-malaysia)) | SF [Truck Trailer FREE](https://sketchfab.com/3d-models/truck-trailer-free-575958a53e3d4e9f8bcfb1ee2cef67bf); SF [Container Trailer Chassis](https://sketchfab.com/3d-models/container-trailer-chassis-4179e400ef464b958bcf8416e11f87df) | One or two at inbound doors |
| Delivery van | — | SF [European Delivery Van](https://sketchfab.com/3d-models/european-delivery-van-0b2f1ad95a79419f9a092420024d329c); SF [Nissan Caravan](https://sketchfab.com/3d-models/nissan-caravan-detailed-3d-van-model-bfddc35e8b40441cbaa291ef0b120935) | Skip any branded (e.g. DHL) vans; remove makers' badges |
| Cones, bollards, barriers | — | SF [Traffic Cones](https://sketchfab.com/3d-models/traffic-cones-822f8e30bad4469e808b8c32d9c8aa10); SF [Traffic Cone](https://sketchfab.com/3d-models/traffic-cone-e9c9c21db7c44c4fb901e0c55bb86934); PH Wet Floor Sign 01; PH [Concrete Road Barrier 02](https://polyhaven.com/a/concrete_road_barrier_02) | No free rack-protector found; search "warehouse guard rail" |
| People (realistic) | Average adult height; walk 1.2–1.4 m/s | SF [Construction Worker in Safety Vest](https://sketchfab.com/3d-models/construction-worker-in-safety-vest-0ee4e54dc78b45f9bb7e26fb0d000f7e); SF [Worker Man Rigged](https://sketchfab.com/3d-models/worker-man-rigged-ca5d218c51e04c3ba96929dbe8f9b68e) | Best match for realism |
| People (CC0 base) | — | [Quaternius Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html) (CC0, rigged); [Quaternius Modular Men](https://poly.pizza/bundle/Ultimate-Modular-Men-Pack-ZiH8muWqwQ) (CC0, has a "Worker") | Add a hi-vis vest and uniform colours; the Modular Men are stylised |
| Animations | Walk, carry, lift, scan, push | [Mixamo](https://helpx.adobe.com/au/creative-cloud/faq/mixamo-faq.html): royalty-free for commercial projects, but not a CC licence | Use for renders; check before committing raw Mixamo files to the public repo |

### Getting them into Blender

[blender-mcp](https://glama.ai/mcp/servers/ahujasid/blender-mcp) can download **Poly Haven** assets by ID (the part after `/a/`, e.g. `security_camera_01`) and **Sketchfab** models by UID (the 32-character code at the end of each SF link). Two cautions:

- Its Sketchfab tool says the model must be downloadable and you must have access rights. It does **not** check NC for you, so check each licence yourself.
- It also offers Hyper3D and Hunyuan3D (AI-generated models). Leave them off: they blur the "what we built" line and break your "every frame rendered from real assets" rule.

## CCTV: a reusable design framework

Place cameras around the **points where a parcel changes hands or gets scanned**, not around the room. Every hub has the same custody points, so the same five steps work for any hub. Spoor can then ship them as a site-setup checklist.

### The 5-step framework

1. **Write the question for each zone.** Before placing a camera, write the one question its footage must answer (for example "which bag did parcel X go into?"). This is the UK *Operational Requirement* method: define where, what, how much detail, and how fast the action is ([IFSEC](https://www.ifsecglobal.com/installers/cctv-guide-setting-objectives-requirements/amp/)).
2. **Set the detail level in pixels per metre (PPM).** The DORI levels from IEC 62676-4 are 25 PPM to detect, 62 to observe, 125 to recognise and 250 to identify ([Omada](https://www.omadanetworks.com/my/support/faq/4098/)). For parcels, **observe (62 PPM)** is the useful target: a 30 cm box becomes about 19 pixels wide, enough to track it but not to read its label. Reading labels is the scan tunnel's job.
3. **Follow the coverage rules** (below).
4. **Make the time trustworthy.** Without accurate, synced timestamps, footage can't be relied on to rebuild events ([Masterclock](https://www.masterclock.com/accurate-time-stamping-for-video-surveillance.html)). Sync every camera and scanner to one internal NTP server. Spoor still fits clock offsets, because real hubs drift anyway.
5. **Test on site and record the result.** Check each camera live *and* recorded against its question, and re-check footage at 1 minute, 1 hour, 1 day, 1 week and 1 month after recording ([CPNI](https://www.cpni.gov.uk/system/files/documents/bc/82/CCTV%20for%20CNI%20Perimeter.pdf)). Save each camera's position, FOV and validity window, as your PRD already requires.

### Coverage rules

- **Every scan point is in view.** The camera sees the scanner and the parcel at the moment of the scan. This is what lets Spoor bind a scan to a track.
- **Overlap at every zone boundary.** A parcel leaving one camera's view must enter the next one's, so tracks can hand off.
- **Cameras watch each other.** Overlap views so each camera's mount is visible from another camera ([CPNI](https://www.cpni.gov.uk/system/files/documents/bc/82/CCTV%20for%20CNI%20Perimeter.pdf)).
- **Dock doors are filmed from inside, at an angle.** Facing straight out into daylight blows out the image. Real cameras use WDR (the 120 dB rating on the dome below), so model the glare but don't make it total.
- **The sorter's frame causes blind spots.** Chutes, guard rails and the raised loop block views. Check occlusion from each camera in the 2D plan.
- **Blind spots are written down.** Real hubs have gaps; your demo has one on purpose. List it in the site config so Spoor can say "no coverage here" rather than guess.

### Camera list per zone (template)

PPM below assumes the 4MP 2.8 mm dome described under *Realistic camera spec*. Its usable distance is about **1,070 ÷ PPM** metres (17 m to observe, 8.6 m to recognise).

| Zone | Question the footage must answer | Detail | Camera | Mount |
| --- | --- | --- | --- | --- |
| Inbound dock (per 2–3 doors) | Which truck and bag did the parcel arrive in? | Observe | Dome or bullet, from inside, angled | 5–6 m, column |
| Bag opening | Did every parcel from the bag reach the belt? | Recognise | Dome above the bench | 4–5 m |
| Induction | Was the parcel put on the belt, and when? | Observe | Dome looking along the belt | 4–5 m |
| Scan tunnel exit | Which parcel left the tunnel at the scan time? | Recognise | Bullet aimed at the tunnel exit | 3–4 m |
| Sorter loop | Did a parcel fall off or get stuck between carriers? | Detect / observe | Wide dome, 1 per loop corner | 6–8 m |
| Reject chute | Which no-read parcel came out here? | Recognise | Dome above the chute end | 4–5 m |
| Chute row + bagging | Which bag did the parcel go into? | Recognise | Dome per 4–6 chutes, looking down the row | 4–5 m |
| Exception bench | Was it relabelled, and with what? | Recognise | Dome above the bench | 3–4 m |
| Cage staging | Which cage, and where did it go? | Observe | Wide dome | 6–8 m |
| Outbound dock | Which cage went onto which truck? | Observe | Dome or bullet, from inside, angled | 5–6 m |
| Truck yard / gate | Which truck came and left, and when? | Observe | Bullet on the outside wall | 5–6 m |

Heights are our design assumption: I found no published hub standard for them.

### Realistic camera spec (match one real model)

Copy a real camera so the footage has true numbers. A good default is a 4MP 2.8 mm dome such as the [Hikvision DS-2CD2143G0-I](https://www.panacompu.com/panama/en/product-information/hikvision-ds-2cd2143g0-i28mm-ip-camera-for-indoors-and-outdoors-4mp-fixed-focal-lens-poe): 1/3" sensor, **2688 × 1520**, **103° horizontal × 58° vertical** field of view, up to 25 fps at 50 Hz, H.265, 120 dB WDR. Use it only as a spec; keep its brand off the model.

| Setting | Value | Why |
| --- | --- | --- |
| Resolution | 2688 × 1520 (final), 1280 × 720 (drafts) | Matches the real main stream and a typical sub-stream |
| Frame rate | 15 fps | The industry average is about 15 fps; 30 fps adds little detail for much more storage ([IPVM](https://ipvm.com/reports/frame-rate-surveillance-guide)) |
| Field of view | 103° horizontal | Copied from the datasheet |
| Lens distortion | Mild barrel distortion | Wide CCTV lenses bend straight lines near the edges |
| Shutter / motion blur | Short (about 1/50 s) | Fast parcels on the sorter blur slightly; workers don't |
| Exposure | Fixed per camera; doors brighter | Imitates WDR, which helps but doesn't fully fix glare |
| Compression | H.265 or H.264 at low bitrate | Blocky edges and smeared detail are the strongest "real CCTV" cue |
| On-screen display | Camera name + date/time burned in, top-left | Every real NVR does this; the time must come from the *camera's* drifting clock, not the true time |
| Defects (some clips only) | Dropped frames, one camera offline, a dirty lens | Feeds your camera-outage scenario and tests Spoor honestly |

### Privacy (Malaysia)

CCTV recordings count as personal data under Malaysia's PDPA 2010 ([Malay Mail](https://www.malaymail.com/news/malaysia/2019/07/23/cctv-recordings-protected-under-personal-data-protection-act-says-deputy-mi/1774090)). For a real hub rollout, include CCTV notice signs, a stated purpose and a retention period. For the demo, people are anonymous low-detail figures and Spoor uses anonymous tracks only, which matches your PRD.

## Make it look real: realism checklist

Real CCTV looks real because of its **flaws**, and a real hub looks real because of its **mess**. A clean, evenly lit, sharp render is what gives synthetic footage away. Work through both lists, then run the blind test at the end.

### The hub (scene)

| Area | What makes it real | How |
| --- | --- | --- |
| Lighting | LED high-bays in rows, a bit uneven; docks brighter and cooler. Guides suggest 30–50 fc (about 320–540 lux) and 5000 K or more at loading docks ([PacLights](https://www.paclights.com/learning-center/ies-warehouse-lighting-levels-a-complete-guide/)) | Area lights in a grid; vary strength ±10%; leave one light dimmer or off |
| Daylight | Open dock doors spill hard daylight onto the floor | Outdoor HDRI + sun; the brightest thing in dock views |
| Floor | Tyre marks, scuffed and faded yellow lines, oil stains at docks, dust in corners | Layer grime decals and a roughness map over the concrete; wear lines most where forklifts turn |
| Clutter | Stretch-wrapped pallets, piles of empty bags, torn tape, a crooked trolley, cables, standing fans | Scatter by hand near work areas; keep walkways clear (real hubs do) |
| Parcels | Mostly grey, black and white poly flyers plus brown boxes of many sizes, all with labels and tape | Up to 100 × 70 × 70 cm / 30 kg, J&T's limit ([EasyParcel](https://blog.easyparcel.com/my/parcel-size-and-weight/)); randomise size, colour, label position and rotation |
| Signs | Chute destination boards (Penang, Johor Bahru, Kuching), Malay/English safety signs ("AWAS", "DILARANG MEROKOK"), floor arrows | Flat planes with simple decal textures; fictional brand only |
| People | Hi-vis vests, walking 1.2–1.4 m/s, some standing idle, bending to lift | Rigged anonymous figures with a few looping actions; never all moving at once |

### The CCTV (camera + video)

Add these on top of the spec table above.

| Real CCTV flaw | What it looks like | How to fake it |
| --- | --- | --- |
| Smart codec | Moving things keep detail; the still background is compressed more ([Dahua](https://us.dahuasecurity.com/4-cool-things-smart-h-265-can-do/)) | Low bitrate H.265; let the encoder smear static areas |
| Keyframe pulse | The image "breathes" or sharpens every 1–2 s when a new full frame arrives | ffmpeg: keyframe every 15–30 frames at 15 fps |
| Noise + denoise smear | Grain in dark corners; soft ghost trails behind moving people | Add noise before encoding, then a temporal blur on moving areas |
| Rolling shutter | Fast objects lean or wobble ([i-PRO](https://iproiot.atlassian.net/wiki/spaces/FAQ/pages/1012368433/Why+are+network+camera+images+distorted)) | Slight skew on the sorter-loop cameras only |
| Cheap fixed lens | Barrel distortion, darker corners, soft edges, colour fringes at the edges | ffmpeg `lenscorrection` + vignette; slight blur toward the edges |
| Auto exposure | Image dims and colour shifts when a dock door opens to daylight | Animate exposure and white balance over 1–2 s on dock cameras |
| Dome bubble | Faint reflection, a smudge or spider web on one camera | A semi-transparent overlay on 1–2 cameras only |
| Mount angle | High, looking down 20–45°, never eye level; horizon sometimes slightly tilted | Set in Blender; tilt one camera 1–2° |
| Frame timing | Uneven gaps, an occasional repeated or dropped frame | Drop or duplicate random frames; log them in ground truth |
| On-screen text | Date/time and camera name in a plain NVR font, from the camera's own drifting clock | ffmpeg `drawtext` per camera with its clock offset |
| Night (yard only) | Outdoor cameras switch to black-and-white infrared at night | Only if a scenario runs at night; inside stays lit and in colour |

### Blind test (realism check)

1. Grab 3 stills from real hub CCTV clips on YouTube (search *"J&T sorting CCTV"* or *"parcel hub CCTV"*). Use them only as a private reference; they never go in the repo.
2. Mix them with 3 of your rendered stills at the same size and compression.
3. Ask 5 friends which are real. **Goal: they can't do better than guessing.**
4. For every still they spot, ask what gave it away, and fix that first.

However real it looks, the footage is still labelled **synthetic footage of a fictional hub** in the repo and the demo. That keeps you inside the rules and your PRD.

## Blender best practices

The film workflow you watched is a good base, but your job is different: it made one cinematic film, while you need **many fixed CCTV cameras, many scenarios, plus ground-truth data**. So you need cheap renders and exact numbers more than pretty light.

### Keep from the Mr omi workflow

| Practice (from the video and your screenshots) | Use it like this |
| --- | --- |
| Claude drives Blender through Python, over a live bridge on `127.0.0.1` | Use Blender MCP or the socket bridge. Keep it bound to localhost only, never `0.0.0.0` |
| "Don't build the car. Find one." | Find every prop (cages, trucks, forklifts, boxes). Your Claude only builds the shell, floor markings and sorter path |
| Poly Haven + ambientCG for CC0 materials and lighting | Same, plus Sketchfab CC BY with credits |
| Bake simulations to disk once | Bake any falling-parcel rigid body once, so all 11 cameras see the same fall |
| Cut light bounces nobody can see | Even more true for CCTV: compression hides fine light detail |
| Adaptive sampling + AI denoise | Use for the **cinematic** pass only (see the render plan) |
| "No AI images, every frame rendered in Blender" | Keep this rule. It's also what makes the footage fair test data |

### Add for a CCTV hub

1. **Real scale.** 1 Blender unit = 1 metre. Apply scale on every imported asset, then check it against the sizes in this pack (a roll cage must measure 0.72 × 0.80 × 1.80 m).
2. **One collection per zone, named like Spoor's zones.** `Z01_inbound_dock`, `Z05_sorter`, `Z07_reject_chute`… The same IDs appear in Blender, the site config and the floor plan.
3. **Cameras named and spec'd like the real camera.** `CAM_03_reject_chute`, 103° horizontal FOV, 2688 × 1520, 15 fps. Store each camera's height and purpose as custom properties.
4. **Export camera truth to JSON.** For each camera, write position, rotation, focal length and sensor size, and compute the pixel focal length: fx = focal\_mm × image\_width\_px ÷ sensor\_width\_mm. Spoor's calibration can then be scored against the truth.
5. **Export parcel truth to JSON.** Per frame: each parcel's world position, which bag/cage/truck it is in, and which cameras can see it. Keep this file away from inference code, as your PRD requires for lab ground truth.
6. **Animate parcels on paths, not physics.** Belts and the sorter loop move parcels along curves (Follow Path), which is exact and repeatable. Use physics only for fall-offs.
7. **Reuse, don't copy.** Parcels, cages and chutes are collection instances (or Geometry Nodes scatter). Keep the assets in a separate library `.blend` and *link* them, so the main file stays small.
8. **Same seed, same result.** Fix random seeds for parcel placement and the scan log, so a scenario re-renders the same way.
9. **One Blender version for the whole build.** The video used Blender 5.2; pick one and write it in the README.

### Render plan (fast enough for many scenarios)

The frame count adds up fast: 11 cameras × 60 s × 15 fps is about **9,900 frames per scenario**, or about **119,000 for 12 scenarios**. Plan for that.

| Pass | Engine | Resolution | Settings |
| --- | --- | --- | --- |
| Drafts | EEVEE | 1280 × 720 | Check movement and camera views only |
| CCTV final | EEVEE | 2688 × 1520 | Fixed lighting, no motion-blur tricks, no depth of field. CCTV compression hides EEVEE's limits |
| Cinematic (viral clip) | Cycles | 2K | Your screenshot settings: adaptive sampling, OptiX denoise, low bounces |

- Render **image sequences (PNG)**, not video, from the command line in background mode. A crash then loses one frame, not the whole clip.
- **Make it look like CCTV after rendering, with ffmpeg:** lens distortion (the `lenscorrection` filter), a little noise, the burned-in camera name + drifting clock (`drawtext`), then H.265 at a low bitrate. Write the same distortion values and clock offsets into the ground-truth JSON.
- Give each camera its own clock offset in the overlay, matching the `scan_simulated` log offsets in your plan. That's how Spoor's `fit_clock()` gets a real test.

## Copy-paste brief for your Claude

Paste this together with the link to this doc. Fill in the two blanks first.

```markdown
# Task: 2D plan for the Spoor parcel hub (no Blender yet)

Read the reference pack first: <link to this doc>.
My look choice: <name the hub or video you liked most>.

## Output
1. `hub_spec.yaml` — every zone, asset, camera and door with real sizes in metres.
2. `hub_plan.svg` — a top-down plan at 1:200 with zone IDs, flow arrows,
   camera positions and their view cones, and the blind corner marked.

## Building
- Steel portal-frame shed, 10–12 m eaves, L-flow: inbound on the west wall,
  outbound on the north wall, blind corner in the inside corner of the L.
- Truck yard outside both dock walls.

## Zones (use these IDs everywhere)
Z01 inbound dock (telescopic conveyors) · Z02 bag opening · Z03 induction ·
Z04 scan tunnel · Z05 cross-belt loop (one raised level) · Z06 chutes + bagging ·
Z07 reject chute · Z08 exception bench · Z09 oversize area · Z10 cage staging ·
Z11 empty cage/bag store · Z12 outbound dock · Z13 supervisor office · Z14 truck yard

## Sizes to respect
Use the sizes in the pack (roll cage 0.72 × 0.80 × 1.80 m, sorter curve radius
≥ 4 m, carrier pitch 0.7–0.8 m, max parcel 1.0 × 0.7 × 0.7 m / 30 kg).
If a size is missing, say so and propose one; don't invent silently.

## Cameras
Follow the pack's CCTV framework: one question per camera, observe-level
(62 PPM) detail at minimum, every scan point in view, overlap at zone
boundaries, one camera on the reject chute, dock doors filmed from inside.
Camera spec: 2688 × 1520, 103° HFOV, 15 fps. Show each camera's coverage and
the PPM at its far edge.

## Realism (non-negotiable)
The hub and the CCTV must pass the pack's blind test: friends can't tell our
stills from real hub CCTV. In the spec, list for each zone the wear, clutter,
signs and lighting from the realism checklist, and for each camera its flaws
(codec, noise, lens, exposure, clock offset).

## Rules
- Fictional brand only; no real courier names or logos.
- Only CC0 / CC BY assets; list each in the spec with its URL and licence.
- Check the plan against the hackathon section of the pack before you finish.
- Show me the plan and wait for my OK before anything goes into Blender.
```

## Sources

Asset links are in their tables. Poly Haven and ambientCG pages were checked as CC0. Sketchfab links came from search results; their licences weren't confirmed.

**Hubs and equipment**

- [Pitney Bowes sortation layout (MMH)](https://www.mmh.com/article/sortation_and_robotics_layout_at_pitney_bowes/Automation)
- [DHL Brussels hub (BEUMER PDF)](https://www.beumergroup.com/app/uploads/2019/11/DHL-Brussels-hub.pdf)
- [GDEX Auto Hub press release](https://gdexpress.com/?p=9363)
- [LG CNS / PosLaju cross-belt (Korea Times)](https://www.koreatimes.co.kr/business/tech-science/20151122/lg-cns-sets-sights-on-logistics-automation)
- [Pos Malaysia IPC cladding (NS BlueScope)](https://www.nsbluescope.com/my/project/pos-malaysia-intergrated-parcel-centres)
- [Ninja Van Shah Alam warehouse](https://www.parcelandpostaltechnologyinternational.com/?p=18377)
- [J&T Setia Alam hub (NST)](https://www.nst.com.my/amp/business/corporate/2025/06/1229628/jt-unveils-logistics-hub-daily-capacity-12mil-parcels)
- [J&T behind the scenes (TheSmartLocal)](https://thesmartlocal.com/read/jt-express-behind-the-scenes/)
- [J&T H1 2026 volumes (Logistics Matters)](https://www.logisticsmatters.co.uk/?p=39169)
- [Skynet Hounslow crossbelt (Logistics Matters)](https://logisticsmatters.co.uk/Crossbelt-sorter-boosts-parcel-throughput)
- [Hermes Rugby / BEUMER video description (paketda)](https://www.paketda.de/logistik-paketsortierung.php)
- [FORTNA cross-belt sorter datasheet](https://fortna.com/wp-content/uploads/2024/10/DS-FORTNA-Cross-Belt-Sorter-1-EN.pdf)
- [Roll cage dimensions (AJ Products)](https://www.ajproducts.co.uk/p/3-sided-roll-cage-246786-246784)
- [Truck berth spacing (Blue Giant)](https://www.bluegiant.com/architects/planning-and-design/truck-berths/)
- [Shah Alam logistics shed listing (Mudah)](https://www.mudah.my/shah-alam-u10-logistics-park-140-000-sqft-modern-warehouse-116027931.htm)
- [Malaysian courier size limits (EasyParcel)](https://blog.easyparcel.com/my/parcel-size-and-weight/)
- [Malaysian lorry types (TheLorry)](https://thelorry.com/my/blog/11-types-of-lorries-you-see-in-malaysia)

**CCTV**

- [CCTV Operational Requirements (IFSEC)](https://www.ifsecglobal.com/installers/cctv-guide-setting-objectives-requirements/amp/)
- [CCTV for perimeter security (CPNI PDF)](https://www.cpni.gov.uk/system/files/documents/bc/82/CCTV%20for%20CNI%20Perimeter.pdf)
- [What is DORI? (Omada)](https://www.omadanetworks.com/my/support/faq/4098/)
- [Frame rate guide (IPVM)](https://ipvm.com/reports/frame-rate-surveillance-guide)
- [Hikvision DS-2CD2143G0-I spec (Panacompu)](https://www.panacompu.com/panama/en/product-information/hikvision-ds-2cd2143g0-i28mm-ip-camera-for-indoors-and-outdoors-4mp-fixed-focal-lens-poe)
- [Accurate time-stamping (Masterclock)](https://www.masterclock.com/accurate-time-stamping-for-video-surveillance.html)
- [Smart H.265 (Dahua)](https://us.dahuasecurity.com/4-cool-things-smart-h-265-can-do/)
- [Rolling-shutter distortion (i-PRO)](https://iproiot.atlassian.net/wiki/spaces/FAQ/pages/1012368433/Why+are+network+camera+images+distorted)
- [Warehouse lighting levels (PacLights)](https://www.paclights.com/learning-center/ies-warehouse-lighting-levels-a-complete-guide/)
- [CCTV recordings under PDPA (Malay Mail)](https://www.malaymail.com/news/malaysia/2019/07/23/cctv-recordings-protected-under-personal-data-protection-act-says-deputy-mi/1774090)

**Blender workflow**

- [Mr omi: 3D short film with Claude in Blender (YouTube)](https://www.youtube.com/watch?v=BagZ55ac4xs)
- [blender-mcp README (Glama mirror)](https://glama.ai/mcp/servers/ahujasid/blender-mcp)
