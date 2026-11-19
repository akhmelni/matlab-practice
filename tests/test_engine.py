import os

import pytest

from matlab_practice import engine, problems
from conftest import reference

pytestmark = pytest.mark.skipif(not engine.find_octave().found, reason="Octave not installed")

BUGGY = """function [Y] = myLinInterp(x,y,X)
Y = zeros(numel(X), 1);
for k = 1:numel(X)
  i = find(x <= X(k), 1, 'last');
  Y(k) = y(i) + (y(i+1) - y(i)) * (X(k) - x(i)) / (x(i+1) - x(i));
end
end
"""


def run(pid, code):
    r = engine.run_tests(problems.find(pid), code)
    engine.cleanup(r["workdir"])
    return r


def test_reference_passes():
    r = run("ex-01-mylininterp", reference("ex-01-mylininterp"))
    assert r["tests_verdict"] == "accepted" and r["passed"] == r["total"] > 10


def test_buggy_reports_cases():
    r = run("ex-01-mylininterp", BUGGY)
    assert r["tests_verdict"] == "wrong"
    by_name = {c["name"]: c for c in r["cases"]}
    shape = by_name["uneven spacing (row)"]
    assert shape["status"] == "failed" and shape["message"] == "expected size 1x2, got 2x1"
    assert shape["expected"] == "[2.5 15]" and shape["actual"] == "[2.5;15]"
    assert "X = [0.25 3.5]" in shape["input"]
    crash = by_name["the last data point alone"]
    assert crash["status"] == "error"
    assert crash["message"].startswith("Error in myLinInterp.m line 5: Index exceeds")
    assert crash["input"]  # inputs are shown even when the code crashed


def test_syntax_error():
    r = run("ex-01-mylininterp", "function [Y] = myLinInterp(x,y,X)\nY = X +\nend\n")
    assert r["tests_verdict"] == "error"
    assert "Invalid syntax" in r["error"]


def test_infinite_loop_times_out():
    p = problems.find("ex-01-mylininterp")
    p.timeout_s = 3
    r = engine.run_tests(p, "function [Y] = myLinInterp(x,y,X)\nY = X;\nwhile true\nend\nend\n")
    engine.cleanup(r["workdir"])
    assert r["tests_verdict"] == "timeout" and r["seconds"] < 10


def test_value_problem_hidden():
    r = run("ex-02-basel-terms", "n = 999;\ntotal = 1.64;\n")
    assert r["tests_verdict"] == "wrong"
    for c in r["cases"]:
        assert c["hidden"] and c["expected"] is None and c["actual"] is None


def test_value_reference():
    assert run("ex-02-basel-terms", reference("ex-02-basel-terms"))["tests_verdict"] == "accepted"


def test_plot_makes_figure():
    r = engine.run_tests(problems.find("ex-03-sin-cos-plot"), reference("ex-03-sin-cos-plot"))
    try:
        assert r["tests_verdict"] == "accepted"
        assert len(r["figures_paths"]) == 1
        if not os.environ.get("GITHUB_ACTIONS"):  # GitHub's machines have no graphics card: plots save blank
            assert r["figures_paths"][0].stat().st_size > 1000
    finally:
        engine.cleanup(r["workdir"])


def test_run_scratch():
    p = problems.find("ex-01-mylininterp")
    r = engine.run_code(p, reference("ex-01-mylininterp"), "Y = myLinInterp([0;1], [0;2], 0.5)")
    engine.cleanup(r["workdir"])
    assert r["error"] is None and "Y = 1" in r["stdout"]


def test_run_error_is_matlab_worded():
    p = problems.find("ex-01-mylininterp")
    r = engine.run_code(p, reference("ex-01-mylininterp"), "z = undefinedThing + 1")
    engine.cleanup(r["workdir"])
    assert "Unrecognized function or variable 'undefinedThing'" in r["error"]


def test_uses_graphics():
    assert engine.uses_graphics("x = 1;\nplot(x)")
    assert not engine.uses_graphics("% plot(x)\ny = 'plot';\n")
