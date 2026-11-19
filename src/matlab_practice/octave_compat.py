"""Make valid MATLAB run in Octave where the two differ, without the student noticing.

MATLAB requires local functions in a script to be at the END of the file. Octave only knows a
function once the line defining it has run, so `x = g(3)` at the top fails with "'g' undefined".
Before running a script we move each local function into its own file `<name>.m`, padded with
blank lines so its line numbers match the original script, and blank those lines in the script.
"""

from __future__ import annotations

import re

from .checker.tokenizer import tokenize

_OPENERS = {"function", "if", "for", "parfor", "while", "switch", "try", "spmd"}
_NAME_RE = re.compile(r"^\s*function\s+(?:\[[^\]]*\]\s*=\s*|[A-Za-z]\w*\s*=\s*)?([A-Za-z]\w*)")


def _blocks(code: str) -> list[tuple[str, int, int]]:
    """Top-level function blocks closed by `end`: (name, first line, last line)."""
    try:
        tokens, _ = tokenize(code)
    except Exception:
        return []
    lines = code.splitlines()
    found: list[tuple[str, int, int]] = []
    stack: list[tuple[str, int]] = []
    for tok in tokens:
        if tok.kind != "KEYWORD" or tok.depth != 0:
            continue
        if tok.text in _OPENERS:
            stack.append((tok.text, tok.line))
        elif tok.text == "end" and stack:
            kind, start = stack.pop()
            if kind == "function" and not stack and start - 1 < len(lines):
                m = _NAME_RE.match(lines[start - 1])
                if m:
                    found.append((m.group(1), start, tok.end_line))
    return found


def split_local_functions(code: str, taken: set[str] = frozenset()) -> tuple[str, list[tuple[str, str]]]:
    """Return (script with moved function lines blanked, [(file name, function file text)]).

    Functions whose file name is in `taken` stay where they are."""
    lines = code.splitlines()
    moved: list[tuple[str, str]] = []
    blanked: set[int] = set()
    for name, start, end in _blocks(code):
        target = f"{name}.m"
        if target in taken or any(t == target for t, _ in moved):
            continue
        body = "\n" * (start - 1) + "\n".join(lines[start - 1:end]) + "\n"
        moved.append((target, body))
        blanked.update(range(start, end + 1))
    if not moved:
        return code, []
    script = "\n".join("" if i in blanked else line for i, line in enumerate(lines, start=1)) + "\n"
    return script, moved


def prepare_files(files: dict[str, str], scripts: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Split local functions out of the given script files.

    Returns (files to write, {generated file name: script file it came from}) so error messages
    that mention a generated file can be pointed back at the student's script.
    """
    out = dict(files)
    origin: dict[str, str] = {}
    for name in sorted(scripts):
        if name not in out:
            continue
        script, moved = split_local_functions(out[name], taken=set(out) | set(origin))
        if not moved:
            continue
        out[name] = script
        for target, body in moved:
            out[target] = body
            origin[target] = name
    return out, origin
