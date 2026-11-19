"""A tokenizer for MATLAB source code that also notices Octave-only lexical habits.

Token kinds:

- ``NAME``      identifier (also Octave-only words like ``endif``; the rules decide)
- ``KEYWORD``   MATLAB keyword (``if``, ``end``, ``function`` ...)
- ``NUMBER``    numeric literal (``3``, ``1e-3``, ``.5``, ``2i``, ``0x1F``)
- ``STR``       single-quoted char vector, text includes the quotes
- ``DQSTR``     double-quoted string, text includes the quotes
- ``OP``        operator or punctuation (``+``, ``.^``, ``(``, ``;`` ...)
- ``CMDWORD``   argument of command syntax (``on`` in ``hold on``) or of a ``!`` shell escape
- ``NEWLINE``   end of a line (not emitted after ``...`` continuation)
- ``COMMENT``   ``%`` or ``#`` comment (``...`` continuation text included)
- ``BAD``       a character MATLAB doesn't understand

The tokenizer also returns lexical issues (``#`` comments, ``#{`` blocks, ``\\`` line continuation,
line breaks inside ``( )``) because those are easiest to see while scanning characters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .issue import Issue

KEYWORDS = frozenset(
    "break case catch classdef continue else elseif end for function global if otherwise "
    "parfor persistent return spmd switch try while".split()
)

# Keywords after which a new statement may start on the same line.
_STMT_AFTER_KEYWORDS = frozenset({"else", "try", "otherwise"})

_OPS3 = (".**",)
_OPS2 = ("**", ".^", ".*", "./", ".\\", ".'", "==", "~=", "!=", "<=", ">=", "&&", "||")
_OPS1 = frozenset("+-*/\\^<>&|~!=:@.?,;()[]{}")

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUM_RE = re.compile(
    r"(?:0[xX][0-9a-fA-F]+|0[bB][01]+)(?:[us](?:8|16|32|64))?"
    r"|(?:\d+(?:\.(?![*/\\^'])\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?(?:[ij](?![A-Za-z0-9_]))?"
)

_COMPOUND_RE = re.compile(r"(\.?\*\*|\.?[-+*/\\^|&])=(?!=)")

_VALUE_KINDS = frozenset({"NAME", "NUMBER", "STR", "DQSTR"})
_VALUE_OPS = frozenset({")", "]", "}", "'", ".'"})


@dataclass(slots=True)
class Token:
    kind: str
    text: str
    line: int
    col: int  # 1-based
    end_line: int
    end_col: int  # exclusive
    space_before: bool = False  # whitespace right before it on the same line
    depth: int = 0  # number of open brackets before this token
    bracket: str = ""  # innermost open bracket before this token, "" at top level
    stmt_start: bool = False  # first token of a statement
    shell: bool = False  # the ``!`` of a shell escape / its command text

    def is_op(self, *texts: str) -> bool:
        return self.kind == "OP" and self.text in texts

    def is_kw(self, *texts: str) -> bool:
        return self.kind == "KEYWORD" and self.text in texts


def _issue(line: int, col: int, end_col: int, message: str) -> Issue:
    return Issue(line, col, line, max(end_col, col + 1), "octave-syntax", "error", message)


def _is_value_end(tok: Token | None) -> bool:
    """Can a ``'`` right after this token be a transpose?"""
    if tok is None:
        return False
    if tok.kind in _VALUE_KINDS:
        return True
    if tok.kind == "OP" and tok.text in _VALUE_OPS:
        return True
    # ``end`` inside indexing: x(end)'
    return tok.kind == "KEYWORD" and tok.text == "end" and tok.depth > 0


def _match_op(s: str, i: int) -> str | None:
    for op in _OPS3:
        if s.startswith(op, i):
            return op
    for op in _OPS2:
        if s.startswith(op, i):
            return op
    if i < len(s) and s[i] in _OPS1:
        return s[i]
    return None


