# Problem format

Every problem is one folder. Hand-made examples live in `examples/<id>/` (tracked by git).
Problems made from homework live in `my-work/problems/<id>/` (ignored by git).

The student's own files never go into a problem folder. They live in
`my-work/solutions/<id>/`, and submissions in `my-work/submissions/<id>/`.

## Folder contents

```
<id>/
  problem.json   metadata (below)
  problem.md     the question, VERBATIM from the homework (Markdown, math as $...$ / $$...$$)
  submit.md      "How to submit": mechanics only (file name, header, answer variables)
  source.png     the original screenshot / PDF crop (or .jpg); optional for hand-made examples
  starter.m      what the student's file starts as
  scratch.m      (function problems only) starter for the Run button's try-it script
  tests.m        the evaluator: function cases = tests()
```

## id

`<set>-<NN>-<slug>`: lowercase letters, digits and dashes, e.g. `hw3-08-cos-interp`.
`set` groups problems in the app (homework sheet name), `NN` is the problem number, zero-padded.

## problem.json

```json
{
  "id": "hw3-08-cos-interp",
  "set": "hw3",
  "number": 8,
  "title": "Linear interpolation of cos",
  "kind": "function",
  "file": "cosInterp.m",
  "function": {"name": "cosInterp", "inputs": ["x"], "outputs": ["y"]},
  "answers": [],
  "banned_functions": ["interp1"],
  "banned_operators": [],
  "context": ["hw3-07-sum-cos-cubes"],
  "source": "source.png",
  "timeout_s": 30
}
```

| field | required | meaning |
| --- | --- | --- |
| `id` | yes | must equal the folder name |
| `set`, `number` | yes | grouping and order in the app |
| `title` | yes | short neutral label for the problem list (NOT a rewording of the question) |
| `kind` | yes | `function`, `value` or `plot` |
| `file` | yes | the student's file name. Function problems: `<function name>.m`. Script problems: `solution.m` |
| `function` | function kind | `name`, `inputs`, `outputs` (argument names, in order) |
| `answers` | value kind | variable names the script must set, e.g. `["answer"]` or `["x1","x2","x3"]` |
| `banned_functions` | no | names the student may not call (`interp1`, `sqrt`, ...) |
| `banned_operators` | no | operator spellings the student may not use, e.g. `"^0.5"`, `".^0.5"`, `"^(1/2)"` (whitespace ignored) |
| `context` | no | ids of problems this one refers to ("the previous problem") |
| `source` | no | image file name in the folder |
| `timeout_s` | no | Submit time limit, default 30 |

## The three kinds

- **function**: the student writes a function in `<name>.m`. `tests.m` calls it with inputs and compares outputs.
- **value**: the student writes a script `solution.m` that stores results in the variables named in `answers`.
  The app never shows the expected value: only correct / incorrect.
- **plot**: the student writes a script `solution.m` that draws (and maybe prints). Figures are saved and shown.
  `tests.m` may check variables; if it returns no cases the problem is self-checked.

## tests.m

`tests.m` is a MATLAB function file with no inputs that returns a cell array of cases built with the
helpers in `matlab/` (they are on the path when tests run):

```matlab
function cases = tests()
  x = [0; 1; 2; 4];
  y = [0; 10; 0; 20];
  cases = {};
  cases{end+1} = mp_case('single point', {x, y, 0.5}, {5});
  cases{end+1} = mp_case('exact data points, row', {x, y, [0 1 2 4]}, {[0 10 0 20]});
  cases{end+1} = mp_case('column in, column out', {x, y, [1.5; 3]}, {[5; 10]}, 'tol', 1e-9);
  % ambiguous question: accept either reading
  cases{end+1} = mp_case('first 3 terms', {1, 3}, {-1.5}, 'alts', {{[1 -5 12.5]}});
end
```

- `mp_case(name, args, expected, ...)`: function problems. `args` = cell of inputs, `expected` = cell of
  expected outputs (one per output argument checked; the function is called with that many outputs).
- `mp_value(name, varname, expected, ...)`: value / plot problems. Checks the variable `varname` set by `solution.m`.
- `mp_check(name, @localFn)`: a custom check. `localFn` is a local function in `tests.m` (anonymous
  functions can't return two outputs) that gets a struct with `.fn` (handle to the student's function,
  function problems), `.vars` (the script's variables, script problems) and `.nfigures`, and returns
  `[ok, message]`.

Options (name/value pairs) for `mp_case` / `mp_value`:

| option | default | meaning |
| --- | --- | --- |
| `'tol'` | `1e-9` | allowed error: abs(actual-expected) <= tol * max(1, abs(expected)) |
| `'sigfigs'` | none | instead of `tol`: equal when rounded to N significant figures |
| `'alts'` | `{}` | cell of alternative `expected` cells, any one of which also passes |
| `'hidden'` | false for function, true for value | never show expected value (or inputs) to the student |
| `'size_only'` | false | only the size must match |

Comparison rules: sizes must match exactly; numbers and logicals compare as doubles within tolerance;
NaN equals NaN; Inf equals Inf of the same sign; char compares exactly; cells and structs recursively.

Random cases: generate them while authoring, then write the inputs and expected outputs into `tests.m`
as literal numbers with full precision (`sprintf('%.17g', v)`). `tests.m` must not call `rand`.

Every `.m` file here (starter, scratch, tests) must pass the MATLAB-compatibility checker.
