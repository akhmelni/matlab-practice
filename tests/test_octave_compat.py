import json

import pytest

from matlab_practice import engine, grading, problems
from matlab_practice.octave_compat import prepare_files, split_local_functions
from conftest import reference

octave = pytest.mark.skipif(not engine.find_octave().found, reason="Octave not installed")

SCRIPT = """target = pi^2 / 6;
[n, total] = countTerms(target, 0.001);
fprintf('%d\\n', n);

function [n, total] = countTerms(target, tol)
  total = 0;
  n = 0;
  while abs(target - total) >= tol
    n = n + 1;
    total = total + step(n);
  end
end

function s = step(k)
  v = [1 2 3];
  s = 1 / k^2 + 0 * v(end);
end
"""


def test_split_keeps_line_numbers():
    script, moved = split_local_functions(SCRIPT)
    assert [name for name, _ in moved] == ["countTerms.m", "step.m"]
    assert script.splitlines()[:3] == SCRIPT.splitlines()[:3]
    assert len(script.splitlines()) == len(SCRIPT.splitlines())
    body = dict(moved)["step.m"].splitlines()
    assert body[13].startswith("function s = step(k)")  # same line number as in the script


def test_split_ignores_function_files():
    code = "function y = f(x)\n  y = g(x);\nend\nfunction z = g(x)\n  z = x;\nend\n"
    files, origin = prepare_files({"f.m": code}, {"scratch.m"})
    assert files == {"f.m": code} and origin == {}


def test_never_overwrites_student_function():
    files, origin = prepare_files({"myF.m": "function y = myF(x)\ny = x;\nend\n",
                                   "scratch.m": "a = myF(1);\nfunction y = myF(x)\ny = 2;\nend\n"},
                                  {"scratch.m"})
    assert files["myF.m"].startswith("function y = myF(x)\ny = x;") and origin == {}


@octave
def test_script_with_local_functions_runs(work):
    p = problems.find("ex-02-basel-terms")
    r = engine.run_tests(p, SCRIPT)
    engine.cleanup(r["workdir"])
    assert r["tests_verdict"] == "accepted", r


@octave
def test_error_in_local_function_points_at_script_line(work):
    p = problems.find("ex-02-basel-terms")
    bad = SCRIPT.replace("v(end)", "v(5)")
    r = engine.run_tests(p, bad)
    engine.cleanup(r["workdir"])
    assert r["tests_verdict"] == "error"
    assert r["error"].startswith("Error in solution.m line 16:"), r["error"]


@octave
def test_scratch_local_function(work):
    p = problems.find("ex-01-mylininterp")
    scratch = "show(myLinInterp([0;1], [0;2], 0.5));\nfunction show(v)\n  fprintf('value %g\\n', v);\nend\n"
    r = grading.run(p, reference("ex-01-mylininterp"), scratch)
    assert not r["blocked"] and r["error"] is None and "value 1" in r["stdout"], r


@octave
def test_previous_problem_function_available(work):
    problems.find("ex-01-mylininterp").save_student(reference("ex-01-mylininterp"), None)
    folder = work / "problems" / "hw9-02-use-previous"
    folder.mkdir(parents=True)
    (folder / "problem.json").write_text(json.dumps({
        "id": "hw9-02-use-previous", "set": "hw9", "number": 2, "title": "Use the previous function",
        "kind": "value", "file": "solution.m", "answers": ["answer"], "context": ["ex-01-mylininterp"],
        "source": "source.png"}))
    (folder / "source.png").write_bytes(b"\x89PNG")
    (folder / "problem.md").write_text("Use the function from the previous problem.")
    (folder / "submit.md").write_text("Store it in `answer`.")
    (folder / "starter.m").write_text("% Write your script here.\n")
    (folder / "tests.m").write_text("function cases = tests()\n  cases = {};\n"
                                    "  cases{end+1} = mp_value('value', 'answer', 1);\nend\n")
    p = problems.find("hw9-02-use-previous")
    assert grading.lint(p, "answer = myLinInterp([0;1], [0;2], 0.5);\n") == []
    sub = grading.submit(p, "answer = myLinInterp([0;1], [0;2], 0.5);\n", None, background=False)
    assert sub["tests_verdict"] == "accepted", sub
