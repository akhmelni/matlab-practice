"""Corpus tests for the MATLAB checker.

- tests/checker/octave_only/*.m: first line ``% expect: rule[, rule...]``; each rule must be reported.
- tests/checker/valid/*.m: valid MATLAB; must produce no issues. ``% allow: name ...`` and
  ``% profile: authoring`` header lines are honoured.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from matlab_practice.checker import check

HERE = Path(__file__).parent / "checker"
OCTAVE = sorted((HERE / "octave_only").glob("*.m"))
VALID = sorted((HERE / "valid").glob("*.m"))


def _header(code: str, key: str) -> list[str]:
    out: list[str] = []
    for line in code.splitlines()[:5]:
        m = re.match(rf"\s*%\s*{key}:\s*(.*)$", line)
        if m:
            out += [w for w in re.split(r"[,\s]+", m.group(1)) if w]
    return out


def _run(path: Path):
    code = path.read_text(encoding="utf-8")
    profile = (_header(code, "profile") or ["student"])[0]
    return code, check(code, filename=path.name, profile=profile, extra_allowed=_header(code, "allow"))


def test_corpus_sizes():
    assert len(OCTAVE) >= 40
    assert len(VALID) >= 30


@pytest.mark.parametrize("path", OCTAVE, ids=lambda p: p.stem)
def test_octave_only_is_caught(path: Path):
    code, issues = _run(path)
    expected = _header(code, "expect")
    assert expected, f"{path.name} needs a '% expect: rule' first line"
    rules = {i.rule for i in issues}
    for rule in expected:
        assert rule in rules, f"{path.name}: expected {rule}, got {[i.to_dict() for i in issues]}"
    for i in issues:
        assert i.severity == "error"
        assert i.message and i.line >= 1 and i.col >= 1
        assert (i.end_line, i.end_col) > (i.line, i.col)


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_matlab_has_no_issues(path: Path):
    _, issues = _run(path)
    assert issues == [], "\n".join(f"{i.line}:{i.col} {i.rule}: {i.message}" for i in issues)
