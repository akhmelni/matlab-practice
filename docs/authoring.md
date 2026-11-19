# Authoring guide: turning homework into practice problems

This is the source of truth for any LLM (or person) creating problems for this app.
The folder format is in [problem-format.md](problem-format.md). Read both before writing anything.

## The four hard rules

1. **The question is verbatim.** Copy the problem text exactly as it appears in the homework: same words,
   same symbols, same numbers, same order. Do not rephrase, simplify, clarify, fix grammar, add hints,
   or add examples. Working out what the question means is part of the student's exercise.
   - Math goes in LaTeX (`$...$` inline, `$$...$$` display; matrices with `\begin{pmatrix}`).
   - Text shown in a code font in the homework (like `x = [1.3, 3.4, 2.8, 9.2]`) goes in backticks.
   - Leave out the problem's number (it goes in `problem.json`) and instructions that apply to the whole
     sheet ("Write MATLAB code for one of the problems below...").
   - If any part is unreadable, cut off, or ambiguous to *read* (not to interpret): **stop and ask the
     student** to send a clearer image or the missing text. Never guess a number or a word.
2. **No Octave-only habits.** The student runs Octave but must only ever see MATLAB. Every `.m` file you
   write (starter, scratch, tests, and your reference) must pass the checker (`uv run mcheck FILE.m`).
   Use single-quoted strings, `%` comments, `~=`, `end`, `fprintf`/`disp`.
3. **Never hand over the work.** The student never sees your reference solution, your approach, or the
   expected answer of a "value" problem. Do not explain the method when you finish. Write the reference
   to a temporary file *outside the repo* and delete it after validating.
4. **A wrong grader is worse than none.** A problem only counts when `uv run validate <id> --reference
   <file>` passes: the reference passes every test and the untouched starter fails.

## Choosing the kind and the interface

| The question asks to... | kind | student writes | `submit.md` says |
| --- | --- | --- | --- |
| "write a function" (with or without a header) | `function` | `<name>.m` | the exact header to use |
| find / compute / report / display a value ("display on the screen the integer i...", "find x for which...") | `value` | script `solution.m` | which variable(s) to store results in |
| plot something | `plot` | script `solution.m` | which variables to store (if any are checked), and that the plot is checked by eye |
| explain what happens | `value` or `plot` with checkable numbers if any, otherwise `plot` with no cases (self-checked) | `solution.m` | what to store |

- If the homework gives a function header, use it exactly (name, argument names, order).
- If it doesn't, pick a neutral name that doesn't hint at the method, e.g. `taylorExp(x, n)`, and
  name the arguments after the symbols in the question.
- `submit.md` is **mechanics only**: file name, header, variable names, "Run uses scratch.m".
  Nothing about how to solve it, what the answer looks like, or which built-in functions to use.
- Problems that say "display on the screen" still store the value in a variable so it can be graded;
  printing it as well is fine.
- Multi-answer questions ("use three built-in operations to find x") → one variable per answer, e.g.
  `x1`, `x2`, `x3`, plus an `mp_check` that the three were computed differently if the question
  requires that (judge from the student's code is not possible in tests; the Claude review checks the
  problem's own rules).

## Rules from the question

Turn explicit prohibitions in the question into bans in `problem.json`:
- "You may not use interp1" → `"banned_functions": ["interp1"]` (add close relatives that would make the
  problem trivial: `interp2`, `interpn`, `griddedInterpolant`, `spline`, `pchip`, `makima`).
- "Do not use the built-in SQRT function, or similar" → `["sqrt", "nthroot", "realsqrt", "hypot"]`
  and `"banned_operators": ["^0.5", ".^0.5", "^(1/2)", ".^(1/2)", "^.5", ".^.5"]`.
Do not ban things the question doesn't forbid.

## Ambiguous questions

Do not clarify them in the text. Make the tests accept every reasonable reading with `'alts'`:
- "computes the first n terms of the Taylor series" → accept the sum of the n terms **or** the vector of
  the n terms (`'alts', {{vector}}`). If "n terms" could include or exclude the constant term, accept both.
- "Use the function from the previous problem" → add the earlier problem's id to `context`.
- Grid-search questions ("scan 10,000 values of x between 0 and 1") → use a tolerance that accepts the
  common grids (`linspace(0,1,10000)` and `0:1e-4:1`), e.g. `'tol', 2e-4`.
- "Reported with three significant digits" → `'sigfigs', 3`.
When a reading is clearly wrong, don't accept it.

## Writing good tests

- **Hand-picked cases first:** the examples from the question, then the edge cases where students
  usually fail: first and last elements, a single element, row vs column input (output must keep the
  shape the question asks for), negative numbers, zero, exact data points, the boundary of a loop
  condition (off-by-one), large n.
- **Random cases second (5-10):** generate them with a throwaway Octave script that uses your reference
  (or a trusted built-in, e.g. `interp1` even if the student may not), and paste the results into
  `tests.m` as literals with `mat2str(v, 15)`. `tests.m` itself must never call `rand`.
- **Tolerances:** default `1e-9` relative. Use looser ones only where the question allows approximations.
- **Value problems:** `mp_value` cases are hidden automatically. Never put the expected value in
  `submit.md`, the title, or anywhere the student can see.
- **Custom checks** (`mp_check`) need a local function in `tests.m` returning `[ok, msg]`
  (anonymous functions can't return two outputs). `info.vars`, `info.nfigures`, `info.fn` are available.
- Give every case a short, readable name: it is shown to the student ("column in, column out").
- Check yourself: does each case test something the question actually requires?

## Files to write

For each problem `my-work/problems/<id>/`:
1. `problem.json` (id `<set>-<NN>-<slug>`; ask the student what to call the set, e.g. `hw3`, if unknown).
2. `problem.md`: the verbatim question.
3. `submit.md`: mechanics only.
4. `source.png` (or `.jpg`): a copy of the image the student gave you (crop not required).
5. `starter.m`: function problems: the header line, a blank line, `end`. Script problems: `% Write your script here.`
6. `scratch.m` (function problems): a few lines that call the function on the question's example
   inputs, e.g. `Y = myLinInterp([0;1;2;4], [0;10;0;20], [0.5 3])`. Do not print expected outputs.
7. `tests.m`.

## Proving it

```bash
uv run mcheck my-work/problems/<id>/tests.m --profile authoring
uv run validate <id> --reference /path/outside/repo/reference.m
```

Fix and repeat until `validate` prints `VALID`. Then delete the reference file. If after several honest
attempts the problem can't be validated (e.g. it can't be graded automatically), make it a `plot`-kind,
self-checked problem with no cases and tell the student it is self-checked.
