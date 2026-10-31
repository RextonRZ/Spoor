"""Claude Code hook: make the builder notice new reviewer files immediately (Rexton, 31 Oct 01:03).

Wire as PostToolUse (matcher "*") and Stop hooks. Reads the hook JSON on stdin, compares review/reviews/*.md
(and the QUEUE.md banner) with review/.builder_seen.json, and:
- PostToolUse: injects "NEW REVIEW FILES …" as additionalContext, then marks them seen;
- Stop: blocks the stop once with the list, then marks them seen (no loop: stop_hook_active is respected).
Stdlib only, quiet when nothing is new.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REV = ROOT / "review"
SEEN = REV / ".builder_seen.json"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    event = data.get("hook_event_name", "PostToolUse")
    # Project hooks run in every agent's session (builder AND frontend): keep "seen" per session, or one agent reading
    # a review would hide it from the other. Sessions without an id keep the original file.
    global SEEN
    sid = "".join(c for c in str(data.get("session_id", "")) if c.isalnum() or c == "-")[:64]
    if sid:
        SEEN = REV / f".seen_{sid}.json"
    try:
        seen = json.loads(SEEN.read_text(encoding="utf-8"))
    except Exception:
        seen = {}
    files = sorted((REV / "reviews").glob("*.md")) + [REV / "QUEUE.md"]
    new = []
    for f in files:
        if not f.exists():
            continue
        key, m = f.name, f.stat().st_mtime
        if seen.get(key, 0) < m:
            new.append(f.relative_to(ROOT).as_posix())
            seen[key] = m
    if not new:
        return
    if not SEEN.exists():  # first run: baseline only, do not flood the context with old files
        SEEN.write_text(json.dumps(seen), encoding="utf-8")
        return
    SEEN.write_text(json.dumps(seen), encoding="utf-8")
    msg = ("NEW/UPDATED REVIEWER FILES: " + ", ".join(new) +
           ". Read them now (P0 first, owner orders override your plan) before continuing; log an ACK in review/log.md.")
    if event == "Stop":
        if data.get("stop_hook_active"):
            return
        print(json.dumps({"decision": "block", "reason": msg}))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


if __name__ == "__main__":
    main()
