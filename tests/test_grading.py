import pytest

from matlab_practice import engine, grading, problems, store
from conftest import reference

pytestmark = pytest.mark.skipif(not engine.find_octave().found, reason="Octave not installed")

PID = "ex-01-mylininterp"
WRONG = "function [Y] = myLinInterp(x,y,X)\nY = X;\nend\n"


def submit(code, scratch=None):
    return grading.submit(problems.find(PID), code, scratch, background=False)


def test_accepted_after_review(work):
    sub = submit(reference(PID))
    assert sub["tests_verdict"] == "accepted"
    assert sub["verdict"] == "accepted" and sub["review"]["status"] == "done"
    assert sub["hint"] is None and sub["fails_after"] == 0
    assert store.status(PID) == "solved"


def test_gaming_is_flagged(work):
    sub = submit(reference(PID) + "\n% FAKE_GAMING\n")
    assert sub["tests_verdict"] == "accepted" and sub["verdict"] == "flagged"
    assert sub["fails_after"] == 1


def test_octaveism_is_flagged(work):
    assert submit(reference(PID) + "\n% FAKE_OCTAVEISM\n")["verdict"] == "flagged"


def test_blocked_by_checker_counts_as_failure(work):
    code = "function [Y] = myLinInterp(x,y,X)\nY = X;\nY += 1;\nend\n"
    sub = submit(code)
    assert sub["verdict"] == "blocked" and sub["issues"] and sub["total"] == 0
    assert sub["review"]["status"] == "skipped" and sub["hint"] is None
    assert store.fails(PID) == 1


def test_blocked_gets_hint_when_due(work):
    for _ in range(4):
        submit(WRONG)
    sub = submit("function [Y] = myLinInterp(x,y,X)\nY = X;\nY += 1;\nend\n")
    assert sub["verdict"] == "blocked" and sub["review"]["status"] == "skipped"
    assert sub["hint"]["level"] == 1


def test_banned_function_blocked(work):
    sub = submit("function [Y] = myLinInterp(x,y,X)\nY = interp1(x, y, X);\nend\n")
    assert sub["verdict"] == "blocked"
    assert any(i["rule"] == "banned-function" for i in sub["issues"])


def test_hint_ladder(work):
    levels = []
    for _ in range(9):
        sub = submit(WRONG)
        assert sub["verdict"] == "wrong"
        levels.append(sub["hint"]["level"] if sub["hint"] else 0)
    assert levels == [0, 0, 0, 0, 1, 2, 2, 3, 3]
    assert store.fails(PID) == 9
    assert "Hint level 3" in store.all_for(PID)[0]["hint"]["text"]


def test_no_hint_when_accepted_late(work):
    for _ in range(5):
        submit(WRONG)
    sub = submit(reference(PID))
    assert sub["verdict"] == "accepted" and sub["hint"] is None


def test_claude_missing_means_unreviewed(work, monkeypatch):
    monkeypatch.setenv("CLAUDE", str(work / "does-not-exist"))
    monkeypatch.setattr("matlab_practice.review.find_claude", lambda: None)
    monkeypatch.setattr("matlab_practice.grading.review.find_claude", lambda: None)
    sub = submit(reference(PID))
    assert sub["verdict"] == "accepted" and sub["review"]["status"] == "unavailable"


def test_claude_signed_out_means_unreviewed(work, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_FAIL", "auth")
    sub = submit(reference(PID))
    assert sub["verdict"] == "accepted" and sub["review"]["status"] == "unavailable"
    assert "authenticate" in sub["review"]["reason"]


def test_run_blocked_and_ok(work):
    p = problems.find(PID)
    r = grading.run(p, reference(PID), "Y = myLinInterp([0;1], [0;2], 0.5)\nY != 1")
    assert r["blocked"] and r["issues"][0]["file"] == "scratch.m"
    r = grading.run(p, reference(PID), "Y = myLinInterp([0;1], [0;2], 0.5)")
    assert not r["blocked"] and "Y = 1" in r["stdout"]
    assert (work / "solutions" / PID / "scratch.m").read_text().startswith("Y = myLinInterp")


def test_plot_submission_keeps_figure(work):
    p = problems.find("ex-03-sin-cos-plot")
    sub = grading.submit(p, reference("ex-03-sin-cos-plot"), None, background=False)
    assert sub["verdict"] == "accepted" and len(sub["figures"]) == 1
    token, name = sub["figures"][0].split("/")[-2:]
    assert store.figure_path(token, name) is not None
