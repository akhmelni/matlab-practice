"""Check that a problem folder is complete and its evaluator is proven.

    uv run validate <problem id or folder> [--reference path/to/reference.m] [--json]
    uv run validate --all            (every problem; examples use tests/references/<id>.m)

A problem passes only if every file is present and valid, every .m file passes the
MATLAB-compatibility checker, the reference solution passes every test, and the starter fails.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import config, engine, problems
from .checker import check

REQUIRED = ("problem.json", "problem.md", "submit.md", "starter.m", "tests.m")


class Report:
    def __init__(self, name: str):
        self.name = name
        self.items: list[tuple[bool, str]] = []

    def ok(self, text: str) -> None:
        self.items.append((True, text))

    def fail(self, text: str) -> None:
        self.items.append((False, text))

    @property
    def passed(self) -> bool:
        return all(ok for ok, _ in self.items)

    def print(self) -> None:
        print(f"\n{self.name}")
        for ok, text in self.items:
            print(f"  {'PASS' if ok else 'FAIL'}  {text}")
        print(f"  => {'VALID' if self.passed else 'NOT VALID'}")


def _folder(arg: str) -> Path | None:
    path = Path(arg)
    if path.is_dir():
        return path.resolve()
    for base in (config.problems_dir(), config.EXAMPLES_DIR):
        if (base / arg).is_dir():
            return base / arg
    return None


def _check_file(rep: Report, path: Path, label: str, **kw) -> bool:
    issues = [i for i in check(path.read_text(encoding="utf-8"), filename=path.name, **kw) if i.severity == "error"]
    if issues:
        for i in issues[:8]:
            rep.fail(f"{label} line {i.line}: [{i.rule}] {i.message}")
        return False
    rep.ok(f"{label} passes the MATLAB-compatibility checker")
    return True


_VALUE_RE = re.compile(r"mp_value\(\s*'[^']*'\s*,\s*'(\w+)'\s*,\s*([-+]?[\d.]+(?:[eE][-+]?\d+)?)\s*[,)]")


def validate(folder: Path, reference: Path | None) -> Report:
    rep = Report(f"Problem {folder.name}")
    missing = [f for f in REQUIRED if not (folder / f).is_file()]
    if missing:
        rep.fail("missing files: " + ", ".join(missing))
        return rep
    rep.ok("all required files are present")
    example = folder.parent.resolve() == config.EXAMPLES_DIR.resolve()
    try:
        p = problems.parse(folder, example)
    except problems.ProblemError as e:
        rep.fail(f"problem.json: {e}")
        return rep
    rep.ok("problem.json is valid")

    if not p.statement.strip():
        rep.fail("problem.md is empty")
    if not p.submit_text.strip():
        rep.fail("submit.md is empty")
    if p.kind == "function" and not (folder / "scratch.m").is_file():
        rep.fail("function problems need scratch.m")
    if p.source:
        if p.source_path:
            rep.ok(f"source image {p.source} is present")
        else:
            rep.fail(f"source image {p.source} is missing")
    elif not example:
        rep.fail("problems made from homework need the original image (set \"source\" in problem.json)")
    for cid in p.context:
        if problems.find(cid) is None:
            rep.fail(f"context problem '{cid}' doesn't exist (or isn't valid)")

    allowed = [p.func_name] if p.func_name else []
    _check_file(rep, folder / "starter.m", "starter.m", profile="student")
    if (folder / "scratch.m").is_file():
        _check_file(rep, folder / "scratch.m", "scratch.m", profile="student", extra_allowed=allowed)
    _check_file(rep, folder / "tests.m", "tests.m", profile="authoring", extra_allowed=allowed)
    tests_text = (folder / "tests.m").read_text(encoding="utf-8")
    if re.search(r"\b(rand|randn|randi|randperm|rng)\s*\(", re.sub(r"%.*", "", tests_text)):
        rep.fail("tests.m must not call rand/randn/randi: write random cases out as literal numbers")
    if not re.search(r"^\s*function\s+cases\s*=\s*tests\s*\(\s*\)", tests_text, re.M):
        rep.fail("tests.m must start with: function cases = tests()")

    if p.kind == "value":
        visible = re.findall(r"mp_value\([^;]*'hidden'\s*,\s*false", tests_text)
        if visible:
            rep.fail("value problems must keep expected answers hidden (remove 'hidden', false)")
        shown = p.submit_text + "\n" + p.title
        for var, literal in _VALUE_RE.findall(tests_text):
            value = float(literal)
            if (abs(value) >= 10 or len(re.sub(r"[^1-9]", "", literal)) >= 2) and re.search(rf"(?<![\d.]){re.escape(literal)}(?![\d])", shown):
                rep.fail(f"the expected value of {var} ({literal}) appears in submit.md or the title")

    if not rep.passed:
        return rep

    if reference is None:
        rep.fail("no reference solution given (--reference): the evaluator can't be proven")
        return rep
    if not reference.is_file():
        rep.fail(f"reference file {reference} not found")
        return rep
    _check_file(rep, reference, "reference solution", profile="student",
                banned_functions=p.banned_functions, banned_operators=p.banned_operators)

    try:
        ref = engine.run_tests(p, reference.read_text(encoding="utf-8"))
    except RuntimeError as e:
        rep.fail(str(e))
        return rep
    engine.cleanup(ref["workdir"])
    if ref["tests_verdict"] == "accepted":
        rep.ok(f"reference solution passes all {ref['total']} test case(s)" if ref["total"]
               else "reference solution runs without errors (self-checked problem)")
    else:
        rep.fail(f"reference solution does NOT pass: {ref['tests_verdict']}, {ref['passed']}/{ref['total']}")
        if ref["error"]:
            rep.fail("  error: " + ref["error"])
        for c in ref["cases"]:
            if c["status"] != "passed":
                detail = f"  case '{c['name']}': {c['status']}: {c['message']}"
                if c.get("expected") or c.get("actual"):
                    detail += f" (expected {c.get('expected')}, got {c.get('actual')})"
                rep.fail(detail)
        return rep

    if p.kind == "function" and p.function.get("outputs") and ref["total"] == 0:
        rep.fail("function problems need at least one test case")
    if p.kind == "value" and ref["total"] == 0:
        rep.fail("value problems need at least one mp_value check")

    if ref["total"]:
        start = engine.run_tests(p, p.read("starter.m"))
        engine.cleanup(start["workdir"])
        if start["tests_verdict"] == "accepted":
            rep.fail("the untouched starter passes the tests: the tests are too weak")
        else:
            rep.ok(f"the untouched starter fails ({start['tests_verdict']}), as it should")
    return rep


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="validate", description=__doc__.split("\n\n")[0])
    ap.add_argument("problem", nargs="?", help="problem id or folder")
    ap.add_argument("--reference", type=Path, help="reference solution to prove the tests with")
    ap.add_argument("--all", action="store_true", help="validate every problem")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    targets: list[tuple[Path, Path | None]] = []
    if args.all:
        for p in problems.all_problems():
            ref = config.ROOT / "tests" / "references" / f"{p.id}.m"
            targets.append((p.dir, ref if ref.is_file() else None))
    elif args.problem:
        folder = _folder(args.problem)
        if folder is None:
            print(f"No problem folder '{args.problem}' in my-work/problems or examples.")
            sys.exit(2)
        targets.append((folder, args.reference))
    else:
        ap.print_help()
        sys.exit(2)

    reports = [validate(f, r) for f, r in targets]
    if args.json:
        print(json.dumps([{"problem": r.name, "valid": r.passed,
                           "checks": [{"ok": ok, "text": t} for ok, t in r.items]} for r in reports], indent=1))
    else:
        for r in reports:
            r.print()
    sys.exit(0 if all(r.passed for r in reports) else 1)


if __name__ == "__main__":
    main()