def _looks_like_command(line: str, i: int) -> bool:
    """Is the text from ``line[i:]`` (just after a statement-start name) command-syntax arguments?

    MATLAB's rule, simplified: name, whitespace, then something that is not ``=`` or ``(`` and not
    a binary operator followed by whitespace. ``hold on``, ``format long``, ``disp 'hi'``.
    """
    if i >= len(line) or line[i] not in " \t":
        return False
    rest = line[i:].lstrip(" \t")
    if not rest:
        return False
    ch = rest[0]
    if ch in ";,%#\"([{=.":
        return False
    if rest.startswith("..."):
        return False
    if ch == "'":
        return True
    if _COMPOUND_RE.match(rest):
        return False  # "x += 1": Octave compound assignment, reported by the rules
    if ch.isalnum() or ch == "_":
        return True
    op = _match_op(rest, 0)
    if op is None:
        return True
    after = rest[len(op):]
    # "a - b", "a == b": an expression. "a -b": command syntax (when a is not a variable).
    return bool(after) and after[0] not in " \t"


def _scan_quoted(line: str, i: int, quote: str) -> int:
    """Return the index just past the closing quote of a string starting at ``line[i]``.

    Doubled quotes are escapes. An unterminated string runs to the end of the line.
    """
    j = i + 1
    n = len(line)
    while j < n:
        if line[j] == quote:
            if j + 1 < n and line[j + 1] == quote:
                j += 2
                continue
            return j + 1
        j += 1
    return n


