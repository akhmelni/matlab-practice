"""Problem folders (examples/ and my-work/problems/) and the student's files for each."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KINDS = ("function", "value", "plot")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp"}


class ProblemError(ValueError):
    """problem.json is missing or invalid."""


@dataclass
class Problem:
    id: str
    dir: Path
    set: str
    number: int
    title: str
    kind: str
    file: str
    function: dict = field(default_factory=dict)
    answers: list = field(default_factory=list)
    banned_functions: list = field(default_factory=list)
    banned_operators: list = field(default_factory=list)
    context: list = field(default_factory=list)
    source: str | None = None
    timeout_s: int = 30
    example: bool = False

    # ---- files in the problem folder ----

    def read(self, name: str) -> str:
        path = self.dir / name
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    @property
    def statement(self) -> str:
        return self.read("problem.md")

    @property
    def submit_text(self) -> str:
        return self.read("submit.md")

    @property
    def source_path(self) -> Path | None:
        if self.source and (self.dir / self.source).is_file():
            return self.dir / self.source
        return None

    @property
    def func_name(self) -> str:
        return self.function.get("name", "") if self.kind == "function" else ""

    @property
    def script_name(self) -> str:
        """The script the runner executes: scratch for function problems, the solution otherwise."""
        return "scratch" if self.kind == "function" else Path(self.file).stem

    # ---- the student's files ----

    @property
    def student_dir(self) -> Path:
        return config.solutions_dir() / self.id

    def student_code(self) -> str:
        path = self.student_dir / self.file
        return path.read_text(encoding="utf-8") if path.is_file() else self.read("starter.m")

    def student_scratch(self) -> str | None:
        if self.kind != "function":
            return None
        path = self.student_dir / "scratch.m"
        return path.read_text(encoding="utf-8") if path.is_file() else self.read("scratch.m")

    def save_student(self, code: str, scratch: str | None) -> None:
        self.student_dir.mkdir(parents=True, exist_ok=True)
        (self.student_dir / self.file).write_text(code, encoding="utf-8", newline="\n")
        if self.kind == "function" and scratch is not None:
            (self.student_dir / "scratch.m").write_text(scratch, encoding="utf-8", newline="\n")


def context_files(problem: Problem) -> dict[str, str]:
    """The student's own function files from the problems this one refers to ("the previous problem")."""
    files: dict[str, str] = {}
    for cid in problem.context:
        other = find(cid)
        if other is None or other.kind != "function" or other.file == problem.file:
            continue
        files[other.file] = other.student_code()
    return files


def parse(folder: Path, example: bool = False) -> Problem:
    """Load and check problem.json. Raises ProblemError with a readable reason."""
    meta_path = folder / "problem.json"
    if not meta_path.is_file():
        raise ProblemError(f"{folder.name}: problem.json is missing")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProblemError(f"{folder.name}: problem.json is not valid JSON ({e})") from e
    errors = schema_errors(meta, folder.name)
    if errors:
        raise ProblemError("; ".join(errors))
    return Problem(
        id=meta["id"], dir=folder, set=meta["set"], number=int(meta["number"]), title=meta["title"],
        kind=meta["kind"], file=meta["file"], function=meta.get("function") or {},
        answers=meta.get("answers") or [], banned_functions=meta.get("banned_functions") or [],
        banned_operators=meta.get("banned_operators") or [], context=meta.get("context") or [],
        source=meta.get("source"), timeout_s=int(meta.get("timeout_s") or 30), example=example,
    )


def schema_errors(meta: object, folder_name: str) -> list[str]:
    if not isinstance(meta, dict):
        return ["problem.json must be a JSON object"]
    errs: list[str] = []
    for key in ("id", "set", "number", "title", "kind", "file"):
        if key not in meta:
            errs.append(f"problem.json is missing '{key}'")
    if errs:
        return errs
    if not isinstance(meta["id"], str) or not ID_RE.match(meta["id"]):
        errs.append("id must be lowercase letters, digits and dashes, e.g. hw3-08-cos-interp")
    elif meta["id"] != folder_name:
        errs.append(f"id '{meta['id']}' must equal the folder name '{folder_name}'")
    if not isinstance(meta["number"], int):
        errs.append("number must be an integer")
    if meta["kind"] not in KINDS:
        errs.append(f"kind must be one of {', '.join(KINDS)}")
    file = meta["file"]
    if not isinstance(file, str) or not re.match(r"^[A-Za-z][A-Za-z0-9_]*\.m$", file):
        errs.append("file must be a MATLAB file name like myFunction.m")
    if meta["kind"] == "function":
        fn = meta.get("function")
        if not isinstance(fn, dict) or not NAME_RE.match(str(fn.get("name", ""))):
            errs.append("function problems need function.name")
        else:
            if isinstance(file, str) and file != fn["name"] + ".m":
                errs.append(f"file must be {fn['name']}.m (MATLAB requires the file name to match the function)")
            for k in ("inputs", "outputs"):
                if not isinstance(fn.get(k), list) or not all(isinstance(n, str) for n in fn.get(k, [])):
                    errs.append(f"function.{k} must be a list of argument names")
    else:
        if file != "solution.m":
            errs.append("value and plot problems use file solution.m")
    if meta["kind"] == "value":
        ans = meta.get("answers")
        if not isinstance(ans, list) or not ans or not all(isinstance(a, str) and NAME_RE.match(a) for a in ans):
            errs.append("value problems need answers: a list of variable names, e.g. [\"answer\"]")
    for k in ("banned_functions", "banned_operators", "context"):
        if k in meta and not (isinstance(meta[k], list) and all(isinstance(v, str) for v in meta[k])):
            errs.append(f"{k} must be a list of strings")
    if meta.get("source") is not None and not isinstance(meta.get("source"), str):
        errs.append("source must be a file name")
    if "timeout_s" in meta and not (isinstance(meta["timeout_s"], int) and 1 <= meta["timeout_s"] <= 120):
        errs.append("timeout_s must be an integer from 1 to 120")
    return errs


def _scan(base: Path, example: bool) -> list[Problem]:
    out = []
    if not base.is_dir():
        return out
    for folder in sorted(base.iterdir()):
        if folder.is_dir() and ID_RE.match(folder.name) and (folder / "problem.json").is_file():
            try:
                out.append(parse(folder, example))
            except ProblemError:
                continue  # invalid problems are skipped; `validate` explains why
    return out


def all_problems() -> list[Problem]:
    problems = _scan(config.EXAMPLES_DIR, True) + _scan(config.problems_dir(), False)
    seen: dict[str, Problem] = {}
    for p in problems:
        seen.setdefault(p.id, p)
    return sorted(seen.values(), key=lambda p: (p.example, p.set, p.number, p.id))


def find(problem_id: str) -> Problem | None:
    if not ID_RE.match(problem_id or ""):
        return None
    for base, example in ((config.problems_dir(), False), (config.EXAMPLES_DIR, True)):
        folder = base / problem_id
        if (folder / "problem.json").is_file():
            try:
                return parse(folder, example)
            except ProblemError:
                return None
    return None
