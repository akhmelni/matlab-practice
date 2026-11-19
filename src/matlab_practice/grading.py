"""Run and Submit: checker → Octave → Claude review (+ hints)."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from . import engine, problems, review, store
from .checker import check
from .problems import Problem


def _context_names(problem: Problem) -> list[str]:
    return [Path(name).stem for name in problems.context_files(problem)]


def _issues(problem: Problem, code: str, scratch: str | None) -> list[dict]:
    found = []
    for issue in check(code, filename=problem.file, profile="student", extra_allowed=_context_names(problem),
                       banned_functions=problem.banned_functions, banned_operators=problem.banned_operators):
        if issue.severity == "error":
            found.append({**issue.to_dict(), "file": problem.file})
    if problem.kind == "function" and scratch is not None:
        for issue in check(scratch, filename="scratch.m", profile="student",
                           extra_allowed=[problem.func_name, *_context_names(problem)]):
            if issue.severity == "error":
                found.append({**issue.to_dict(), "file": "scratch.m"})
    return found


def lint(problem: Problem, code: str, filename: str | None = None) -> list[dict]:
    filename = filename or problem.file
    ctx = _context_names(problem)
    if filename == "scratch.m":
        issues = check(code, filename="scratch.m", profile="student", extra_allowed=[problem.func_name, *ctx])
    else:
        issues = check(code, filename=problem.file, profile="student", extra_allowed=ctx,
                       banned_functions=problem.banned_functions, banned_operators=problem.banned_operators)
    return [i.to_dict() for i in issues]


def run(problem: Problem, code: str, scratch: str | None) -> dict:
    problem.save_student(code, scratch)
    issues = _issues(problem, code, scratch)
    if issues:
        return {"blocked": True, "issues": issues, "stdout": "", "stderr": "", "error": None,
                "figures": [], "timed_out": False, "seconds": 0}
    raw = engine.run_code(problem, code, scratch, problems.context_files(problem))
    token = f"run-{problem.id}-{datetime.now().strftime('%H%M%S%f')}"
    figures = store.keep_figures(token, raw["figures_paths"])
    engine.cleanup(raw["workdir"])
    out = {k: raw[k] for k in ("stdout", "stderr", "error", "timed_out", "seconds")}
    if raw["figure_error"]:
        out["stderr"] = (out["stderr"] + "\nPlots couldn't be drawn: " + raw["figure_error"]).strip()
    return {"blocked": False, "issues": [], "figures": figures, **out}


def _context(problem: Problem) -> list[Problem]:
    return [c for c in (problems.find(cid) for cid in problem.context) if c is not None]


def submit(problem: Problem, code: str, scratch: str | None, background: bool = True) -> dict:
    """Grade a submission. Returns it as soon as the tests finish; the review completes in a thread."""
    problem.save_student(code, scratch)
    fails_before = store.fails(problem.id)
    sid = store.new_id(problem.id)
    sub: dict = {"id": sid, "time": datetime.now().isoformat(timespec="seconds"), "code": code,
                 "issues": [], "cases": [], "error": None, "stdout": "", "figures": [], "passed": 0,
                 "total": 0, "hint": None}
    issues = [i for i in _issues(problem, code, None)]
    if issues:
        sub.update(tests_verdict="blocked", issues=issues)
    else:
        tests = engine.run_tests(problem, code, extra_files=problems.context_files(problem))
        sub["figures"] = store.keep_figures(f"{problem.id}-{sid}", tests["figures_paths"])
        engine.cleanup(tests["workdir"])
        for k in ("tests_verdict", "cases", "error", "passed", "total", "stdout"):
            sub[k] = tests[k]
        if tests["figure_error"]:
            sub["stdout"] = (sub["stdout"] + "\nPlots couldn't be drawn: " + tests["figure_error"]).strip()

    claude_available = review.find_claude() is not None
    tests_ok = sub["tests_verdict"] == "accepted"
    blocked = sub["tests_verdict"] == "blocked"
    if blocked and review.hint_level(fails_before + 1) == 0:
        # Nothing ran, so there's nothing to review, and no hint is due yet.
        sub["review"] = {"status": "skipped"}
        sub["verdict"] = "blocked"
        sub["fails_after"] = fails_before + 1
        store.save(problem.id, sub)
        return sub
    if claude_available:
        sub["review"] = {"status": "pending"}
        sub["verdict"] = "pending" if tests_ok else sub["tests_verdict"]
    else:
        sub["review"] = {"status": "unavailable", "reason": "Claude Code isn't installed or wasn't found."}
        sub["verdict"] = sub["tests_verdict"]
    sub["fails_after"] = fails_before + (0 if sub["verdict"] in ("accepted", "pending") else 1)
    store.save(problem.id, sub)

    if claude_available:
        job = threading.Thread(target=_finish_review, args=(problem, sub, fails_before), daemon=True)
        job.start()
        if not background:
            job.join()
            return store.load(problem.id, sid) or sub
    return sub


def _finish_review(problem: Problem, sub: dict, fails_before: int) -> None:
    sub = dict(sub)
    earlier = store.previous_hints(problem.id)
    try:
        result = review.review(problem, sub, fails_before + 1, earlier, _context(problem))
    except Exception as e:  # never leave a submission pending
        result = {"status": "unavailable", "reason": f"Review failed: {e}"}
    hint_text = result.pop("hint_text", "")
    level = result.pop("level", 0)
    sub["review"] = result if sub["tests_verdict"] != "blocked" else {"status": "skipped"}
    if sub["tests_verdict"] == "accepted":
        clean = result["status"] != "done" or (result["matlab_ok"] and not result["gaming"] and result["rules_ok"])
        sub["verdict"] = "accepted" if clean else "flagged"
    else:
        sub["verdict"] = sub["tests_verdict"]
    failed = sub["verdict"] != "accepted"
    sub["fails_after"] = fails_before + (1 if failed else 0)
    if failed and level and hint_text:
        sub["hint"] = {"level": level, "text": hint_text}
    store.save(problem.id, sub)
