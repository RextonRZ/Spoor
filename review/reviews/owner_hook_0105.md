# OWNER 01:05 Sat (Rexton: "avoid missing the reviews") — install the review-watch hook

So you can never again miss a reviewer file (like 14:24–15:59 yesterday), install `review/tools/review_watch.py`
as Claude Code hooks for this project:
1. Create `.claude/settings.json` in the Spoor root (project hooks), e.g.
   {"hooks": {
     "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/review/tools/review_watch.py\""}]}],
     "Stop":        [{"hooks": [{"type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/review/tools/review_watch.py\""}]}]
   }}
   Adjust the command to whatever works in your shell on this Windows machine (python / py, quoting); keep it quiet when
   nothing is new.
2. Test: run it once by hand (creates the baseline), touch a test review file, run again → it must print the JSON;
   then delete the test file.
3. Tell Rexton in FOR_REXTON.md that he must approve the hook once (Claude Code asks to review hook changes in `/hooks`,
   or a session restart picks it up) — you cannot activate it silently.
4. Do not add anything else to the hooks; never let a hook block more than once per new file.
What it does: after every tool call, if a reviewer file is new or changed, it puts "NEW REVIEWER FILES: … read them now"
into your context; if you try to stop with unread reviewer files, it stops you once and tells you which.
