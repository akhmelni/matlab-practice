# HTTP API (server ↔ web page)

Server: `matlab_practice.server`, stdlib `ThreadingHTTPServer` on `127.0.0.1:8770`.
Static files: `web/` served at `/` (`/index.html`, `/app.js`, `/style.css`, `/vendor/...`).
All JSON. Problem ids match `^[a-z0-9]+(-[a-z0-9]+)*$`.

## Problems

`GET /api/problems`
```json
[{"id": "ex-01-mylininterp", "set": "examples", "number": 1, "title": "...", "kind": "function",
  "status": "new|attempted|solved", "fails": 0, "example": true}]
```
Sorted by set, then number.

`GET /api/problems/<id>`
```json
{"id": "...", "set": "...", "number": 1, "title": "...", "kind": "function|value|plot",
 "statement_md": "verbatim question (markdown with $math$)",
 "submit_md": "how to submit (markdown)",
 "source_url": "/api/problems/<id>/source" | null,
 "context": [{"id": "...", "title": "...", "statement_md": "..."}],
 "file": "myLinInterp.m",
 "code": "current contents of the student's file",
 "scratch": "current scratch.m contents" | null,
 "fails": 3, "hint_threshold": 5,
 "submissions": [<submission summary>, ...]}
```
`scratch` is null for value/plot problems (Run runs `solution.m` itself).

`GET /api/problems/<id>/source` → the image bytes.

## Editing

`POST /api/problems/<id>/save` `{"code": "...", "scratch": "..."|null}` → `{"ok": true}`

`POST /api/problems/<id>/check` `{"code": "...", "file": "myLinInterp.m" | "scratch.m"}` →
```json
{"issues": [{"line": 3, "col": 5, "end_line": 3, "end_col": 7, "rule": "octave-op",
             "severity": "error", "message": "`+=` doesn't work in MATLAB. Write `x = x + 1`."}]}
```
Lines and columns are 1-based; `end_col` is exclusive. Used for live underlines while typing.

## Run

`POST /api/problems/<id>/run` `{"code": "...", "scratch": "..."|null}` → saves, then
```json
{"blocked": false, "issues": [], "stdout": "...", "stderr": "...", "error": null | "message",
 "figures": ["/api/figures/<token>/1.png"], "timed_out": false, "seconds": 0.9}
```
If the checker finds errors in the code (or scratch), `blocked` is true, `issues` lists them
(each issue also has `"file": "myLinInterp.m" | "scratch.m"`), and nothing runs.

## Submit

`POST /api/problems/<id>/submit` `{"code": "...", "scratch": "..."|null}` → saves, then returns the
new submission (full form, below) as soon as the Octave tests finish. The Claude review then runs in
the background; poll `GET /api/problems/<id>/submissions/<sid>` every 2 s while
`review.status == "pending"`.

Submission (full):
```json
{"id": "20261119-140501", "time": "2026-11-19T14:05:01", "code": "...",
 "verdict": "pending|accepted|wrong|error|timeout|blocked|flagged",
 "tests_verdict": "accepted|wrong|error|timeout|blocked",
 "passed": 3, "total": 4,
 "issues": [ ...checker issues, when blocked... ],
 "cases": [{"name": "...", "status": "passed|failed|error",
            "message": "expected size 1x4, got 4x1" ,
            "input": "x = [0;1;2;4], y = ..., X = 0.5" | null,
            "expected": "5" | null, "actual": "4.5" | null}],
 "error": null | "error text when nothing could run (syntax error, ...)",
 "stdout": "...",
 "figures": ["/api/figures/<token>/1.png"],
 "review": {"status": "pending|done|unavailable|skipped",
            "matlab_ok": true, "gaming": false, "rules_ok": true,
            "summary": "one line", "notes": ["..."]},
 "hint": null | {"level": 1, "text": "markdown"},
 "fails_after": 5}
```
- `verdict` is `pending` while the review runs and the tests passed; final verdict is
  `accepted` (tests pass + review clean, or review unavailable), `flagged` (tests pass, review not clean),
  or the tests verdict otherwise.
- `hint` appears only when `fails_after >= 5` and the verdict is not accepted.
  Levels: 1 = failure 5, 2 = failures 6-7, 3 = failures 8+.
- `review.status == "unavailable"` → show "not reviewed" (Claude Code missing, not signed in, offline).

Submission summary (in lists): same without `code`, `cases`, `stdout`.

`GET /api/problems/<id>/submissions/<sid>` → full submission.

`GET /api/figures/<token>/<n>.png` → figure image.

## Status

`GET /api/status` → `{"octave": {"found": true, "path": "...", "version": "9.2.0"},
"claude": {"found": true}, "work_dir": "..."}` (shown in a small footer / warning banner).
