"""Submissions on disk: my-work/submissions/<problem id>/<submission id>.json (+ figures)."""

from __future__ import annotations

import json
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from . import config

SID_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
TOKEN_RE = re.compile(r"^[a-z0-9-]+$")
FINAL_FAILS = {"wrong", "error", "timeout", "blocked", "flagged"}
_lock = threading.Lock()


def _dir(problem_id: str) -> Path:
    return config.submissions_dir() / problem_id


def new_id(problem_id: str) -> str:
    folder = _dir(problem_id)
    folder.mkdir(parents=True, exist_ok=True)
    base = sid = datetime.now().strftime("%Y%m%d-%H%M%S")
    n = 1
    while (folder / f"{sid}.json").exists():
        n += 1
        sid = f"{base}-{n}"
    (folder / f"{sid}.json").write_text("{}", encoding="utf-8")  # reserve the name
    return sid


def save(problem_id: str, sub: dict) -> None:
    with _lock:
        path = _dir(problem_id) / f"{sub['id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(sub, indent=1), encoding="utf-8")
        tmp.replace(path)


def load(problem_id: str, sid: str) -> dict | None:
    if not SID_RE.match(sid or ""):
        return None
    path = _dir(problem_id) / f"{sid}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data or None


def _order(path: Path) -> tuple[str, int]:
    """Oldest first: by timestamp, then by the -2, -3 ... suffix used within one second."""
    base, _, n = path.stem.partition("-")[2].partition("-")
    return (path.stem.split("-")[0] + base, int(n) if n.isdigit() else 1)


def all_for(problem_id: str) -> list[dict]:
    folder = _dir(problem_id)
    if not folder.is_dir():
        return []
    subs = []
    for f in sorted(folder.glob("*.json"), key=_order, reverse=True):
        if SID_RE.match(f.stem):
            data = load(problem_id, f.stem)
            if data:
                subs.append(data)
    return subs


def summary(sub: dict) -> dict:
    return {k: v for k, v in sub.items() if k not in ("code", "cases", "stdout")}


def fails(problem_id: str) -> int:
    return sum(1 for s in all_for(problem_id) if s.get("verdict") in FINAL_FAILS)


def status(problem_id: str) -> str:
    subs = all_for(problem_id)
    if not subs:
        return "new"
    return "solved" if any(s.get("verdict") == "accepted" for s in subs) else "attempted"


def previous_hints(problem_id: str) -> list[str]:
    hints = []
    for s in reversed(all_for(problem_id)):
        h = s.get("hint")
        if h and h.get("text"):
            hints.append(h["text"])
    return hints


# ---- figures ----

def figures_root() -> Path:
    return config.work_dir() / "figures"


def keep_figures(token: str, paths: list[Path]) -> list[str]:
    """Copy figure PNGs into my-work/figures/<token>/ and return their URLs."""
    if not paths:
        return []
    folder = figures_root() / token
    folder.mkdir(parents=True, exist_ok=True)
    urls = []
    for i, p in enumerate(paths, start=1):
        shutil.copyfile(p, folder / f"{i}.png")
        urls.append(f"/api/figures/{token}/{i}.png")
    return urls


def figure_path(token: str, name: str) -> Path | None:
    if not TOKEN_RE.match(token or "") or not re.match(r"^\d+\.png$", name or ""):
        return None
    path = figures_root() / token / name
    return path if path.is_file() else None
