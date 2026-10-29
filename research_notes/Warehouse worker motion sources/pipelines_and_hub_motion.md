# Synthetic-data pipelines for warehouse workers, and real parcel-hub task motion

Research date: 2026-10-30. Sources are cited inline. Vendor and job-posting figures are labelled as such. Anything I could not source is under Gaps.

## Q1. How NVIDIA Omniverse / Isaac Sim animates people (omni.anim.people, IRA / Replicator Agent)

### Takeaway
Isaac Sim's people simulation runs on navmesh locomotion plus a short list of scripted commands: GoTo, Idle, LookAround, Sit, Queue and Dequeue. "Custom commands" just play a retargeted clip in place or next to an object. The documentation describes no pick-up, carry or hand-contact feature. NVIDIA's own large warehouse datasets mostly show people walking and standing, and use Cosmos Transfer for appearance realism, not for object manipulation.

### Cited Findings
- Built-in commands: `GoTo x y z rot` (one point or a sequence of points), `Idle duration`, `LookAround duration` (stands still and turns the head left to right), `Sit prim_path duration`, `Queue queue_name` and `Dequeue queue_name x y z rot`. — [Isaac Sim 5.1 Actor Control](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/action_and_event_data_generation/ext_replicator-agent/actor_control.html)
- Custom-command templates are `Timing` (play a clip for a duration), `TimingToObject` (walk to an object that matches a filter, then play a clip) and `GoToBlend` (walk while blending in an upper-body clip through a joint filter). Each clip must be a USD SkelAnimation retargeted to `Biped_Setup`, and is registered in `[omni.anim.people]/data/custom_command_tracking.json`. Optional attributes set start/end time, looping and random min/max duration. Random command sequences come from `character_command_transition_map.json`. — [Isaac Sim 5.1 Actor Control](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/action_and_event_data_generation/ext_replicator-agent/actor_control.html)
- The only example custom clips shipped are `Isaac/People/Animations/push_button.skelanim.usd` and `type_keyboard.skelanim.usd`. The page has no pick-up or carry action. "Object interaction" means sitting on a seat prim, or walking to an object and playing a clip. — [Isaac Sim 5.1 Actor Control](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/action_and_event_data_generation/ext_replicator-agent/actor_control.html)
- Documented limitations: dynamic obstacle avoidance is "best effort and not guaranteed", so characters can walk into each other or into static obstacles; turning in place rotates the whole body; Sit needs a seat scaled to fit the clip plus `walk_to_offset` and `interact_offset` Xforms; a seated character stands up before running an injected command. — [Isaac Sim 5.1 Actor Control](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/action_and_event_data_generation/ext_replicator-agent/actor_control.html)
- IRA (Isaac Sim Replicator Agent) is a Kit extension built on omni.anim.graph, omni.anim.navigation and omni.replicator.core. It spawns characters in a warehouse scene and writes 2D and 3D boxes. It is marked beta in the 4.5 docs. NVIDIA's stated motivation is that collecting real data for people detection and tracking is costly and does not scale. — [IRA tutorial 4.5](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/replicator_tutorials/tutorial_replicator_agent.html); [IRA 5.0](https://docs.isaacsim.omniverse.nvidia.com/5.0.0/action_and_event_data_generation/tutorial_replicator_agent.html)
- IRA output has been used to fine-tune TAO ReIdentificationNet for multi-camera tracking. NVIDIA calls fine-tuning on data from the specific scene "crucial" for cutting ID switches. — [edge-ai-vision / NVIDIA blog reprint 2024](https://www.edge-ai-vision.com/2024/07/enhance-multi-camera-tracking-accuracy-by-fine-tuning-ai-models-with-synthetic-data/)
- The NVIDIA PhysicalAI-SmartSpaces dataset (AI City Challenge 2024/2025, CC-BY-4.0) is generated in Omniverse, augmented with Cosmos Transfer and auto-labelled in Isaac Sim. The 2024 split has 90 scenes, 212 h of video, 953 cameras and 2,481 person objects. The 2025 split adds 3D boxes and classes for forklifts, NovaCarter, Transporter and humanoid robots. Later cards report about 280 h from about 1,800 cameras. The 2026 update adds real test scenes Warehouse_026 and Warehouse_027. — [HF dataset card](https://huggingface.co/datasets/nvidia/PhysicalAI-SmartSpaces); [Tang blog 2025](https://zhengthomastang.github.io/posts/2025/03/blog-post-1); [HF discussion 21](https://huggingface.co/datasets/nvidia/PhysicalAI-SmartSpaces/discussions/21/files)
- A 2026 Cosmos 3 paper describes a warehouse dataset in which worker spawning, character-library sampling, camera placement and per-run seeds are randomised and reproducible. — [arXiv 2606.02800](https://arxiv.org/pdf/2606.02800)

### Inferences
- The leading off-the-shelf pipeline does not do hand-object contact. Its labels cover tracking and ReID (boxes, IDs), not manipulation. A dataset with workers visibly picking, carrying and placing parcels would therefore go beyond NVIDIA's public tooling, which is a differentiator. It also means there is no ready-made reference to copy.
- The `GoToBlend` pattern (upper-body clip layered over locomotion with a joint filter) is the industry-standard way to approximate "carry while walking". A Blender pipeline can match it with an upper-body carry action over a walk cycle, plus a child-of or IK constraint parenting the parcel to the hands.
- NVIDIA uses Cosmos Transfer, a generative restyle, to close the appearance gap. That suggests it treats appearance, not motion, as the main sim-to-real gap for detection and tracking.

### Gaps
- I could not retrieve the full list of locomotion and idle clips shipped with omni.anim.people; the 4.2 docs page returned 404. Only the two custom example clips are confirmed.
- I found no NVIDIA documentation or forum post confirming any official pick-up or carry support with hand IK in omni.anim.people or IRA up to 5.1.

## Q2. Unity Perception / Synthetic Humans, Unreal MetaHuman + Motion Matching, and other synthetic human / industrial datasets

### Takeaway
Published synthetic-human generators (PeopleSansPeople, Unity Synthetic Humans) drive characters with small libraries of Mixamo or mocap clips retargeted to scanned humans, with no object interaction. Unreal Motion Matching gives high-quality locomotion through pose search, but manipulation still has to be authored. Industrial HOI synthetic-data work finds that synthetic data helps most as pretraining when real labels are scarce, and that gains grow with better alignment of objects, grasps and environment.

### Cited Findings
- PeopleSansPeople (Unity) uses 28 scanned RenderPeople humans and 39 Mixamo animations (idle, walk, run, planking, break-dance, fighting). The team added a control rig and retargeted every clip to the RenderPeople assets. — [arXiv 2112.09290](https://arxiv.org/pdf/2112.09290)
- Unity Synthetic Humans is a package for "Unity Perception compatible synthetic people". I found no public statement of its animation or interaction capabilities. — [Unity AnthroNet page](https://unity-technologies.github.io/AnthroNet)
- Unreal Motion Matching is "a query-based animation pose selection system" in the Pose Search plugin. It queries channels such as bone position and velocity, and foot channels default to foot_l and foot_r. Epic points to the Game Animation Sample Project as the advanced reference. — [Epic docs: Motion Matching](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-matching-in-unreal-engine)
- A secondary source says Motion Matching keeps foot contact naturally because it selects frames whose foot contact state matches. — [mocaponline guide](https://mocaponline.com/blogs/mocap-news/motion-matching-games-guide)
- Industrial egocentric HOI: pretraining on photo-realistic synthetic data and fine-tuning on real data raised active-object mAP from about 22% to about 36%, compared with real-only training. — [arXiv 2306.12152](https://arxiv.org/pdf/2306.12152); [arXiv 2204.07061](https://www.arxiv.org/pdf/2204.07061)
- HOI-Synth (2026): synthetic data plus 10% of the real labels gave Overall AP gains of +5.67 (VISOR), +8.24 (EgoHOS) and +11.69 (ENIGMA-51). Effectiveness "consistently improves with better synthetic-real alignment in objects, grasps, and environments." — [arXiv 2603.29733](https://arxiv.org/abs/2603.29733)
- Models trained only on synthetic data lagged real-trained models by about 30–40 AP in one 2023 study. — [arXiv 2312.02672](https://arxiv.org/html/2312.02672v3)
- Carried-object detection from surveillance video (Damen and Hogg) aligns a person's foreground over a short sequence into a temporal template and compares it with exemplars of unencumbered pedestrians. Carried objects show up as protrusions from the silhouette. — [ECCV 2008](https://eprints.whiterose.ac.uk/74697/4/eccv08.pdf); [project page](https://dimadamen.github.io/BaggageDetection/baggage.htm)

### Inferences
- In surveillance-style vision, a carried parcel is recognised mainly as a silhouette change and a co-moving blob attached to the torso and arms, not by finger detail. What matters most is that the parcel stays rigidly locked to the hands and torso and moves with them, with no lag, jitter or drift.
- "Grasp alignment matters" (HOI-Synth) argues for the right hand placement (two palms on opposite parcel faces, or underneath it) even though fingers are not resolvable.

### Gaps
- I found no published synthetic warehouse or parcel-hub CCTV dataset in which workers physically pick, carry and place parcels. The SmartSpaces classes are people, robots and forklifts.
- No paper found reports which animation limitations hurt sim-to-real transfer specifically for warehouse person tracking.

## Q3. What hand-object fidelity is visible at CCTV distance; which animation errors viewers notice

### Takeaway
Action recognition still works for figures 20–40 px tall, so 100–200 px workers carry plenty of gross-motion information, but fingers are effectively unresolvable. Perception studies show viewers are very sensitive to foot sliding (under about 21 mm is detectable in most conditions) and to hands that do not touch the object surface. Hands slightly inside an object hurt plausibility less than hands floating off it.

### Cited Findings
- Efros et al. targeted recognition "at resolutions where a whole person may be, say, 30 pixels tall", using noisy optical-flow descriptors. — [Efros ICCV 2003](https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/human/efros-iccv03.pdf)
- Far-field action work targets figures under 40 px, where limbs can be about 3 px wide. — [typeset copy](https://typeset.io/pdf/recognizing-human-action-from-a-far-field-of-view-ogyq58loiv.pdf)
- In the UT-Tower aerial benchmark the average person is about 20 px tall. A region-based mixture model reports near-perfect accuracy on it, and describes typical far-field figures as 20–50 px. — [SDHA 2010](https://cvrc.ece.utexas.edu/SDHA2010/Aerial_View_Activity.html); [UTS paper](https://opus.lib.uts.edu.au/handle/10453/54553)
- A study using simulated Unity avatars at extreme low resolution (1 px up to 10×10) reached 75.7% accuracy over 9 actions with five single-pixel cameras at 30 Hz. Spatial resolution had the largest effect. — [Dai et al. CVPRW 2015](https://openaccess.thecvf.com/content_cvpr_workshops_2015/W08/papers/Dai_Towards_Privacy-Preserving_Activity_2015_CVPR_paper.pdf)
- Footskate: participants perceived "even very low levels of footsliding (<21 mm in most conditions)", and preferred cleaned-up animations whatever the size of the correction. Simple limb-lengthening beat IK plus trajectory smoothing. — [Pražák, Hoyet, O'Sullivan, SCA 2011](https://diglib.eg.org/handle/10.2312/SCA.SCA11.287-294)
- Simple camera motion may raise the threshold for noticing foot slipping, i.e. help mask it. — [Perceptual thresholds for foot slipping (OSU thesis)](https://ir.library.oregonstate.edu/concern/honors_college_theses/6395w911w?locale=en)
- For third-party viewers of mixed-reality object handling, hands placed away from an object's surface hurt plausibility more than hands placed inside its boundaries. Automatically resizing the object to match the distance between the actor's hands significantly improved plausibility ratings. — [Hough, Williams, Athwal via search result (IEEE Access 2021)](https://doaj.org/article/9460b87d47244aecabf4f8d95e8bd037)
- TOCH: fixing hand-object penetration with only minor pose changes "largely enhanced" perceived realism. — [arXiv 2205.07982](https://arxiv.org/pdf/2205.07982)
- Slightly inaccurate hand and finger motion gives the same comprehension as accurate motion, but may change the viewer's impression of the character. — [Jörg et al., NSF PAR](https://par.nsf.gov/biblio/10394435)
- In crowd perception, update rate, linear velocity, motion complexity and group size significantly affected perceived smoothness. Character type, clothing and scene complexity did not. — [McDonnell, Newell, O'Sullivan "Smooth Movers" SCA 2007](https://unpaywall.org/10.2312%2FSCA%2FSCA07%2F259-270)
- Low-poly geometry reproduces the motion of high-resolution models worse than impostors do. Perceptual equivalence depends on camera distance. — [McDonnell et al. 2005](https://edepositireland.ie/handle/2262/18219)

### Inferences
- Pixel budget, as arithmetic: a 1.7 m worker at 100–200 px gives about 0.6–1.2 px per cm. A 30 cm parcel is about 18–35 px across, a hand (about 19 cm long) about 11–22 px, a finger about 1–2 px. Grip shape is invisible. What is visible is whether the parcel sits between the two hands, at the right height, and moves rigidly with them.
- A 21 mm foot slide is about 1.2–2.5 px at that scale. One frame's slide is near the noise floor, especially after H.265 smoothing. But cumulative sliding over a stance phase (often 5–20 cm in uncorrected retargets) is clearly visible against a static floor, and the camera is static, so there is no camera-motion masking. Foot locking should take priority.
- The priority order these sources support at CCTV distance: (1) feet planted and no sliding; (2) parcel attached at the right hand height with no gap between hands and box (slight penetration beats a visible gap); (3) no pops or teleports at transitions; (4) plausible timing and velocity; (5) finger detail, which is barely relevant.

### Gaps
- I found no study measuring human detection of hand-object gaps or penetration at surveillance resolution or under H.265 compression specifically.
- I did not retrieve the threshold values from the OSU foot-slip thesis or the distance values from McDonnell 2005.

## Q4. Real parcel-hub task motion facts

### Takeaway
Manual sorter induction runs at about 600–2,000 parcels/h per station (about 1.8–6 s per parcel). Operators place one parcel at a time, label up, singulated, sometimes after a scan. Manual trailer unloading onto an extendable conveyor runs at about 600–1,200 parcels/h per person (about 3–6 s per parcel). Roll cages are pushed, not pulled, at walking pace, with handles at about 1,000 mm. Bags at chutes are filled, tied off by hand and moved to cages. Ring scanners worn on the fingers are the standard hands-free scanning tool.

### Cited Findings — manual induction
- Vendor-neutral guide: practical ceiling for a manual station is about 1,500–2,000 items/h, with items taken from a feed conveyor or tote. — [motiontech / logifrontier search summary](https://www.motiontech.co.uk/sorter-induction)
- Practitioner field observation: one manual induction station "averages six or seven hundred parcels an hour, with big swings". When freight piles up, workers "slam two or three cartons onto the belt at once"; when it thins out, they idle; and they "slow down when they're tired". One site reached about 7,000/h from 4 stations (3 staffed), and about 9,000/h from 6 stations through peak. — [logifrontier](https://www.logifrontier.com/en/article/sorter-induction-metering-gap-control-guide)
- Older carton-encoding figure: an operator can induct up to 50 cases/min, about 30 on average. — [Plant Engineering](https://www.plantengineering.com/articles/conveyor-sortation-systems/)
- Bell & Howell parcel sorter listing (vendor/resale): 5,000 pcs/h with 1 operator in barcode mode (no orientation needed). Label/OCR mode is 5,000 pph with 2 operators, because parcels must be oriented. — [gebrauchtmaschinen listing](https://www.gebrauchtmaschinen.de/bell+%26+howell-m/gm-798-4973)
- Induction-conveyor patents: the feeder presents about 3,000–5,000 parcels/h to the operator. — [EP3099607](https://data.epo.org/publication-server/rest/v1.2/publication-dates/20210630/patents/EP3099607NWB1/document.html)
- Method: the operator places one carton at a time and holds the next until the previous one clears the induction sensor or is accepted. The operator scans and confirms a successful read and destination before releasing it. — [Sortation induction SOP template](https://www.mangoapps.com/templates/sop/sortation-induction-standard-operating-procedure)
- Label-up placement: items are placed "(effortlessly label up) on the belt". Operators arrange parcels "facing up and in a single file" before they are inducted and scanned. — [MHI spec PDF](https://og.mhi.org/media/members/16501/132996955614236997.pdf); [patent 9776215](https://patents.justia.com/patent/9776215)
- Vision QC at induction lanes gives the operator a green or red light and sends failures to an exception chute. — [Plus One CheckOne](https://automationdistribution.com/parcel-induction-qc-plus-one-robotics)
- Robotic comparison: Vanderlande Auto Induct picks 1,500–1,700 items/h (20 g–5 kg), marketed as replacing manual induction. — [Vanderlande](https://www.vanderlande.com/us/news/adapt-to-regulatory-changes-improve-worker-wellbeing-and-deliver-operational-excellence-with-auto-induct/)

### Cited Findings — trailer unloading
- Manual singulated unloading onto an extendable conveyor (1D flow): 850–900 pph with 1 operator, 1,350–1,450 pph with 2. Bulk 2D flow: 1,100–1,300 pph (1 operator), 1,750–2,100 pph (2). Bulk 3D: 1,300–1,600 pph (1), 1,800–2,250 pph (2). — [Parcel Industry, "Choosing a Singulation Method"](https://parcelindustry.com/print-article-4901-permanent.html)
- Caljan puts manual trailer unloading at about 600–800 parcels/h. Its AutoUnloader reaches about 5,000/h, "six times faster than manual". Parcels can weigh up to 31.5 kg. — [Caljan FAQ](https://caljan.com/?p=1433); [Caljan AutoUnloader press release](https://www.supplychaindive.com/press-release/20240919-caljan-expands-its-product-portfolio-with-autounloader-for-trailers/)
- Patent: one person unloading standard packages with an extendible conveyor may reach about 1,000 pph; irregular sacks and items run about 200–500 pph. — [US20120087770A1](https://patents.google.com/patent/US20120087770)
- UPS unloader job postings (third-party sites, low reliability): 800–1,200 pph sustained; another listing gives 700–1,300. — [job listing](https://ups.stoncareer.it.com/jobs/newark/22-25hr-package-unloader-job-in-newark-1bb2b8.html); [Handshake](https://app.joinhandshake.com/jobs/2811355/share_preview)
- Körber says unloading "currently requires a team of two, and a lot of physical effort". ErgoUnload claims up to 3,000 pph per dock with one operator and cuts lifting effort to below 10%. — [Körber news](https://www.koerber.com/en/about-us/news-and-press/ergounload-semi-automatic-parcel-handling); [datasheet](https://koerber-supplychain.com/fileadmin/koerbersupplychain/Homepage/Downloads/Case_Study/Koerber_ErgoUnload_Datasheet.pdf)

### Cited Findings — posture and ergonomic load
- Thai parcel sorters (n=22): 12-month complaints were lower back 86%, shoulders/neck 77% and upper back 68%. REBA put the sorting and preparation stages at high or very high risk. — [Thai J. Ergonomics 2025](https://he01.tci-thaijo.org/index.php/TJE/article/view/270847)
- Indonesian courier warehouse: tiered stacking storage had the highest REBA risk (awkward postures, static and repetitive work). — [JOSI](https://josi.ft.unand.ac.id/index.php/josi/article/download/7/5/9)
- Chalmers thesis: oversized or irregular parcels averaged 3.6% of volume. It recommends cage lifters and other mechanical aids. — [Chalmers ODR](https://odr.chalmers.se/items/defa3273-498d-47a5-955a-26ca5f226dca)

### Cited Findings — bagging at chutes
- Sorter-to-bag systems discharge parcels down chutes into bags held open by sack-holder frames; patents describe actuators that open one bag mouth while closing the other. — [US12012244B2](https://patents.google.com/patent/US12012244)
- Manual workflow (layout document of unclear origin): associates scan the shipment and cage, put the shipment in mapped cage bags, and "when full, associate tie the bags properly". Tied bags go onto a takeaway conveyor and are then put into cage trolleys "and make rows". — [Scribd layout process](https://www.scribd.com/document/712347487/Layout-Process)
- Siemens Logistics design: a full bag is cleared from a small-parcel chute and the chute returns to active status in under 2 s. — [MODEX 2020 innovation award](https://2020.modexshow.com/attendees/innovation-award.aspx?&id=700)
- Vanderlande PARCELTRAX is an auto-consolidated bagging system that fits under small-item sorters. — [Vanderlande](https://www.vanderlande.com/systems/loading/parceltrax/)

### Cited Findings — roll cages
- HSE: push rather than pull, move no faster than walking speed, larger wheels reduce force, handles at about 1,000 mm (to keep fingers away from cage corners). Most operators cannot see over 1,400 mm when cages are 1,550–1,830 mm tall. — [HSE roll cages](https://www.hse.gov.uk/food/safety-hazards/roll-cages-wheeled-racks.htm)
- HSE push/pull guideline forces: starting or stopping 20 kg (about 200 N) for men and 15 kg (about 150 N) for women; keeping a load moving 10 kg (about 100 N) for men and 7 kg (about 70 N) for women. — [HSE push/pull assessment](https://www.hse.gov.uk/msd/pushpull/assessment.htm)
- Botti et al. 2020 (Applied Ergonomics 85:103080): 96 subjects did 2,592 trolley pushes. Push force rose with speed. ISO 11228-2 limits come from slow-walk studies, but real workers push faster. — [UNIBO repository](https://cris.unibo.it/handle/11585/735248)
- Lee et al. 1991: in carts pushed or pulled at 1.8 and 3.6 km/h, pushing gave lower low-back loading than pulling. — [UMich Deep Blue](https://deepblue.lib.umich.edu/bitstream/2027.42/29390/1/0000461.pdf)

### Cited Findings — scanners
- UPS adopted ring scanners from 2003 (Symbol CRS-1). The 2012 rollout used the Motorola RS507 ring imager, worn on two fingers of either hand, triggerless, with Bluetooth to a wrist- or hip-worn terminal. UPS says loading got 29% faster. — [MH&L](https://www.mhlnews.com/archive/ups-marries-workers-ring-scanners-improve-loading); [Vision Systems](https://www.vision-systems.com/factory/article/16746723/ring-scanners-improve-operational-efficiency-at-ups)
- The Zebra RS4000 is a current 1D ring scanner paired with the WT6000 wrist computer. — [Zebra spec sheet](https://www.zebra.com/content/dam/zebra_dam/en/spec-sheets/rs4000-specification-sheet-en-us.pdf)

### Inferences
- Animation timing targets derived from the figures above:
  - Inductor: 1 parcel every 2–6 s. Use about 3–4 s as a realistic Malaysian-hub mid-value, a judgement between the 600–700/h field average and the 1,500–2,000/h ceiling. Add occasional idle gaps and occasional bursts of 2–3 parcels at once, since those are observed real behaviours.
  - Trailer unloader: 1 parcel every 3–6 s (600–1,200 pph), with a lift from the stack, a short turn or step, and a place on the telescopic conveyor tip.
  - Roll-cage push: walking pace (about 1.0–1.3 m/s is typical human walking; the HSE says "no faster than walking speed"; Lee et al. tested 0.5 and 1.0 m/s). Two hands on the frame at about 1.0 m height, forward lean, pushing not pulling.
- Inductor posture: standing at the induction belt, taking a parcel from a feed conveyor or tote, rotating it label up and placing it flat. With a cross-belt timing window, the motion is a short reach, an orientation adjustment and a forward place, mostly two-handed for anything bigger than a small polybag.
- The scanner choice for realism is a ring scanner on the index and middle fingers with a wrist unit. It needs no separate held object, which suits CCTV distance, where it is invisible anyway.

### Gaps
- I found no BEUMER, Vanderlande, Fives, Honeywell Intelligrated or Interroll published rate for a manual induction station operator, and no time-and-motion study giving seconds per parcel for cross-belt or tilt-tray induction.
- I found no source on PosLaju, DHL Malaysia or Royal Mail inductor rates; a Chinese-language search returned nothing citable.
- I found no source describing how bags are physically hung on chute frames in Asian hubs (hooks, rings, clamp frames), how full bags are tied (cable tie, drawstring, seal tag) or their typical full weight. Only the generic "tie the bags" description was found.
- I did not retrieve the numeric push forces or speeds from Botti et al. 2020; only the abstract was accessible.
- I found no measured roll-cage walking speed in parcel hubs. The 1.0–1.3 m/s range above is general walking knowledge, not sourced here.
