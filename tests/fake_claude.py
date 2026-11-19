"""Stand-in for `claude -p` in tests. Behaves like the real CLI's JSON output.

- Code containing FAKE_GAMING        -> gaming: true
- Code containing FAKE_OCTAVEISM     -> matlab_ok: false
- Code containing FAKE_SLOW          -> sleeps 3 s
- System prompt asking for a hint    -> includes a hint naming the level
- Env FAKE_CLAUDE_FAIL=auth          -> is_error result (like an expired sign-in)
"""
import json
import os
import re
import sys
import time

args = sys.argv[1:]
system = args[args.index("--system-prompt") + 1] if "--system-prompt" in args else ""
user = sys.stdin.read()
if os.environ.get("FAKE_CLAUDE_FAIL") == "auth":
    print(json.dumps({"type": "result", "is_error": True,
                      "result": "Failed to authenticate: OAuth session expired and could not be refreshed"}))
    sys.exit(1)
if "FAKE_SLOW" in user:
    time.sleep(3)
level = re.search(r"This is hint level (\d) of 3", system)
data = {
    "matlab_ok": "FAKE_OCTAVEISM" not in user,
    "gaming": "FAKE_GAMING" in user,
    "rules_ok": True,
    "summary": ("This hard-codes the answers." if "FAKE_GAMING" in user
                else "Looks good." if "# Test results: accepted" in user
                else "Valid MATLAB. Keep working on the failing cases."),
    "notes": [],
}
if level:
    data["hint"] = f"Hint level {level.group(1)}: think about the first and last data points."
if "Reply with just the word OK" in user:
    print(json.dumps({"type": "result", "is_error": False, "result": "OK"}))
else:
    print(json.dumps({"type": "result", "is_error": False, "result": "", "structured_output": data}))
