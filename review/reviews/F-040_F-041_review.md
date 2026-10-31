# F-040 + F-041 review — APPROVED WITH FIXES (F-040 APPROVED)

Reviewed 07:25 Sat: F-040 request (fixes as asked; the drop lines for 3D pins are a good fix), F-041 request and
40_j3_malaysian_context.png.

F-041 is handled the right way: estimate logged before, the 16× overrun reported plainly, no silent re-run, cost
shown on the button, deterministic cited-sentence check, "not case evidence" label. Spend now ≈ US$1.12 / $60.

## P1 (J3)
1. **No legal text from mirror sites.** Source [1] is an unofficial PDF mirror (`arturio-pdfs.cancode.codes`). A
   report a supervisor may forward must not cite that for statute text. Rule in the deterministic check:
   - statute / section claims must cite an allow-listed official source (`lom.agc.gov.my`, `mcmc.gov.my`,
     `*.gov.my`); otherwise the sentence is dropped and counted ("statute claim without an official source");
   - secondary sources (news, CFM) may support guidance sentences only, tagged secondary as now.
2. **s.31 mismatch.** A cited sentence that misquotes the Act ("or intentional") must not ship in a report. Until the
   re-run replaces it: hide that sentence and count it as "dropped: differs from the Act's text". Never edit the
   retrieved words.
3. **Re-run: APPROVED once**, with a budget guard: if the search-grounding API offers a cap on searches per request
   (check dev.meta.ai docs), set it to ≤ 4 per question; keep max output tokens tight; expected ≤ US$1.50. Log the
   estimate before and the actual after, as you did. If it would clearly exceed US$2, don't run — leave it for Rexton.
   After that, no automatic re-runs; the button stays admin-only with the measured cost.

## P2
4. The answers sit in a narrow ~500 px column inside an 1,100 px panel; let them use ~70 ch width.
5. Add one line under the panel: "General information, not legal advice."
