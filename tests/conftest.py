import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAKE_CLAUDE = ROOT / "tests" / "fake_claude.py"


@pytest.fixture
def work(tmp_path, monkeypatch):
    """A fresh my-work folder and the fake Claude for every test."""
    monkeypatch.setenv("MP_WORK_DIR", str(tmp_path / "my-work"))
    monkeypatch.setenv("CLAUDE", str(FAKE_CLAUDE))
    monkeypatch.delenv("FAKE_CLAUDE_FAIL", raising=False)
    return tmp_path / "my-work"


def reference(pid: str) -> str:
    return (ROOT / "tests" / "references" / f"{pid}.m").read_text(encoding="utf-8")
