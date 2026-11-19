"""Tests for the checker API: bans, extra names, profiles, positions, the tokenizer and the CLI."""

from __future__ import annotations

import json

import pytest

from matlab_practice.checker import Issue, check
from matlab_practice.checker.cli import main as cli_main
from matlab_practice.checker.tables import OCTAVE_FUNCTIONS, matlab_names
from matlab_practice.checker.tokenizer import tokenize


def rules(code: str, **kw) -> list[str]:
    return [i.rule for i in check(code, **kw)]


# ---------------------------------------------------------------- Issue
def test_issue_fields_and_to_dict():
    [issue] = check("x = 1;\nx += 2;\n")
    assert isinstance(issue, Issue)
    assert (issue.line, issue.col, issue.end_line, issue.end_col) == (2, 3, 2, 5)
    assert issue.rule == "octave-syntax"
    assert issue.severity == "error"
    assert issue.message == "`+=` doesn't work in MATLAB. Write `x = x + 2`."
    assert issue.to_dict() == {
        "line": 2,
        "col": 3,
        "end_line": 2,
        "end_col": 5,
        "rule": "octave-syntax",
        "severity": "error",
        "message": "`+=` doesn't work in MATLAB. Write `x = x + 2`.",
    }


def test_compound_message_wraps_rhs():
    [issue] = check("x = 1; y = 2;\nx *= y + 1;\n")
    assert issue.message == "`*=` doesn't work in MATLAB. Write `x = x * (y + 1)`."


def test_empty_and_comment_only_code():
    assert check("") == []
    assert check("% just a comment\n\n%{\nblock\n%}\n") == []


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        check("x = 1;", profile="teacher")


# ---------------------------------------------------------------- bans
def test_banned_function():
    code = "x = [0 1 2]; y = [0 1 4];\nv = interp1(x, y, 1.5);\n"
    issues = check(code, banned_functions=["interp1"])
    assert [i.rule for i in issues] == ["banned-function"]
    assert issues[0].message == "This problem doesn't allow `interp1`."
    assert (issues[0].line, issues[0].col, issues[0].end_col) == (2, 5, 12)
    assert check(code) == []


def test_banned_function_handle_and_command_syntax():
    assert rules("f = @sqrt;\n", banned_functions=["sqrt"]) == ["banned-function"]
    assert rules("y = cellfun('sqrt', {4, 9});\n", banned_functions=["sqrt"]) == ["banned-function"]
    assert rules("y = arrayfun(@(v) sqrt(v), [4 9]);\n", banned_functions=["sqrt"]) == ["banned-function"]


def test_banned_function_not_flagged_in_strings_comments_fields():
    code = "% sqrt is banned\ns.sqrt = 2;\nt = 'sqrt';\nfprintf('%s\\n', t);\n"
    assert check(code, banned_functions=["sqrt"]) == []


@pytest.mark.parametrize(
    "code",
    ["y = x^0.5;", "y = x ^ 0.5;", "y = x^.5;", "y = x^(0.5);", "y = x ^ 5e-1;"],
)
def test_banned_operator_matches(code):
    issues = check("x = 4;\n" + code + "\n", banned_operators=["^0.5"])
    assert [i.rule for i in issues] == ["banned-operator"]
    assert issues[0].message == "This problem doesn't allow `^0.5`."


def test_banned_operator_variants():
    assert rules("x = 4;\ny = x.^0.5;\n", banned_operators=["^0.5"]) == []
    assert rules("x = 4;\ny = x.^0.5;\n", banned_operators=[".^0.5"]) == ["banned-operator"]
    assert rules("x = 4;\ny = x^(1/2);\n", banned_operators=["^(1/2)"]) == ["banned-operator"]
    assert rules("x = 4;\ny = x ^ ( 1 / 2 );\n", banned_operators=["^ (1/2)"]) == ["banned-operator"]
    assert rules("x = 4;\ny = x^2;\n", banned_operators=["^0.5", "^(1/2)"]) == []
    assert rules("x = 4;\ny = '^0.5';\n", banned_operators=["^0.5"]) == []


def test_banned_operator_position():
    [issue] = check("x = 4;\ny = x ^ (1/2);\n", banned_operators=["^(1/2)"])
    assert (issue.line, issue.col, issue.end_line, issue.end_col) == (2, 7, 2, 14)


