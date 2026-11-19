"""Check that everything the app needs is installed and working.

    uv run check-setup               all checks (includes one short Claude request)
    uv run check-setup --no-claude   skip the Claude request (CI, offline)
    uv run check-setup --json        machine-readable

Exit code 0 when every required check passes. Claude is optional: without it the app works, but
submissions are not reviewed and hints are off.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config, engine, problems, review

results: list[dict] = []


def record(name: str, ok: bool, detail: str, required: bool = True, fix: str = "") -> bool:
    results.append({"check": name, "ok": ok, "required": required, "detail": detail, "fix": fix})
    return ok


def check_python() -> None:
    v = sys.version_info
    record("Python", v >= (3, 12), f"{v.major}.{v.minor}.{v.micro}", fix="uv sync installs the right Python")


def check_octave() -> bool:
    o = engine.find_octave(refresh=True)
    if not o.found:
        return record("Octave", False, "not found",
                      fix="Install GNU Octave (INSTALL.md step 3), or set OCTAVE=<path to octave-cli> in .env")
    major = int((o.version or "0").split(".")[0] or 0)
    record("Octave", major >= 8, f"{o.version} at {o.cli}", fix="Octave 8 or newer is needed")
    record("Octave graphics program", o.gui is not None, o.gui or "not found next to octave-cli",
           fix="Plots need the full 'octave' program next to octave-cli (normally installed together)")
    return major >= 8


def _run_example(pid: str) -> dict | None:
    p = problems.find(pid)
    ref = config.ROOT / "tests" / "references" / f"{pid}.m"
    if p is None or not ref.is_file():
        return None
    r = engine.run_tests(p, ref.read_text(encoding="utf-8"))
    engine.cleanup(r["workdir"])
    return r


def check_grading() -> None:
    r = _run_example("ex-01-mylininterp")
    if r is None:
        record("Grading", False, "example ex-01-mylininterp or its reference is missing")
        return
    record("Grading", r["tests_verdict"] == "accepted",
           f"example function problem: {r['tests_verdict']}, {r['passed']}/{r['total']} in {r['seconds']} s",
           fix=r["error"] or "")


def check_plots() -> None:
    r = _run_example("ex-03-sin-cos-plot")
    if r is None:
        record("Plots", False, "example ex-03-sin-cos-plot or its reference is missing")
        return
    n = len(r["figures_paths"])
    ok = r["tests_verdict"] == "accepted" and n >= 1
    record("Plots", ok, f"{n} figure(s) saved in {r['seconds']} s",
           fix=r["figure_error"] or r["error"] or "Octave could not save the plot as an image")


def check_checker() -> None:
    try:
        from .checker import check
        issues = check("x = 1;\nx += 1;\n")
        ok = any(i.severity == "error" for i in issues)
        record("MATLAB checker", ok, "catches Octave-only `+=`" if ok else "did not flag `x += 1`")
    except Exception as e:  # pragma: no cover
        record("MATLAB checker", False, f"failed to load: {e}")


def check_examples() -> None:
    from .validate import validate
    bad = []
    count = 0
    for p in problems.all_problems():
        if not p.example:
            continue
        count += 1
        ref = config.ROOT / "tests" / "references" / f"{p.id}.m"
        rep = validate(p.dir, ref if ref.is_file() else None)
        if not rep.passed:
            bad.append(p.id)
    record("Example problems", not bad and count > 0,
           f"{count - len(bad)}/{count} valid" + (f" (not valid: {', '.join(bad)})" if bad else ""))


def check_work_dir() -> None:
    try:
        config.work_dir().mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=config.work_dir()):
            pass
        record("Work folder", True, str(config.work_dir()))
    except OSError as e:
        record("Work folder", False, f"{config.work_dir()}: {e}")


def check_port() -> None:
    port = int(config.setting("PORT", "8770"))
    with socket.socket() as s:
        busy = s.connect_ex(("127.0.0.1", port)) == 0
    record("Port", True, f"{port} " + ("is in use (the app may already be running)" if busy else "is free"),
           required=False)


def check_claude(live: bool) -> None:
    cmd = review.find_claude()
    if cmd is None:
        record("Claude Code", False, "not found", required=False,
               fix="Install Claude Code and sign in with the Claude subscription (INSTALL.md)")
        return
    if not live:
        record("Claude Code", True, f"found at {cmd[-1]} (sign-in not checked)", required=False)
        return
    try:
        proc = subprocess.run(cmd + ["-p", "--output-format", "json", "--tools", "", "--no-session-persistence"],
                              input="Reply with just the word OK.", capture_output=True, text=True,
                              timeout=120, cwd=tempfile.gettempdir())
        data = json.loads(proc.stdout or "{}")
        if isinstance(data, list):
            data = next((d for d in reversed(data) if isinstance(d, dict) and d.get("type") == "result"), {})
        ok = not data.get("is_error") and "OK" in str(data.get("result", "")).upper()
        detail = "signed in and answering" if ok else str(data.get("result") or proc.stderr.strip())[:200]
        record("Claude Code", ok, detail, required=False,
               fix="" if ok else "Run `claude` once and sign in with the Claude subscription (/login)")
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as e:
        record("Claude Code", False, f"could not run: {e}", required=False,
               fix="Run `claude` once and sign in with the Claude subscription (/login)")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    check_python()
    if check_octave():
        check_grading()
        check_plots()
    check_checker()
    if engine.find_octave().found:
        check_examples()
    check_work_dir()
    check_port()
    check_claude(live="--no-claude" not in argv)

    if "--json" in argv:
        print(json.dumps(results, indent=1))
    else:
        for r in results:
            mark = "OK  " if r["ok"] else ("FAIL" if r["required"] else "WARN")
            print(f"{mark}  {r['check']}: {r['detail']}")
            if not r["ok"] and r["fix"]:
                print(f"      fix: {r['fix']}")
        failed = [r for r in results if r["required"] and not r["ok"]]
        print("\nAll required checks passed." if not failed else f"\n{len(failed)} required check(s) failed.")
    sys.exit(0 if all(r["ok"] for r in results if r["required"]) else 1)


if __name__ == "__main__":
    main()