def tokenize(code: str, known_vars: frozenset[str] | set[str] = frozenset()) -> tuple[list[Token], list[Issue]]:
    """Split MATLAB code into tokens.

    ``known_vars`` are names assigned somewhere in the file: a statement starting with one of them is
    never command syntax (``x -1`` is an expression when ``x`` is a variable).
    """
    tokens: list[Token] = []
    issues: list[Issue] = []
    stack: list[str] = []  # open brackets
    lines = code.splitlines()

    block_depth = 0  # inside %{ ... %} (nestable)
    octave_block = False  # the outer block comment started with #{
    continuation = False  # previous line ended with ... (or Octave \)
    stmt_start = True
    prev: Token | None = None  # previous code token (not comments)

    def emit(kind: str, text: str, ln: int, c0: int, c1: int, space: bool, **kw) -> Token:
        nonlocal prev, stmt_start
        tok = Token(
            kind,
            text,
            ln,
            c0 + 1,
            ln,
            c1 + 1,
            space_before=space,
            depth=len(stack),
            bracket=stack[-1] if stack else "",
            stmt_start=stmt_start and kind not in ("COMMENT", "NEWLINE"),
            **kw,
        )
        tokens.append(tok)
        if kind != "COMMENT":
            prev = tok
            if kind != "NEWLINE":
                stmt_start = False
        return tok

    for ln, line in enumerate(lines, start=1):
        stripped = line.strip()

        # ---- block comments: %{ / %} (or Octave #{ / #}) alone on their line
        if block_depth:
            # Inside a %{ block only %{ / %} count (MATLAB); inside an Octave #{ block, #} closes too.
            closers = ("%}", "#}") if octave_block else ("%}",)
            openers = ("%{", "#{") if octave_block else ("%{",)
            if stripped in closers:
                block_depth -= 1
                if stripped == "#}":
                    c = line.index("#")
                    issues.append(_issue(ln, c + 1, c + 3, "Use `%}` to end a block comment in MATLAB, not `#}`."))
            elif stripped in openers:
                block_depth += 1
            continue
        if stripped in ("%{", "#{") and not stack:
            block_depth = 1
            octave_block = stripped == "#{"
            if stripped == "#{":
                c = line.index("#")
                issues.append(_issue(ln, c + 1, c + 3, "Use `%{ ... %}` for block comments in MATLAB, not `#{ ... #}`."))
            continue

        was_continuation = continuation
        continuation = False
        i = 0
        n = len(line)
        space = was_continuation  # a continued line acts like whitespace
        while i < n:
            ch = line[i]
            if ch in " \t\f\v":
                space = True
                i += 1
                continue

            # comments
            if ch == "%":
                emit("COMMENT", line[i:], ln, i, n, space)
                break
            if ch == "#":
                issues.append(_issue(ln, i + 1, i + 2, "Use `%` for comments in MATLAB, not `#`."))
                emit("COMMENT", line[i:], ln, i, n, space)
                break
            if line.startswith("...", i):
                continuation = True
                emit("COMMENT", line[i:], ln, i, n, space)
                break

            # Octave backslash continuation: "\" with nothing (or only a comment) after it
            if ch == "\\":
                tail = line[i + 1:].strip()
                if tail == "" or tail.startswith(("%", "#")):
                    issues.append(_issue(ln, i + 1, i + 2, "Use `...` to continue a line in MATLAB, not `\\`."))
                    continuation = True
                    if tail:
                        j = line.index(tail[0], i + 1)
                        emit("COMMENT", line[j:], ln, j, n, True)
                    break

            # shell escape: ! at the start of a statement
            if ch == "!" and stmt_start and not stack and not line.startswith("!=", i):
                emit("OP", "!", ln, i, i + 1, space, shell=True)
                rest = line[i + 1:].rstrip()
                if rest.strip():
                    j = i + 1 + (len(rest) - len(rest.lstrip()))
                    emit("CMDWORD", rest.strip(), ln, j, len(rest) + i + 1, True, shell=True)
                i = n
                break

            # names and keywords
            m = _NAME_RE.match(line, i)
            if m:
                word = m.group()
                after_dot = prev is not None and prev.kind == "OP" and prev.text == "." and not space
                if word in KEYWORDS and not after_dot:
                    emit("KEYWORD", word, ln, i, m.end(), space)
                    if word in _STMT_AFTER_KEYWORDS:
                        stmt_start = True
                    i = m.end()
                    space = False
                    continue
                at_start = stmt_start and not stack
                emit("NAME", word, ln, i, m.end(), space)
                i = m.end()
                space = False
                if at_start and word not in known_vars and _looks_like_command(line, i):
                    i = _scan_command_args(line, i, ln, emit)
                continue

            # numbers
            if ch.isdigit() or (ch == "." and i + 1 < n and line[i + 1].isdigit()):
                m = _NUM_RE.match(line, i)
                if m:
                    emit("NUMBER", m.group(), ln, i, m.end(), space)
                    i = m.end()
                    space = False
                    continue

            # single quote: transpose or char vector
            if ch == "'":
                in_matrix = stack and stack[-1] in "[{"
                # after a value it's a transpose, except "[a 'text']" inside brackets
                if _is_value_end(prev):
                    if not (space and in_matrix):
                        emit("OP", "'", ln, i, i + 1, space)
                        i += 1
                        space = False
                        continue
                j = _scan_quoted(line, i, "'")
                emit("STR", line[i:j], ln, i, j, space)
                i = j
                space = False
                continue

            if ch == '"':
                j = _scan_quoted(line, i, '"')
                emit("DQSTR", line[i:j], ln, i, j, space)
                i = j
                space = False
                continue

            op = _match_op(line, i)
            if op is None:
                emit("BAD", ch, ln, i, i + 1, space)
                i += 1
                space = False
                continue

            if op in ("(", "[", "{"):
                emit("OP", op, ln, i, i + 1, space)
                stack.append(op)
            elif op in (")", "]", "}"):
                want = {")": "(", "]": "[", "}": "{"}[op]
                if want in stack:
                    while stack and stack.pop() != want:
                        pass
                emit("OP", op, ln, i, i + 1, space)
            else:
                emit("OP", op, ln, i, i + len(op), space)
                if op in (";", ",") and not stack:
                    stmt_start = True
            i += len(op)
            space = False

        if continuation:
            continue
        # end of line
        if stack and stack[-1] == "(":
            c = len(line.rstrip())
            issues.append(
                _issue(
                    ln,
                    max(c, 1),
                    max(c, 1) + 1,
                    "In MATLAB, a line can't break inside `( )`. Add `...` at the end of the line to continue it.",
                )
            )
            # recover: forget the open brackets so later lines are read normally
            stack.clear()
        emit("NEWLINE", "\n", ln, len(line), len(line) + 1, False)
        if not stack:
            stmt_start = True

    return tokens, issues


def _scan_command_args(line: str, i: int, ln: int, emit) -> int:
    """Emit CMDWORD tokens for command-syntax arguments starting at ``line[i]``; return new index."""
    n = len(line)
    while i < n:
        while i < n and line[i] in " \t":
            i += 1
        if i >= n or line[i] in ",;%#" or line.startswith("...", i):
            return i
        start = i
        while i < n and line[i] not in " \t,;%":
            if line[i] == "'":
                i = _scan_quoted(line, i, "'")
            else:
                i += 1
        emit("CMDWORD", line[start:i], ln, start, i, True)
    return i