# ---------------------------------------------------------------- names
def test_extra_allowed():
    code = "yq = myLinInterp([0 1], [0 2], 0.5);\n"
    assert rules(code) == ["unknown-function"]
    assert check(code, extra_allowed=["myLinInterp"]) == []


def test_unknown_function_message():
    [issue] = check("y = foo(3);\n")
    assert issue.message == (
        "`foo` isn't a MATLAB function (it may only exist in Octave). "
        "If it is a real MATLAB function, ask Claude to add it to the list."
    )


def test_names_never_checked_in_strings_comments_fields_or_commands():
    code = "% foo(1)\ns.foo = 1;\nt = s.foo;\nm = 'foo(2)';\nhold on\nformat long\nclear foo\n"
    assert check(code) == []


def test_assignments_are_known():
    code = (
        "[a, ~, b] = deal(1, 2, 3);\n"
        "for k = 1:3, end\n"
        "c(2).d{3} = 4;\n"
        "global G\n"
        "try, error('x'); catch err, disp(err.message); end\n"
        "f = @(u, v) u + v;\n"
        "disp(a + b + k + G + f(1, 2) + c(2).d{3})\n"
    )
    assert check(code) == []


def test_variable_shadowing_octave_name_is_fine():
    code = "rows = 3;\ncolumns = 4;\ne = exp(1);\nA = zeros(rows, columns) + e;\n"
    assert check(code) == []


def test_dotted_names():
    assert check("m = containers.Map();\nn = matlab.lang.makeValidName('a b');\n") == []
    assert rules("x = py.list();\n") == ["unsupported-feature"]


def test_function_list_contents():
    plain, dotted = matlab_names()
    for name in (
        "zeros ones linspace sum cumsum prod cumprod mean max min abs sqrt exp log log10 sin cos tan "
        "factorial mod rem floor ceil round fix numel length size find any all sort fprintf disp "
        "num2str sprintf plot hold xlabel ylabel title legend grid axis figure subplot polyfit polyval "
        "interp1 inv det linsolve pinv mldivide norm trapz diff isempty isnan error warning fliplr "
        "flipud repmat reshape meshgrid tic toc rand randn randi pi eps Inf inf NaN nan true false i j "
        "nargin nargout varargin varargout ans"
    ).split():
        assert name in plain, name
    assert not set(OCTAVE_FUNCTIONS) & plain
    assert "containers.Map" in dotted["containers"]
    assert len(plain) > 2000


# ---------------------------------------------------------------- profiles
def test_authoring_profile_allows_mp_helpers_and_unsafe():
    code = (
        "function cases = tests()\n"
        "  cases = {};\n"
        "  cases{end+1} = mp_case('one', {1}, {2});\n"
        "  f = str2func('myFun');\n"
        "  cases{end+1} = mp_check('custom', @(r) deal(true, ''));\n"
        "end\n"
    )
    assert check(code, profile="authoring") == []
    student = rules(code)
    assert "unsafe" in student and "unknown-function" in student


def test_authoring_profile_keeps_syntax_rules():
    code = "function cases = tests()\n  cases = {};\n  printf('x');\n  n = 1; n += 1;\nendfunction\n"
    assert set(rules(code, profile="authoring")) == {"octave-function", "octave-syntax"}


def test_shell_escape_in_authoring_is_still_flagged():
    assert rules("!echo hi\n", profile="authoring") == ["octave-syntax"]
    assert rules("!echo hi\n") == ["unsafe"]


# ---------------------------------------------------------------- tokenizer
def kinds(code):
    toks, _ = tokenize(code)
    return [(t.kind, t.text) for t in toks if t.kind not in ("NEWLINE",)]


def test_tokenizer_transpose_vs_string():
    assert kinds("a'") == [("NAME", "a"), ("OP", "'")]
    assert kinds("x = 'a'") == [("NAME", "x"), ("OP", "="), ("STR", "'a'")]
    assert kinds("[a 'b']") == [("OP", "["), ("NAME", "a"), ("STR", "'b'"), ("OP", "]")]
    assert kinds("[a' b']") == [("OP", "["), ("NAME", "a"), ("OP", "'"), ("NAME", "b"), ("OP", "'"), ("OP", "]")]
    assert kinds("x(end)'")[-1] == ("OP", "'")
    assert kinds("y = 'it''s'")[-1] == ("STR", "'it''s'")
    assert kinds("z = a.'")[-1] == ("OP", ".'")


