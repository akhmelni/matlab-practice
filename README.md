# MATLAB Practice

A local practice app for learning MATLAB, LeetCode-style, built around your own homework.

- **Problems come from your homework, word for word.** Give Claude Code a screenshot or PDF page and
  type `/new-problem`: it copies each question exactly, writes tests, and proves them before saving.
- **Your code runs in GNU Octave** (free), but the app **only accepts MATLAB**: anything that works in
  Octave but not in MATLAB is blocked with the MATLAB way to write it, and errors are shown in
  MATLAB's wording.
- **Every submission is graded and reviewed.** Octave runs the tests; Claude checks it's real MATLAB,
  isn't gaming the tests, and follows the problem's rules.
- **Hints start after 5 failed submissions** on a problem, and get more specific each time. Claude never
  writes the solution for you.

## Daily use

| | Windows | Mac |
| --- | --- | --- |
| Start the app | double-click `start.bat` | `./start.sh` |
| Add problems | see [Adding problems from your homework](#adding-problems-from-your-homework) | same |
| Update the tool | `git pull` then `uv sync` | same |

The app opens at http://127.0.0.1:8770.

- **Run** (Ctrl+' / ⌘'): runs your code (`scratch.m` for function problems) and shows the output and plots.
- **Submit** (Ctrl+Enter / ⌘↵): checks, grades and reviews it, and saves it to your history.
- Problems you made live in `my-work/` (never touched by updates).

## Adding problems from your homework

You don't write problems yourself: Claude Code turns your homework into practice problems, with the
questions copied **word for word** and tests that check your answers.

1. **Take a clear screenshot** (or export the PDF page) of the homework. One sheet at a time works best.
   Make sure nothing is cut off at the edges.
2. **Open this folder in Claude Code**: in the Claude desktop app, open the **Code** tab and choose the
   `matlab-practice` folder, or run `claude` in a terminal inside the folder.
3. **Attach the screenshot** (drag it in, or paste it) and type:

   ```text
   /new-problem This is hw3. Make all of them.
   ```

   Say what the sheet is called (`hw3`, `quiz2`...) so the problems are grouped and numbered the same
   way as your homework. You can also ask for only some: "just problems 2, 5 and 7".
4. **Answer its questions.** If part of a question is unreadable or cut off, Claude stops and asks you
   instead of guessing. Send a better screenshot or type the missing part.
5. **Wait a few minutes.** For every question Claude writes tests, checks them in Octave against its own
   hidden solution, then deletes that solution. It tells you which problems are ready.
6. **Open the app** (or reload the page). The new problems appear under the sheet's name.
7. **Check each question against the original**: click **Show original** above the question. If the
   text doesn't match the sheet, tell Claude ("hw3 problem 4 has the wrong number in the matrix").

Good to know:

- Claude won't tell you how to solve a problem or what the answer is. Ask it for help on a problem and
  you get nothing specific until you've failed that problem **5 times** in the app, then hints that
  get more specific each time.
- Some problems can't be fully checked automatically (for example "plot this" or "explain what
  happens"). Claude tells you which ones; for those, look at your plot or output yourself.
- If a problem seems graded unfairly (you're sure your answer is right), tell Claude which problem
  and why, and ask it to check the tests.

## Install

See [INSTALL.md](INSTALL.md) (Windows and Mac). An agent can follow it on its own.

## For maintainers

| Path | What it is |
| --- | --- |
| `src/matlab_practice/` | server, Octave engine, grading, Claude review, `validate`, `check-setup` |
| `src/matlab_practice/checker/` | the MATLAB-compatibility checker (`uv run mcheck file.m`) |
| `matlab/` | the `.m` test runner every problem uses (`mp_case`, `mp_value`, `mp_check`) |
| `web/` | the page (CodeMirror, KaTeX and marked vendored in `web/vendor/`) |
| `prompts/` | Claude's review and hint instructions |
| `docs/authoring.md`, `docs/problem-format.md` | how problems are written (also what Claude follows) |
| `examples/` | three hand-made problems; their references are in `tests/references/` |

```bash
uv run pytest            # tests (needs Octave)
uv run validate --all    # prove every problem against its reference
uv run check-setup       # what the install guide runs
```

Settings go in a `.env` file in the repo root: `OCTAVE`, `OCTAVE_GUI`, `CLAUDE`, `CLAUDE_MODEL`,
`PORT`, `MP_WORK_DIR`, `QT_QPA_PLATFORM`.
