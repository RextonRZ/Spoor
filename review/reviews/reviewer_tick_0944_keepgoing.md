last commit reviewed: f55fa59

IMPORTANT (Rexton is out until ~19:00 with no laptop; nobody can type "continue" for you today):
- Do NOT end your turn / stop to wait while a background job (Modal render, Blender bake, SAM run, test run) is
  running. Wait for it inside your turn (poll its log or status every 1-2 min with a sleep loop) and continue.
- When a step is done, start the next one from day_plan_mon_0215.md immediately. Only end your turn when the whole
  day plan is done or a stop condition is hit (spend > cap, keyed answer changes, tests failing and unfixable).
- If you must stop, write the reason at the top of review/READY.md first, so the reviewer can tell Rexton.