def test_tokenizer_numbers():
    nums = [t for k, t in kinds("a = [1e-3 2.5E+4 .5 3i 1.*2 2.^x 0x1F];") if k == "NUMBER"]
    assert nums == ["1e-3", "2.5E+4", ".5", "3i", "1", "2", "2", "0x1F"]


def test_tokenizer_command_syntax():
    assert kinds("hold on") == [("NAME", "hold"), ("CMDWORD", "on")]
    assert kinds("format long g;") == [("NAME", "format"), ("CMDWORD", "long"), ("CMDWORD", "g"), ("OP", ";")]
    assert kinds("disp 'hi there'") == [("NAME", "disp"), ("CMDWORD", "'hi there'")]
    # expressions, not commands
    assert ("OP", "-") in kinds("a - b")
    assert ("OP", "=") in kinds("x = 3")
    assert ("OP", "(") in kinds("plot (x, y)")
    toks, _ = tokenize("x -1", known_vars={"x"})
    assert [t.kind for t in toks if t.kind != "NEWLINE"] == ["NAME", "OP", "NUMBER"]


def test_tokenizer_comments_and_continuation():
    toks, issues = tokenize("x = 1 + ... comment\n  2; % c\n%{\nblock\n%}\n")
    assert issues == []
    assert [t.kind for t in toks].count("NEWLINE") == 1
    assert [t.text for t in toks if t.kind == "NUMBER"] == ["1", "2"]


# ---------------------------------------------------------------- CLI
def test_cli_text_output(tmp_path, capsys):
    f = tmp_path / "solution.m"
    f.write_text("x = 1;\nx += 1;\n", encoding="utf-8")
    assert cli_main([str(f)]) == 1
    out = capsys.readouterr().out.strip()
    assert out == f"{f}:2:3: octave-syntax: `+=` doesn't work in MATLAB. Write `x = x + 1`."


def test_cli_clean_file(tmp_path, capsys):
    f = tmp_path / "ok.m"
    f.write_text("x = 1;\ndisp(x)\n", encoding="utf-8")
    assert cli_main([str(f)]) == 0
    assert capsys.readouterr().out == ""


def test_cli_options_and_json(tmp_path, capsys):
    f = tmp_path / "tests.m"
    f.write_text("y = myFun(4)^0.5;\nz = interp1([0 1], [0 1], 0.5);\nc = mp_case('a', {1}, {2});\n", encoding="utf-8")
    code = cli_main(
        [str(f), "--profile", "authoring", "--ban", "interp1", "--ban-op", "^0.5", "--allow", "myFun", "--json"]
    )
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert sorted(d["rule"] for d in data) == ["banned-function", "banned-operator"]
    assert set(data[0]) == {"line", "col", "end_line", "end_col", "rule", "severity", "message"}


def test_cli_missing_file(tmp_path):
    assert cli_main([str(tmp_path / "nope.m")]) == 2


# ---------------------------------------------------------------- function name vs file
def test_function_name_warning():
    code = "function y = myF(x)\n  y = x;\nend\n"
    [issue] = check(code, filename="cosInterp.m")
    assert (issue.rule, issue.severity) == ("function-name", "warning")
    assert "`cosInterp`" in issue.message
    assert check(code, filename="myF.m") == []
    assert check(code) == []  # default solution.m: no file name to compare with
    assert check("x = 1;\n", filename="cosInterp.m") == []  # scripts are not checked


def test_warning_alone_does_not_fail_cli(tmp_path, capsys):
    f = tmp_path / "other.m"
    f.write_text("function y = myF(x)\n  y = x;\nend\n", encoding="utf-8")
    assert cli_main([str(f)]) == 0
    assert "function-name" in capsys.readouterr().out


def test_octave_block_markers_inside_matlab_block_comment_are_text():
    assert check("%{\n#{\n# notes\n#}\n%}\nx = 1;\n") == []
    assert [i.rule for i in check("#{\nnotes\n#}\nx = 1;\n")] == ["octave-syntax", "octave-syntax"]


def test_unterminated_paren_does_not_cascade():
    issues = check("y = max(3,\n4);\nz = y + 1;\nw = z;\n")
    assert [i.rule for i in issues] == ["octave-syntax"]
