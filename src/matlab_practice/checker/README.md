# MATLAB-compatibility checker

The student's code runs in GNU Octave, which accepts a lot that MATLAB rejects. This checker is the
safety net: it blocks Octave-only habits, unsafe or grader-dodging calls, and anything a problem bans,
while never flagging ordinary MATLAB. Messages are short and always say the MATLAB way to write it.

```python
from matlab_practice.checker import check, Issue
issues = check(code, filename="cosInterp.m", profile="student",
               banned_functions=["interp1"], banned_operators=["^0.5"], extra_allowed=["myFun"])
```

```
mcheck FILE.m [--profile authoring] [--ban NAME ...] [--ban-op OP ...] [--allow NAME ...] [--json]
```
prints `file:line:col: rule: message` and exits 1 if there is any error.

`Issue` has `line, col, end_line, end_col` (1-based, `end_col` exclusive), `rule`, `severity`
(`"error"` or `"warning"`), `message`, and `to_dict()`.

## Profiles

- `student` (default): every rule.
- `authoring`: for evaluator files (`tests.m`). Same syntax and function rules, but the `unsafe` rule is
  off and names starting with `mp_` (the helpers in `matlab/`) are allowed.

`extra_allowed` lists names defined in other files, e.g. the student's function when checking his
scratch script.

## Rules

| rule | severity | what it catches |
| --- | --- | --- |
| `octave-syntax` | error | `#` comments and `#{ #}` blocks, `!` and `!=`, `x++` / `x--` / `++x`, `+= -= *= /= ^= \|= &=`, `**` and `.**`, `endif endfor endwhile endfunction endswitch end_try_catch endparfor end_unwind_protect`, `unwind_protect`, `do ... until`, `\` line continuation, a line break inside `( )` without `...`, indexing a result directly (`f(x)(2)`, `f(x){1}`, `[1 2 3](2)`, `'abc'(1)`, `A'(1)`), chained `a = b = 3`, `if (x = 3)`, `global g = 1` |
| `octave-function` | error | Octave-only functions and constants (`printf`, `puts`, `fflush`, `columns`, `rows`, `e`, `NA`, ...) with the MATLAB replacement |
| `unknown-function` | error | a name used as a function or value that is not assigned in the file, not a function defined in the file, not in `extra_allowed`, and not in `matlab_functions.txt` |
| `unsupported-feature` | error | double-quoted strings, `classdef`, `arguments` blocks, `table`, `timetable`, `datetime`, `duration`, `categorical`, `dictionary`, `string`, `strings`, `py.` |
| `unsafe` | error | (student only) files, shell (`system`, `!`), `eval` family, `feval`, `str2func`, `input` and other waiting calls, `pause`, `exit`, internet, path changes, other languages |
| `script-local-functions` | error | in a script, code after a local function, or a local function without `end`; in a function file, code outside any function |
| `banned-function` | error | a name in `banned_functions` (also `@name` and `cellfun('name', ...)`) |
| `banned-operator` | error | a spelling in `banned_operators`, matched on tokens ignoring whitespace; numbers compare by value (`^.5` = `^0.5`) and may be wrapped in `( )` |
| `function-name` | warning | a function file whose function name differs from the file name (not checked for `solution.m`) |

What is never checked: text in strings and comments, struct fields after `.`, command-syntax
arguments (`on` in `hold on`, `all` in `close all`), and `Name=value` argument names.

## How it works

`tokenizer.py` splits the code into tokens. It decides transpose vs. string for `'` (transpose after a
name, number, `)`, `]`, `}`, `'`, `.'`, or `end` inside indexing; but `[a 'text']` inside brackets is
a string), reads `%{ %}` block comments (markers alone on their line), `...` continuation, and command
syntax (`hold on`, `format long`). It runs twice: the first pass finds the variables so the second can
tell `x -1` (an expression, `x` is a variable) from `disp -1` (command syntax).
`rules.py` runs the rules over the tokens. `tables.py` has the name tables.

## Adding a function to the list

`matlab_functions.txt` is one name per line, built from MathWorks' official MATLAB function reference
(core MATLAB, no toolboxes) by `tools/build_function_list.py`; see its docstring for how to rebuild it.

- Missing a real MATLAB function: add it to `SUPPLEMENT` in `tools/build_function_list.py` and rebuild,
  or append it to `matlab_functions.txt` (keep a short `# reason` comment above it). Only add functions
  that exist in core MATLAB (not a toolbox) and that Octave also has, or the student's code won't run.
- An Octave-only name: add it to `OCTAVE_FUNCTIONS` in `tables.py` with the MATLAB replacement; the
  build script removes those names from the list.
- Add a test: a snippet in `tests/checker/valid/` (must pass) or `tests/checker/octave_only/` (first
  line `% expect: <rule>`), then run `uv run pytest tests/test_checker*.py`.
