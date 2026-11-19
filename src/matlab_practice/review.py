"""Claude review and hints, through Claude Code's non-interactive mode (`claude -p`).

Uses whatever account Claude Code is signed into (a Claude subscription), so no API key is needed.
Claude runs with no tools, in an empty temporary folder, and only sees what this module sends it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config
from .problems import Problem

TIMEOUT_S = 180

SCHEMA = {
    "type": "object",
    "properties": {
        "matlab_ok": {"type": "boolean"},
        "gaming": {"type": "boolean"},
        "rules_ok": {"type": "boolean"},
        "summary": {"type": "string"},
        "notes": {"type": "array", "items": {"type": "string"}},
        "hint": {"type": "string"},
    },
    "required": ["matlab_ok", "gaming", "rules_ok", "summary", "notes"],
}


def hint_level(fails_after: int) -> int:
    """0 = no hint yet; 1 at the 5th failure, 2 at the 6th-7th, 3 from the 8th."""
    t = config.HINT_THRESHOLD
    if fails_after < t:
        return 0
    if fails_after == t:
        return 1
    if fails_after <= t + 2:
        return 2
    return 3


def find_claude() -> list[str] | None:
    """The command to run Claude Code, or None. CLAUDE in .env may point at an executable or a .py file."""
    configured = config.setting("CLAUDE")
    candidates = [configured] if configured else []
    which = shutil.which("claude")
    if which:
        candidates.append(which)
    home = Path.home()
    candidates += [str(home / ".local" / "bin" / ("claude.exe" if sys.platform == "win32" else "claude")),
                   str(home / ".claude" / "local" / "claude")]
    for c in candidates:
        if c and os.path.isfile(c):
            return [sys.executable, c] if c.endswith(".py") else [c]
    return None


def _system_prompt(level: int, fails: int, earlier: list[str]) -> str:
    text = (config.PROMPTS_DIR / "review.md").read_text(encoding="utf-8")
    if level:
        hint = (config.PROMPTS_DIR / "hint.md").read_text(encoding="utf-8")
        hint = hint.replace("{fails}", str(fails)).replace("{level}", str(level))
        if earlier:
            hint += "\n\nEarlier hints:\n" + "\n".join(f"- {h}" for h in earlier)
        else:
            hint += "\n\nEarlier hints: none."
        text += "\n\n" + hint
    else:
        text += '\n\nDo not give a hint: leave the "hint" field out or empty.'
    text += "\n\nReply only through the structured output."
    return text


def _user_message(problem: Problem, sub: dict, context: list[Problem]) -> str:
    parts = [f"# Problem ({problem.kind} problem, id {problem.id})", problem.statement.strip()]
    for c in context:
        parts += [f"## Earlier problem it refers to ({c.id})", c.statement.strip()]
    parts += ["# How to submit", problem.submit_text.strip()]
    rules = []
    if problem.banned_functions:
        rules.append("Banned functions: " + ", ".join(problem.banned_functions))
    if problem.banned_operators:
        rules.append("Banned operators: " + ", ".join(problem.banned_operators))
    if rules:
        parts += ["# App rules for this problem", "\n".join(rules)]
    parts += [f"# Student's file {problem.file}", "```matlab\n" + sub.get("code", "") + "\n```"]
    parts.append(f"# Test results: {sub.get('tests_verdict')} ({sub.get('passed', 0)}/{sub.get('total', 0)} passed)")
    if sub.get("issues"):
        parts.append("Blocked by the checker before running:\n" +
                     "\n".join(f"- line {i['line']}: {i['message']}" for i in sub["issues"]))
    if sub.get("error"):
        parts.append("Error: " + sub["error"])
    for c in sub.get("cases", []):
        if c.get("status") == "passed":
            continue
        line = f"- {c.get('status')}: {c.get('name')}: {c.get('message')}"
        if c.get("hidden"):
            line += " (expected value is HIDDEN from the student: never reveal it)"
        else:
            if c.get("input"):
                line += f" | input {c['input']}"
            if c.get("expected"):
                line += f" | expected {c['expected']} | got {c.get('actual')}"
        parts.append(line)
    return "\n\n".join(parts)


def _parse(stdout: str) -> tuple[dict | None, str]:
    try:
        obj = json.loads(stdout)
    except json.JSONDecodeError:
        return None, "Claude Code returned something unexpected."
    if isinstance(obj, list):  # some versions print a list of events
        obj = next((o for o in reversed(obj) if isinstance(o, dict) and o.get("type") == "result"), {})
    if obj.get("is_error"):
        return None, str(obj.get("result") or "Claude Code reported an error.")
    data = obj.get("structured_output")
    if not isinstance(data, dict):
        text = str(obj.get("result") or "").strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None, "Claude's answer wasn't in the expected format."
    if not all(k in data for k in ("matlab_ok", "gaming", "rules_ok")):
        return None, "Claude's answer was missing fields."
    return data, ""


def review(problem: Problem, sub: dict, fails_if_failed: int, earlier_hints: list[str],
           context: list[Problem]) -> dict:
    """Return {"status", "matlab_ok", "gaming", "rules_ok", "summary", "notes", "hint_text", "reason"}."""
    cmd = find_claude()
    if cmd is None:
        return {"status": "unavailable", "reason": "Claude Code isn't installed or wasn't found."}
    level = hint_level(fails_if_failed)
    args = cmd + ["-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
                  "--strict-mcp-config", "--json-schema", json.dumps(SCHEMA),
                  "--system-prompt", _system_prompt(level, fails_if_failed, earlier_hints)]
    model = config.setting("CLAUDE_MODEL")
    if model:
        args += ["--model", model]
    workdir = tempfile.mkdtemp(prefix="mp-claude-")
    try:
        proc = subprocess.run(args, input=_user_message(problem, sub, context), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S, cwd=workdir,
                              **({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}))
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "reason": "Claude took too long to answer."}
    except OSError as e:
        return {"status": "unavailable", "reason": f"Couldn't start Claude Code ({e})."}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    data, reason = _parse(proc.stdout)
    if data is None:
        if not reason or reason.startswith("Claude Code returned"):
            reason = (proc.stderr.strip().splitlines() or [reason])[-1][:300]
        return {"status": "unavailable", "reason": reason}
    notes = [str(n) for n in (data.get("notes") or [])][:3]
    return {
        "status": "done", "matlab_ok": bool(data["matlab_ok"]), "gaming": bool(data["gaming"]),
        "rules_ok": bool(data["rules_ok"]), "summary": str(data.get("summary") or ""), "notes": notes,
        "hint_text": str(data.get("hint") or "").replace('\\"', '"').strip() if level else "", "level": level,
    }
