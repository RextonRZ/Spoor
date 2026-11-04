last commit reviewed: 17450e8

OWNER RULE (Rexton): the demo must not look weak anywhere. The DEMO PATH = Landing -> Hub (live alert + Customer asked
row) -> Investigating (live run) -> Answer -> Proof -> Go look -> Report (customer update) for CTX334048419302.
On that path, for the story parcel only, these must never appear: "Can't tell", "Not seen at the point", "No
footage", "Not checked yet", empty grey tiles, stale text that contradicts the verified answer, internal IDs, UTC
times, placeholders, loading spinners that never resolve, identical thumbnails, a far camera where a close-up exists.
For every place the story parcel shows one of these today, either fix the cause (data, sim, render: as for the unload
door) or redesign the slot so it shows real evidence. The general "can't tell" logic stays for all other parcels.
After the UI pass (reviewer_tick_1147_ui.md), walk the whole demo path at 1440x900 and 390 wide, screenshot every
screen into review/shots/mon/demo_path/, and list in READY.md each item above you found and fixed. The reviewer
will check every screenshot before the video.
