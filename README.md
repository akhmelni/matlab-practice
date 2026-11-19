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
| Add problems | open the folder in Claude Code, attach the homework, type `/new-problem` | same |
| Update the tool | `git pull` then `uv sync` | same |

The app opens at http://127.0.0.1:8770.

- **Run** (Ctrl+' / ⌘'): runs your code (`scratch.m` for function problems) and shows the output and plots.
- **Submit** (Ctrl+Enter / ⌘↵): checks, grades and reviews it, and saves it to your history.
- Problems you made live in `my-work/` (never touched by updates).

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
