import shutil

import pytest

from matlab_practice import config, engine
from matlab_practice.validate import validate

pytestmark = pytest.mark.skipif(not engine.find_octave().found, reason="Octave not installed")
REFS = config.ROOT / "tests" / "references"


@pytest.mark.parametrize("pid", ["ex-01-mylininterp", "ex-02-basel-terms", "ex-03-sin-cos-plot"])
def test_examples_are_valid(pid):
    rep = validate(config.EXAMPLES_DIR / pid, REFS / f"{pid}.m")
    assert rep.passed, rep.items


def copy_example(tmp_path, pid, new_id, source=True):
    dest = tmp_path / "problems" / new_id
    shutil.copytree(config.EXAMPLES_DIR / pid, dest)
    meta = (dest / "problem.json").read_text().replace(pid, new_id)
    if source:
        (dest / "source.png").write_bytes(b"\x89PNG fake")
        meta = meta.replace('"timeout_s"', '"source": "source.png", "timeout_s"')
    (dest / "problem.json").write_text(meta)
    return dest


def test_wrong_expected_value_is_caught(tmp_path):
    dest = copy_example(tmp_path, "ex-01-mylininterp", "hw1-01-interp")
    tests = (dest / "tests.m").read_text().replace("{[2.5 15]}", "{[2.5 17.5]}")
    (dest / "tests.m").write_text(tests)
    rep = validate(dest, REFS / "ex-01-mylininterp.m")
    assert not rep.passed
    assert any("does NOT pass" in t for ok, t in rep.items if not ok)


def test_homework_problem_needs_source(tmp_path):
    dest = copy_example(tmp_path, "ex-02-basel-terms", "hw1-02-basel", source=False)
    rep = validate(dest, REFS / "ex-02-basel-terms.m")
    assert any("original image" in t for ok, t in rep.items if not ok)


def test_answer_leak_is_caught(tmp_path):
    dest = copy_example(tmp_path, "ex-02-basel-terms", "hw1-02-basel")
    (dest / "submit.md").write_text("Store n (it should be 1000) in `n`.")
    rep = validate(dest, REFS / "ex-02-basel-terms.m")
    assert any("appears in submit.md" in t for ok, t in rep.items if not ok)


def test_octave_only_tests_file_is_caught(tmp_path):
    dest = copy_example(tmp_path, "ex-01-mylininterp", "hw1-01-interp")
    (dest / "tests.m").write_text((dest / "tests.m").read_text().replace("  cases = {};", "  cases = {}; # list"))
    rep = validate(dest, REFS / "ex-01-mylininterp.m")
    assert any("tests.m line" in t for ok, t in rep.items if not ok)


def test_weak_tests_are_caught(tmp_path):
    dest = copy_example(tmp_path, "ex-01-mylininterp", "hw1-01-interp")
    (dest / "starter.m").write_text((REFS / "ex-01-mylininterp.m").read_text())
    rep = validate(dest, REFS / "ex-01-mylininterp.m")
    assert any("too weak" in t for ok, t in rep.items if not ok)
