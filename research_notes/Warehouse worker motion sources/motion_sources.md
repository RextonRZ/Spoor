# Warehouse / parcel-handling motion sources (free or permissive) for the Spoor synthetic CCTV dataset (Blender 5.2)

Project licence rule applied strictly: ALLOWED = CC0, CC BY, MIT, and Mixamo (under Adobe's own terms). NOT ALLOWED without explicit owner approval = NC, ND, research-only, custom or unclear licences, and AI-generated assets.
Research date: 2026-10-30. "Verified" means I read it on the primary page or file during this session. "Unverified" means it came from a secondary source or was not checked.

## Q1. Mixamo: exact animation names for box/parcel handling, carrying, pushing and related actions

### Takeaway
Mixamo has a small but usable set of box/parcel clips: Box Idle, Box Turn (left and right variants), Box Walk Arc, Jogging With Box, Picking Up, Putting Down, Lifting, Lifting Object, Push / Push Start / Push Stop / Pushing, Holding Idle/Walk/Turn, and Wheelbarrow clips. There is no "push cart" or "roll cage" clip, no straight-line "walk carrying box" clip, and no barcode-scanner clip. **Major licence flag:** a widely cited 2022 Adobe community FAQ says "The only research application Mixamo content can't be used in is training machine-learning models." That directly affects an ML training dataset and needs an owner decision.

### Cited Findings
**Where the names come from.** The names below come from `metadata.csv` in the Hugging Face mirror [Linzhan/Mixamo-Animations-Characters](https://huggingface.co/datasets/Linzhan/Mixamo-Animations-Characters). It indexes 2,446 Mixamo clips, each with its catalogue name (`prompt`), the Mixamo long description and the Mixamo `motion_id`. The page says the clips were "exported from Mixamo through its own export API" and are "subject to Adobe's Mixamo terms". Download the clips from mixamo.com itself, not from this mirror, which says it is for research use. I downloaded and searched the CSV myself. Where several clips share a catalogue name, the `_2`/`_3` suffix comes from the mirror, not from Mixamo, so use the long description to pick the right one in the Mixamo search.

Format below: Mixamo catalogue name — Mixamo description — frame count (at 30 fps) — motion_id.

**Box / parcel handling**
- **Box Idle** — "Carrying A Box" — 190 f — c9cd8d90-b96c-11e4-a802-0aaa78deedf9
- **Box Turn** — "Turning Right Carrying A Box" — 36 f — c9cd8fe5-b96c-11e4-a802-0aaa78deedf9
- **Box Turn** — "Turning Left Carrying A Box" — 47 f — c9cd8f1a-b96c-11e4-a802-0aaa78deedf9
- **Box Walk Arc** — "Walking In A Left Arc Carrying A Box" — 38 f — c9cd8e51-b96c-11e4-a802-0aaa78deedf9
- **Jogging With Box** — "Jogging While Carrying A Box" — 24 f — c9c72ec7-b96c-11e4-a802-0aaa78deedf9
- **Picking Up** — "Picking Up An Object" — 288 f — c9c6d7aa-b96c-11e4-a802-0aaa78deedf9
- **Putting Down** — "Putting Down An Object" — 311 f — c9c6d86d-b96c-11e4-a802-0aaa78deedf9
- **Lifting Object** — "Lifting A Heavy Object With Both Hands" — 346 f — c9c8fb6e-b96c-11e4-a802-0aaa78deedf9. Best candidate for a heavy sack or box lifted from the floor.
- **Lifting** — "Pick Up Object And Examine" — 217 f — c9c6fe3b-b96c-11e4-a802-0aaa78deedf9. Could serve for picking up and inspecting a label.
- **Picking Up Object** — "Picking Up An Object With One Hand" — 104 f — c9c6c5eb-b96c-11e4-a802-0aaa78deedf9
- **Gathering Objects** — "Squatting Down To Gather Objects"
- **Taking Item** — "Taking An Item And Examining It"
- **Rummaging** — "Reaching To Rummage Through Items"
- **Throw Object** — "Picking Up Object And Throwing" — 217 f. Parcel-toss behaviour.
- **Dropping** — "Dropping Something And Picking It Up" — 149 f
- **Closing A Lid** / **Opening A Lid** — "Closing/Opening The Lid On A Chest Or Box"
- **Holding Idle** / **Holding Walk** / **Holding Turn Left** / **Holding Turn Right** — "Holding An Object Idle / While Walking / While Turning Left / While Turning Right". This is the only straight-line walk-while-holding set found. Whether the object is held two-handed is unverified; preview it on Mixamo.

**Pushing / pulling (closest to a cart or trolley)**
- **Push** — "Pushing Heavy Object" (52 f, c9c74449-…) and a second clip, also "Pushing Heavy Object" (241 f, c9c72e08-…)
- **Push Start** — "Start To Push A Heavy Object" — 143 f
- **Push Stop** — "Stop Pushing A Heavy Object" — 79 f
- **Pushing** — "Pushing An Object Forward" (120 f) and "Pushing A Heavy Object" (81 f)
- **Pull Heavy Object** / **Pull Heavy Object Start** / **Pull Heavy Object Stop** — pulling a heavy object
- **Wheelbarrow Idle** ("Holding A Full Wheelbarrow Idle"), **Wheelbarrow Walk** ("Walking With An Empty Wheelbarrow" / "Walking With A Full Wheelbarrow"), **Wheelbarrow Walk Turn** (full and empty variants), **Wheelbarrow Dump**. Hands at waist height, gripping and walking: usable as a stand-in for pulling a pallet jack or hand truck.
- **Shopping Cart Dance** — "Shopping Cart Silly Dance". A comedy clip, not usable.
- I found no clip named "Push Cart", "Pushing Cart" or "Trolley" in the 2,446-clip index.

**Scanner / handheld device stand-ins.** No barcode-scanner clip exists.
- **Texting While Standing** — "Texting On A Smart Phone While Standing"
- **Texting** — "Standing Texting On Phone"
- **Walking While Texting** / **Texting And Walking**
- **Standing Using Touchscreen Tablet** — "Female Using Touchscreen Tablet"
- **Using A Fax Machine** — "Female Standing While Using A Fax Machine On A Table". Standing work at table height.
- **Kneeling Inspecting** — "Kneeling And Inspecting Element With Hands"
- **Standing Torch Inspect Downward/Forward/Upward**. One-hand-held object pointed at a target. A possible scanner-aim stand-in, but it is a fantasy "torch" set.

**Other useful clips**
- Crouch To Stand / Stand To Crouch / Kneeling Down / Standing (from kneeling), Looking, Talking On A Cell Phone.
- **Walk With Briefcase** / **Standing W/Briefcase Idle** / **Walking With Shopping Bag** — one-hand carry of a small parcel or bag.

**Licence: Adobe help page** (verbatim, "Last updated on Sep 14, 2021"): "Mixamo is available free for anyone with an Adobe ID and does not require a subscription to Creative Cloud." … "You can use both characters and animations royalty free for personal, commercial, and non-profit projects including: Incorporate characters into illustrations and graphic art. 3D print characters. Create films. Create video games." — [Adobe Mixamo FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)

**Licence: Adobe community FAQ** (verbatim, posted by "TylerG 3D", Sep 29, 2022):
- "really the only thing you can't do is distribute the raw character and animation files."
- Under "NO, you cannot create": "Any type of free distribution of character or animation raw files".
- "Can I use Fuse and Mixamo for non-profit, commercial, research, or school projects? Yes to all. … The only research application Mixamo content can't be used in is training machine-learning models."
- "you … are not required to give credit to Adobe, Mixamo, or Fuse in any way."

Source: [Adobe Community – Mixamo FAQ Licensing](https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/td-p/13234775). In replies dated Aug–Oct 2026, users ask whether the post is still current. One community expert only points back to the helpx FAQ. No Adobe staff answer was seen.

### Inferences
- **Coverage by action:**
  - Pick-up box: Picking Up, Lifting Object
  - Put-down: Putting Down
  - Two-handed carry while walking: Holding Walk and Box Walk Arc. There is no straight-line "Box Walk". Box Idle and Box Turn give the upper-body pose, which could be layered over a normal walk using Blender NLA with an upper-body mask.
  - Carry-turn: Box Turn ×2, Holding Turn Left/Right
  - Heavy lift from the floor: Lifting Object
  - Push cart/trolley: Push / Push Start / Push Stop / Pushing are "heavy object" pushes, likely with a forward lean and hands at chest height. Wheelbarrow Walk has hands at waist height. A roll-cage push probably needs one of these plus hand-IK retargeting to the handle.
  - Scanner: Texting While Standing as a proxy
  - Sack tying: nothing suitable
  - Unloading from a stack or truck: chain Picking Up → Holding Walk → Putting Down
- **ML-training flag.** Spoor's renders feed ML. The community FAQ's "can't be used in … training machine-learning models" line is not in the current helpx page, but it is also not withdrawn anywhere I could see. The project rule accepts Mixamo "under Adobe's own terms", and those terms may exclude ML training. **The owner must decide this explicitly.** It is the single biggest licence risk in this catalogue.
- In-place vs root motion: Mixamo shows an "In Place" checkbox in its download/preview panel for clips that travel (e.g. Box Walk Arc, Holding Walk, Push, Wheelbarrow Walk). Stationary clips (Picking Up, Putting Down, Lifting Object, Box Idle) do not travel. This is from general knowledge of the Mixamo UI and was not verified on the site this session.

### Gaps
- I could not open mixamo.com search results (login required), so the exact UI titles and the In Place option per clip are unverified. Clip names come from the HF mirror's index of Mixamo's own catalogue.
- Whether "Holding Walk" is two-handed, and the hand height in the Push clips, need a visual check on Mixamo.
- I found no current official Adobe statement on ML training. The current Adobe General Terms (adobe.com/legal/terms.html) were not read in this session.

## Q2. CMU Graphics Lab Motion Capture Database: box/object-manipulation trials and licence

### Takeaway
CMU has the most relevant real mocap for this task: Subject 115 (10 box pick-up trials), Subject 69 trials 68–75 (walk, pick up, carry and set down an object), 143_10–13 (walk and pick up a box or toolbox), 79_25 "moving heavy box", and the 81/82 heavy-object pushes. Its licence is a custom permissive statement, not CC0/CC BY/MIT, so under the strict rule it **needs explicit owner approval**. On substance it permits commercial products and modification, and does not forbid ML use.

### Cited Findings
**Licence, verbatim from the CMU home page:** "This dataset of motions is free for all uses." … "This data is free for use in research projects. You may include this data in commercially-sold products, but you may not resell this data directly, even in converted form. If you publish results obtained using this data, we would appreciate it if you would send the citation to your published paper to jkh+mocap@cs.cmu.edu, and also would add this text to your acknowledgments section: The data used in this project was obtained from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217." — [mocap.cs.cmu.edu](http://mocap.cs.cmu.edu/)

**Licence, verbatim from the CMU FAQ:** "How can I use this data? The motion capture data may be copied, modified, or redistributed without permission." Also: "Disclaimer 1: We do not guarantee the quality of the data." — [CMU FAQs](http://mocap.cs.cmu.edu/faqs.php)

**Data notes from CMU:**
- The "toe" and "hand" joints "tend to be noisy, and may require some smoothing".
- Finger and thumb joints "are added to the skeleton for editing convenience — we do not actually capture these joints' motions".
- The full ASF/AMC set is downloadable as allasfamc.zip. The FAQ asks users not to crawl the site.

Source: [mocap.cs.cmu.edu](http://mocap.cs.cmu.edu/)

**Relevant trials (subject_trial — description — fps).** All come from CMU keyword searches for box, carry, pick, lift and push. Sources: [search "box"](http://mocap.cs.cmu.edu/search.php?subjectnumber=%25&motion=box), ["pick"](http://mocap.cs.cmu.edu/search.php?subjectnumber=%25&motion=pick), ["carry"](http://mocap.cs.cmu.edu/search.php?subjectnumber=%25&motion=carry), ["push"](http://mocap.cs.cmu.edu/search.php?subjectnumber=%25&motion=push), ["lift"](http://mocap.cs.cmu.edu/search.php?subjectnumber=%25&motion=lift).

- **Subject 115 ("Bending over")** — 115_01 "Pick up box, bend from waist"; 115_02–05 and 115_10 "Pick box up, bend from waist"; 115_06–09 "Picking box up, bending knees" — 120 fps. Gives both a stoop lift and a squat lift.
- **Subject 69 ("walking")**, 120 fps:
  - 69_68 "walk forward and pick up object, set down object"
  - 69_69 "walk forward and pick up object, carry back object"
  - 69_70, 69_71, 69_75 "walk up to object, squat, pick up object, set down in another place"
  - 69_72 "walk up to object, pick up object, set down in another place"
  - 69_73, 69_74 "walk up to object, lean over, pick up object, set down in another place"
  - These cover the full pick → carry → place cycle in one clip.
- **Subject 143 ("General Subject Capture")**, 120 fps:
  - 143_10 "Walk And Pick up Tool Box"
  - 143_11 "Walk And Pick up Box"
  - 143_12 "Walk And Pick up Toolbox"
  - 143_13 "Walk and Pick up Laundry Basket". A two-handed carry of a bulky object.
  - Also 143_28 "Sweeping, Push Broom".
- **Subject 79 ("actor everyday activities")** — 79_25 "moving heavy box" — 60 fps.
- **Subject 62 ("construction work, random motions")** — 62_18 "closing a box", 62_19 "opening a box", 62_20 "closing, moving and opening a box" — 60 fps.
- **Subject 81 ("pushing a box; jumping off a ledge; walks")** — 81_05 "push heavy object", 81_06 "push heavy box", 81_10 and 81_11 "push object that is high in air" — 120 fps.
- **Subject 82 ("jumping; pushing; emotional walks")** — 82_06 and 82_07 "Pushing on heavy object" — 120 fps.
- **Subject 70 ("suitcase")** — 70_01–02 "carry 5.5lb suitcase", 70_03–09 "carry 19.5lb suitcase", 70_10–13 "carry 12.5lb suitcase" — 120 fps. One-hand heavy carry with a weight-dependent lean.
- **Subjects 111 and 113** (pregnant / post-pregnant woman) — 111_36 and 113_26 "Walk and carry"; 111_17 and 111_18 "Pick up" — 120 fps.
- **Others:**
  - 26_09 "bend, pick up"
  - 26_10 and 26_11 "bend, lift"
  - 02_06 "bend over, scoop up, rise, lift arm"
  - 80_08 "picking up something"
  - 74_07 and 74_08 "lifting up" (60 fps)
  - 137_27 "Normal Pick Up"
  - 137_40 "Strong Man Pick Up". Subject 137 is a set of stylized motions; avoid the other 137 styles.
- No CMU trial matched "cart" (only cartwheels) or "load". "Put" matched nothing relevant.

**BVH conversions:** CMU's home page points to "Bruce Hahn ... 3D Studio Max and MotionBuilder bvh's, hosted at cgspeed" — [mocap.cs.cmu.edu](http://mocap.cs.cmu.edu/). A search-result copy of the cgspeed README (July 2008) quotes: "CMU places no restrictions on the use of the original dataset, and I (Bruce) place no additional restrictions on the use of this particular BVH conversion." — via [cmubvh GitHub](https://github.com/Shriinivas/cmubvh) and [amc2bvh](https://github.com/thcopeland/amc2bvh). Not read on the cgspeed page itself (unverified). Truebones claims the cgspeed conversion lacked hand data and sells a "corrected" version ([truebones.gumroad.com/l/CPaSkd](https://truebones.gumroad.com/l/CPaSkd)). That is a vendor claim.

### Inferences
- CMU covers almost every target action except the cart/roll cage, the scanner and sack tying. Subject 69 and Subject 143 are the best for realistic, unstylized pick-carry-place cycles. Subject 115 is ideal for lifting heavy boxes or sacks from the floor.
- **Licence classification under the strict rule:** CMU's terms are permissive but custom. They say "free for all uses", "copied, modified, or redistributed without permission", and allow inclusion in commercial products, but forbid resale of the data. They match none of CC0/CC BY/MIT word for word, so **owner approval is required**. Approval risk looks low: the terms say nothing against ML, and rendering frames is not reselling the data.
- Converting AMC to BVH yourself (e.g. with amc2bvh), or using Blender's AMC/ASF import add-ons, avoids depending on the cgspeed or Truebones redistribution terms.

### Gaps
- I did not visually check trial quality. CMU warns that lower-numbered subjects are lower quality.
- The current cgspeed page text was not read (site not fetched).

## Q3. Quaternius Universal Animation Library (CC0) and Quaternius packs

### Takeaway
UAL is verified CC0 and usable, but its free Standard set has only two parcel-relevant clips, `PickUp_Table` and `Push_Loop`, plus generic `Interact`, `Fixing_Kneeling`, idle and walk clips. There is no box carry in the Standard set. The paid Pro/Source tiers (120+ clips, still CC0) and UAL2 (130+, CC0) may contain more, but their clip lists are unverified.

### Cited Findings
- **Licence:** "Free to use in personal, educational and commercial projects. (CC0 License)". The itch.io "Asset license" field reads "Creative Commons Zero v1.0 Universal". The page is tagged "No generative AI was used". Source: [quaternius.itch.io/universal-animation-library](https://quaternius.itch.io/universal-animation-library)
- **Tiers and features:** "120+ Animations" covering "Locomotion in 8 directions, jog, sprint, push, crawling, swimming, sitting, death animations and more". Now "including two versions, one with full Root Motion and one with Root Motion disabled". "Compatible with other common rigs (Mixamo for example)". The Standard image caption says "STANDARD FREE 45 completely free animations … CC0". Source: [itch.io UAL](https://quaternius.itch.io/universal-animation-library); [quaternius.com UAL page](https://quaternius.com/packs/universalanimationlibrary.html) also states CC0.
- **Standard clip names:** I read these from the AnimStack names in `ual.fbx`, which ozz-animation redistributes in [guillaumeblanc/ozz-animation media/fbx/quaternius](https://github.com/guillaumeblanc/ozz-animation/tree/master/media/fbx/quaternius). Its README says the data came from the Quaternius UAL "released under CC0 licence". The 46 stacks are:
  - A_TPose, Crouch_Fwd_Loop, Crouch_Idle_Loop, Dance_Loop, Death01, Driving_Loop, **Fixing_Kneeling**, Hit_Chest, Hit_Head
  - Idle_Loop, Idle_Talking_Loop, Idle_Torch_Loop, **Interact**, Jog_Fwd_Loop, Jump_Land, Jump_Loop, Jump_Start
  - **PickUp_Table**, Pistol_Aim_Down, Pistol_Aim_Neutral, Pistol_Aim_Up, Pistol_Idle_Loop, Pistol_Reload, Pistol_Shoot
  - Punch_Cross, Punch_Enter, Punch_Jab, **Push_Loop**, Roll, Roll_RM
  - Sitting_Enter, Sitting_Exit, Sitting_Idle_Loop, Sitting_Talking_Loop
  - Spell_Simple_Enter, Spell_Simple_Exit, Spell_Simple_Idle_Loop, Spell_Simple_Shoot
  - Sprint_Loop, Swim_Fwd_Loop, Swim_Idle_Loop, Sword_Attack, Sword_Attack_RM, Sword_Idle, **Walk_Formal_Loop**, **Walk_Loop**
- **Naming may have changed.** A Patreon post title says UAL1 got an update "with updated naming scheme", so current download names may differ — [Patreon UAL2 post](https://www.patreon.com/quaternius/posts/universal-2-148950153) (search snippet only).
- **UAL2:** OpenGameArt lists "Universal Animation Library 2" as CC0 — [opengameart.org/content/universal-animation-library-2](https://opengameart.org/content/universal-animation-library-2). Coverage describes melee/armed combos, parkour, farming, fishing and zombie locomotion, with a free Standard of about 70% of the content — [80.lv](https://80.lv/articles/get-this-animation-asset-library-with-over-130-diverse-items) (search snippet).

### Inferences
- `PickUp_Table` reaches to waist height, so it may double as a place-on-conveyor or pick-off-conveyor clip. Verify the direction visually.
- `Push_Loop` is a loop with no start/stop and its hand height is unknown, but it is CC0 and the cleanest-licensed push available.
- `Interact` could act as a generic reach/press stand-in for scanning a parcel.
- UAL's own rig is not the Spoor character rig. It is described as Mixamo-compatible for retargeting.

### Gaps
- Exact clip lists for UAL1 Pro/Source and UAL2 were not verified. The animation viewer (quaternius.com/animviewer.html) is JavaScript-driven and was not read. UAL2's "farming" set might include carrying (e.g. a sack or crate), but this is unverified.

## Q4. Other libraries: Rokoko, Bandai Namco, Truebones, SFU, LaFAN1, AMASS, HumanML3D, ActorCore, Kenney, OpenGameArt, Sketchfab, 100STYLE

### Takeaway
Under the strict rule, almost every large academic dataset is excluded: Bandai Namco (CC BY-NC), LaFAN1 (CC BY-NC-ND), SFU (research only), AMASS and HumanML3D (non-commercial research). Commercial-vendor free packs (Rokoko, Truebones, ActorCore) use custom royalty-free EULAs that need owner approval. OpenGameArt hosts the CC0 Quaternius sets.

### Cited Findings
- **Bandai Namco Research Motiondataset** — README "License": "Bandai-Namco-Research-Motiondataset-1: CC BY-NC 4.0; Bandai-Namco-Research-Motiondataset-2: CC BY-NC 4.0; Motion visualization on Blender: MIT". Content is "daily activities, fighting, and dancing" (dataset 1) and "10 types of content mainly focusing on locomotion and hand actions" (dataset 2). Source: [GitHub README](https://github.com/BandaiNamcoResearchInc/Bandai-Namco-Research-Motiondataset/blob/master/README.md). A secondary source reported CC BY-NC-ND ([automaton-media](https://automaton-media.com/en/news/20220430-12213/) via search snippet). The primary README says CC BY-NC. **NOT usable (NC).**
- **LaFAN1 (Ubisoft)** — "This dataset can be used under the Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International Public License (see license.txt)." Source: [ubisoft-laforge-animation-dataset](https://github.com/ubisoft/ubisoft-laforge-animation-dataset). **NOT usable (NC+ND).**
- **SFU Motion Capture Database** — "This dataset of motions is free for research purposes. The data cannot be used for commercial products or resale, unfortunately." Source: [mocap.cs.sfu.ca](https://mocap.cs.sfu.ca/). **NOT usable (research-only).** No box, carry, lift or push trials appeared on the scraped index page.
- **AMASS** — "Dataset Copyright License for non-commercial scientific research purposes" … "To use the Dataset for the sole purpose of performing non-commercial scientific research, non-commercial education, or non-commercial artistic projects; Any other use, in particular any use for commercial purposes, is prohibited. … The Dataset may not be reproduced, modified and/or made available in any form to any third party without Max-Planck's prior written permission." It also "prohibits the use of the Dataset to train methods/algorithms/neural networks/etc. for commercial use of any kind." Source: [amass.is.tue.mpg.de/license.html](https://amass.is.tue.mpg.de/license.html). **NOT usable.**
- **HumanML3D** — derived from HumanAct12 and AMASS, "both released for academic research only" — [Motion-X paper, arXiv 2307.00818](https://arxiv.org/pdf/2307.00818) (search snippet). It inherits AMASS restrictions. **NOT usable.**
- **Truebones free packs** — a Gumroad terms text quoted in search results: "TRUEBONES products are absolutely royalty free and can be used for any and all purposes even commercial, but Re-Distribution or ReSale of Truebones in .FBX, .BVH or i-Motion formats is strictly prohibited and protected by copyright law." — [truebones.gumroad.com](https://truebones.gumroad.com/l/vlvPq). The body text did not load on direct fetch, so this is unverified. Custom EULA: **needs owner approval.** No specific box clips verified.
- **Rokoko free Motion Library** — Rokoko offered "150 high-quality mocap assets for free", described as "licensed for use in commercial projects" — [CG Channel](https://www.cgchannel.com/?p=113569) (secondary, c. 2020). Current licence text was not read (unverified). Custom EULA: **needs owner approval.**
- **Reallusion ActorCore free motions** — press coverage says the free assets "are licensed for commercial use" — [CG Channel 2022](https://www.cgchannel.com/?p=121885) (secondary). They are governed by the [Reallusion Content EULA](https://www.reallusion.com/Content/EULA/EULA.htm), which was not read in full. A forum post says a motion cannot be resold "even if it is an edited version". Custom EULA: **needs owner approval.** Specific free box/cart clips are unverified.
- **OpenGameArt** — hosts Quaternius UAL and UAL2 as CC0 ([UAL2 on OGA](https://opengameart.org/content/universal-animation-library-2)). Other CC0/CC BY mocap on OGA was not surveyed in detail.
- **100STYLE** — BVH under "Creative Commons Attribution 4.0 International License", but it is locomotion styles, not handling — [100STYLE](https://ianxmason.github.io/100style/) (search snippet). CC BY is usable, but its relevance is likely limited to walking-style variety.

### Inferences
- If the owner wants zero-approval sources only, the realistic set is Mixamo (subject to the ML flag), Quaternius UAL (CC0), AndyData (CC BY 4.0, see Q5) and the industrial benchmark (CC BY 4.0).

### Gaps
- Kenney: not checked this session. Kenney's character packs are CC0, but whether any contain carry or push animations is unverified.
- Sketchfab: per-model licences, mostly CC BY. Not surveyed. Each model must be checked individually for licence and for AI generation.
- I did not verify current (2026) pages for Rokoko, Truebones or ActorCore.

## Q5. CC0 / CC BY mocap of logistics, warehouse or ergonomics work

### Takeaway
The best rule-compliant real mocap of load handling is **AndyData-lab-onePerson** (Zenodo 3254403, CC BY 4.0). It includes Xsens BVH of 13 people doing industrial tasks including "manipulating loads", with per-frame action labels such as reaching, carrying and picking. LARa, the actual warehouse picking/packing dataset, is CC BY-NC 4.0 and therefore not usable. SAFELIFT is CC BY-NC-SA and video-only, so also not usable.

### Cited Findings
- **AndyData-lab-onePerson** — "13 participants performed a series of activities mimicking industrial tasks, such as setting screws at different heights and manipulating loads (15 trials per participant, duration of one trial: between 1.5 and 2 min)". Whole-body kinematics were recorded "both with optical (gold standard) and inertial motion capture systems". "Action taxonomy defines elementary actions such as reaching, carrying, picking." The files include `xsens_bvh.zip`, `xsens_mvn.zip`, `xens_mnvx.zip`, `qualisys_c3d.zip`, `labels_csv.zip` and avatar/camera videos. Licence: **cc-by-4.0** ("Creative Commons Attribution 4.0 International"). Creators: Maurice, Malaisé, Ivaldi, Rochel, Amiot, Paris, Richard, Fritzsche. Paper: "Human Movement and Ergonomics: an Industry-Oriented Dataset for Collaborative Robotics" (IJRR 2019). Sources: [zenodo.org/records/3254403](https://zenodo.org/records/3254403) and the Zenodo API. **USABLE (CC BY; attribution required).**
- **Motion Capture Benchmark of Industrial Tasks for Ergonomic Assessment and European Historic Crafts** (Olivas-Padilla, Manitsaris, Glushkova, Menychtas, MINES ParisTech). BVH files. Includes "TV assembly and packaging … packing TVs for shipping on pallets, in medium (TVP) and large (TVL) sizes", plus 28 lab ergonomic-hazard postures. Licence "Creative Commons Attribution 4.0 International". Source: [zenodo.org/records/5356992](https://zenodo.org/records/5356992). **USABLE (CC BY).** The TVP/TVL pallet packing is the closest to stacking boxes or cartons.
- **LARa Version 03 (TU Dortmund)** — "two picking and one packing scenarios with 16 subjects were recorded using an optical marker-based Motion Capturing system (OMoCap), Inertial Measurement Units (IMUs), and an RGB camera … 960 minutes in total". Files are OMoCap c3d/csv, IMU, RGB video. Licence **cc-by-nc-4.0**. Source: [zenodo.org/records/8189341](https://zenodo.org/records/8189341) (Zenodo API). **NOT usable (NC)** without owner approval. It is the most on-topic warehouse dataset found.
- **SAFELIFT** — videos of "a person lifting a package from the floor to a target surface". Licence "CC BY-NC-SA 4.0". Source: [zenodo.org/records/18243098](https://zenodo.org/records/18243098). **NOT usable** (NC, and video not mocap).

### Inferences
- AndyData's labelled carry and pick segments can be cut directly from the Xsens BVH using `labels_csv`. Its loads are lab objects at varied heights, which is likely a good proxy for placing a parcel on a waist-height conveyor or shelf.
- The CC BY attribution text for AndyData and the industrial benchmark must go into Spoor's dataset credits.

### Gaps
- The exact AndyData task list (load mass, heights, whether the load is a box) is unverified: the HAL paper was blocked by bot protection.
- I found no CC0/CC BY mocap of cart, trolley or roll-cage pushing, barcode scanning, or sack tying in any source. These actions will need Mixamo stand-ins (Push*/Wheelbarrow*/Texting), procedural hand IK, or the owner's own capture.
