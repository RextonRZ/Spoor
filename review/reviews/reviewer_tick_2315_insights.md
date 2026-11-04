last commit reviewed: (insights)

OWNER (Rexton): add a "Hub insights" tab that shows the FEEDBACK LOOP (cases -> confirmed outcomes -> where the hub
loses parcels -> what to fix -> fewer cases). Build it only from real data already in the store; never invent
numbers; label it "Demo hub data". Time box 3 h, after the Answer/Proof split (tick 2230). Four skills, brand style.
Sections (each number links to its source):
1. Loop at a glance: Customer asked / stalled scans -> cases opened -> Spoor answered -> staff confirmed (Go look
   "Found here") -> closed. Show the real counts (e.g. 1 case, answered, confirmed once the demo marks it found).
   "Spoor's answer confirmed by staff: X of Y" fills in when a Go look outcome is recorded.
2. Where parcels go missing: from answered cases + the exceptions inbox: places and checkpoints where the trail breaks
   (e.g. "Exception store: carried in, not scanned in · 1 case"), with the suggested fix in plain words ("scan-in at
   the store door was skipped"). Rank by count.
3. Records the cameras disagreed with: e.g. "RFID D07 marked a cage loaded while its parcel was in the store · 1".
4. Coverage and health (the system checking itself): scan points no camera sees (visible_by), checkpoint cameras
   with a fitted clock vs not, outline check results per camera (labels shown / right), Glimmer footage skipped.
5. What it cost and saved: time to answer vs hours of footage a person would scroll, cost per case (real ledger).
When the Go look screen marks the parcel found in the Exception store, the insights update live (that is the loop
to show in the video). Empty states must be honest ("No confirmed outcomes yet"). README: one paragraph on the loop;
"with real hub data this ranks the places that lose parcels most".

OWNER ADD: an AGENT feedback loop (the agents use outcomes, not only the dashboard). Two honest loops, no training,
no answer-key data, everything from staff-confirmed outcomes:
A. In-case loop (demo this one): on Go look, if staff tap "Not found here", that place is ruled out as evidence
   ("searched by staff, not found, <time>"), the case goes back to Investigating, and Muse Wonder re-plans the next
   most likely place from the remaining possible locations (the screen shows "Re-planned after the search"). If staff
   tap "Found here", the case closes as confirmed. Show both paths work; the video shows "Found here".
B. Hub memory across cases: each confirmed outcome is stored as a short memory ("parcel taken out of a cage with no
   scan -> found in the Exception store, confirmed by staff"). The lead investigator gets the confirmed memories as
   context and must cite one when it uses it ("Past confirmed case: ... so check the store door first"). Memory never
   counts as evidence for the current case; the verifier still needs this case's own frames. Show "Hub memory: N
   confirmed outcomes" on Investigating; with N = 0 it says so plainly.
Insights tab shows both: answers confirmed by staff, re-plans after "not found", memories used.

OWNER ADD: design the Hub insights tab with the design sense of Reelism's ANALYTICS screens (Rexton's own product,
C:\Users\ooiru\Reelism\, READ-ONLY, never edit it). Find its analytics/dashboard pages and components; take their
layout rhythm, chart style (axes, gridlines, labels, tooltips, number formatting), KPI treatment, spacing, type
scale and motion. Keep Spoor's own palette (cool near-black, rare indigo, evidence colours only for meaning), per
owner_style_0136 (Reelism finish, not its colours). Note in the log which Reelism screens/components you used as
reference. Charts only where there are real numbers; small honest counts read better as text than as a big chart.
