---
name: new-problem
description: Turn homework (an image, PDF page or pasted text) into verbatim, validated practice problems for the MATLAB practice app. Use when the student shares homework problems or asks to add/create a new problem.
---

# New problem from homework

Follow `docs/authoring.md` (rules) and `docs/problem-format.md` (files). Read both first, every time.

## Steps

1. **Get the material.** The student attaches a screenshot / PDF page or pastes text. If he didn't,
   ask for it. Ask what the homework set is called if it isn't obvious (`hw3`, `quiz2`...).
2. **Split it** into one problem per numbered question. Ask which ones he wants if there are many
   (default: all). Skip sheet-wide instructions.
3. **Transcribe each question verbatim** into `problem.md` (LaTeX math, code font in backticks).
   If anything is unreadable or cut off, STOP and ask him for the missing part. Never guess.
   Read your transcription back against the image once more, character by character for numbers.
4. **Decide kind and interface** (table in authoring.md). Write `problem.json` (id
   `<set>-<NN>-<slug>`, link "previous problem" references in `context`, bans from the question's own
   rules), `submit.md` (mechanics only), `starter.m`, `scratch.m` (function problems).
   Copy the image into the folder as `source.png` / `source.jpg` and set `"source"`.
5. **Write a reference solution** in a temporary folder OUTSIDE the repo (e.g. the system temp dir).
   It must be valid MATLAB and obey the problem's bans.
6. **Write `tests.m`:** hand-picked edge cases, then random cases generated with the reference in a
   throwaway Octave script (`octave-cli --norc --quiet --eval "..."`), pasted as literals. Accept every
   reasonable reading of an ambiguous question with `'alts'`.
7. **Prove it:** `uv run validate <id> --reference <temp path>`. Fix and repeat until it prints `VALID`.
8. **Delete the reference** and any throwaway scripts.
9. **Tell him** which problems are ready (ids and titles) and to open the app (`start.bat` / `./start.sh`).
   Do not describe the method, the reference, or any expected answer. Mention which problems are
   self-checked (plots) if any.
