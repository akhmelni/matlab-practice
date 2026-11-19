"""The MATLAB-compatibility checker: runs every rule over the token stream."""

from __future__ import annotations

from dataclasses import dataclass, field

from .issue import Issue
from .tables import (
    DQ_MESSAGE,
    OCTAVE_END_KEYWORDS,
    OCTAVE_FUNCTIONS,
    SHELL_ESCAPE_MESSAGE,
    UNSAFE,
    UNSUPPORTED_NAMES,
    matlab_names,
    octave_function_message,
    unsafe_message,
)
from .tokenizer import Token, tokenize

PROFILES = ("student", "authoring")

_COMPOUND_BASE = frozenset({"+", "-", "*", "/", "\\", "^", "|", "&", ".*", "./", ".^", ".\\", "**", ".**"})
_BLOCK_OPENERS = frozenset({"if", "for", "parfor", "while", "switch", "try", "spmd", "classdef", "function"})


def _err(tok: Token, rule: str, message: str, last: Token | None = None) -> Issue:
    last = last or tok
    return Issue(tok.line, tok.col, last.end_line, last.end_col, rule, "error", message)


def _is_value_end(tok: Token) -> bool:
    if tok.kind in ("NAME", "NUMBER", "STR", "DQSTR"):
        return True
    if tok.kind == "OP" and tok.text in (")", "]", "}", "'", ".'"):
        return True
    return tok.is_kw("end") and tok.depth > 0


def _is_terminator(tok: Token | None) -> bool:
    return tok is None or tok.kind == "NEWLINE" or tok.is_op(";", ",")


@dataclass
class _Defs:
    vars: set[str] = field(default_factory=set)
    funcs: set[str] = field(default_factory=set)
    header: set[int] = field(default_factory=set)  # indices (in code tokens) of function-header tokens


def _code_tokens(tokens: list[Token]) -> list[Token]:
    return [t for t in tokens if t.kind != "COMMENT"]


def _match_brackets(ct: list[Token]) -> dict[int, int]:
    """Map each bracket's index to its partner's index (both directions)."""
    pairs: dict[int, int] = {}
    stack: list[int] = []
    partner = {")": "(", "]": "[", "}": "{"}
    for k, t in enumerate(ct):
        if t.kind == "NEWLINE" and not t.depth:
            stack.clear()
        if t.kind != "OP":
            continue
        if t.text in "([{":
            stack.append(k)
        elif t.text in partner:
            for depth in range(len(stack) - 1, -1, -1):
                if ct[stack[depth]].text == partner[t.text]:
                    o = stack[depth]
                    del stack[depth:]
                    pairs[o] = k
                    pairs[k] = o
                    break
    return pairs


def _stmt_end(ct: list[Token], k: int) -> int:
    """Index just past the statement that contains token ``k`` (from ``k`` on)."""
    j = k + 1
    while j < len(ct):
        t = ct[j]
        if t.stmt_start:
            return j
        if (t.kind == "NEWLINE" or t.is_op(";", ",")) and t.depth == 0:
            return j
        j += 1
    return j


def _collect_defs(ct: list[Token], pairs: dict[int, int]) -> _Defs:
    d = _Defs()
    n = len(ct)
    for k, t in enumerate(ct):
        nxt = ct[k + 1] if k + 1 < n else None
        if t.is_kw("function"):
            end = k + 1
            while end < n and ct[end].kind != "NEWLINE" and not (ct[end].is_op(";", ",") and ct[end].depth == t.depth):
                end += 1
            hdr = list(range(k + 1, end))
            d.header.update(hdr)
            eq = next((j for j in hdr if ct[j].is_op("=") and ct[j].depth == t.depth), None)
            if eq is not None:
                d.vars.update(ct[j].text for j in hdr if j < eq and ct[j].kind == "NAME")
                rest = [j for j in hdr if j > eq]
            else:
                rest = hdr
            names = [j for j in rest if ct[j].kind == "NAME"]
            if names:
                first = names[0]
                if not (first + 1 < n and ct[first + 1].is_op(".")):
                    d.funcs.add(ct[first].text)
                d.vars.update(ct[j].text for j in names[1:])
        elif t.is_kw("for", "parfor") and nxt is not None:
            j = k + 1
            if ct[j].is_op("("):
                j += 1
            if j < n and ct[j].kind == "NAME":
                d.vars.add(ct[j].text)
        elif t.is_kw("global", "persistent"):
            for j in range(k + 1, _stmt_end(ct, k)):
                if ct[j].kind in ("NAME", "CMDWORD"):
                    d.vars.add(ct[j].text)
        elif t.is_kw("catch"):
            if nxt is not None and nxt.kind == "NAME" and nxt.line == t.line:
                after = ct[k + 2] if k + 2 < n else None
                if _is_terminator(after) or (after is not None and after.line != nxt.line):
                    d.vars.add(nxt.text)
        elif t.kind == "NAME" and t.stmt_start:
            for j in range(k + 1, _stmt_end(ct, k)):
                if ct[j].is_op("=") and ct[j].depth == t.depth:
                    d.vars.add(t.text)
                    break
        elif t.is_op("[") and t.stmt_start and k in pairs:
            close = pairs[k]
            if close + 1 < n and ct[close + 1].is_op("="):
                for j in range(k + 1, close):
                    u = ct[j]
                    if u.kind == "NAME" and u.depth == t.depth + 1 and not ct[j - 1].is_op("."):
                        d.vars.add(u.text)
        elif t.is_op("@") and nxt is not None and nxt.is_op("(") and (k + 1) in pairs:
            for j in range(k + 2, pairs[k + 1]):
                if ct[j].kind == "NAME":
                    d.vars.add(ct[j].text)
        # fallback: any "name =" at top level
        if t.kind == "NAME" and t.depth == 0 and nxt is not None and nxt.is_op("="):
            if k == 0 or not ct[k - 1].is_op("."):
                d.vars.add(t.text)
    return d


def _src_slice(lines: list[str], a: Token, b: Token) -> str | None:
    if a.line != b.line:
        return None
    return lines[a.line - 1][a.col - 1 : b.end_col - 1].strip()


class _Checker:
    def __init__(self, code, filename, profile, banned_functions, banned_operators, extra_allowed):
        self.filename = filename or ""
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r} (use 'student' or 'authoring')")
        self.code = code
        self.lines = code.splitlines()
        self.student = profile == "student"
        self.banned = {b.strip() for b in banned_functions if b and b.strip()}
        self.banned_ops = [b for b in banned_operators if b and b.strip()]
        self.extra = {a.strip() for a in extra_allowed if a and a.strip()}
        self.issues: list[Issue] = []

        # Pass 1 finds the variables, so pass 2 can tell "x -1" (expression) from "hold on" (command).
        toks1, _ = tokenize(code)
        ct1 = _code_tokens(toks1)
        defs1 = _collect_defs(ct1, _match_brackets(ct1))
        self.tokens, lex_issues = tokenize(code, known_vars=frozenset(defs1.vars | defs1.funcs))
        self.issues.extend(lex_issues)
        self.ct = _code_tokens(self.tokens)
        self.pairs = _match_brackets(self.ct)
        self.defs = _collect_defs(self.ct, self.pairs)
        self.known = self.defs.vars | self.defs.funcs | self.extra

    def add(self, tok: Token, rule: str, message: str, last: Token | None = None) -> None:
        self.issues.append(_err(tok, rule, message, last))

    def tok(self, k: int) -> Token | None:
        return self.ct[k] if 0 <= k < len(self.ct) else None

    def adjacent(self, a: Token, b: Token | None) -> bool:
        return b is not None and b.line == a.end_line and b.col == a.end_col

    # ------------------------------------------------------------------ rules
    def run(self) -> list[Issue]:
        self.check_tokens()
        self.check_assignments()
        self.check_names()
        self.check_local_functions()
        self.check_banned_operators()
        self.check_function_name()
        seen = set()
        out = []
        for i in sorted(self.issues, key=lambda i: (i.line, i.col, i.rule)):
            key = (i.line, i.col, i.rule)
            if key not in seen:
                seen.add(key)
                out.append(i)
        return out

    def check_tokens(self) -> None:
        ct = self.ct
        for k, t in enumerate(ct):
            nxt = self.tok(k + 1)
            if t.kind == "DQSTR":
                self.add(t, "unsupported-feature", DQ_MESSAGE)
            elif t.is_kw("classdef"):
                self.add(t, "unsupported-feature", "`classdef` (classes) isn't supported here: Octave handles classes differently from MATLAB.")
            elif t.kind == "OP":
                self.check_op(k, t, nxt)

            # indexing the result of a call / literal: f(x)(2), [1 2 3](2), 'abc'(1)
            if nxt is not None and nxt.is_op("(", "{") and self.adjacent(t, nxt):
                if self.is_direct_index_of_expression(k, t):
                    self.add(
                        t,
                        "octave-syntax",
                        "MATLAB can't index a result directly, like `f(x)(2)`. Save it in a variable first, then index the variable.",
                        nxt,
                    )

    def check_assignments(self) -> None:
        """Octave accepts ``a = b = 3``, ``if (x = 3)`` and ``global g = 1``; MATLAB doesn't."""
        ct = self.ct
        for k, t in enumerate(ct):
            if not t.stmt_start:
                continue
            end = _stmt_end(ct, k)
            eqs = [j for j in range(k, end) if ct[j].is_op("=") and ct[j].depth == t.depth]
            if t.is_kw("global", "persistent"):
                for j in eqs:
                    self.add(
                        ct[j],
                        "octave-syntax",
                        f"MATLAB can't set a value in a `{t.text}` line. Declare it on its own line, then assign it.",
                    )
            elif t.is_kw("if", "elseif", "while"):
                nxt = self.tok(k + 1)
                bare = nxt is not None and nxt.kind == "NAME" and k + 2 < end and ct[k + 2].is_op("=")
                for j in range(k + 1, end):
                    u = ct[j]
                    if not u.is_op("="):
                        continue
                    grouped = u.depth > t.depth and self.in_grouping_paren(j)
                    if grouped or (bare and j == k + 2):
                        self.add(u, "octave-syntax", "Use `==` to compare in MATLAB. A single `=` only stores a value.")
            elif t.kind == "NAME" or t.is_op("["):
                for j in eqs[1:]:
                    self.add(
                        ct[j],
                        "octave-syntax",
                        "MATLAB can't chain assignments like `a = b = 3`. Assign one variable per statement.",
                    )

    def in_grouping_paren(self, j: int) -> bool:
        """Is token ``j`` directly inside ``( )`` that only group (not a call or an index)?"""
        depth = 0
        for i in range(j - 1, -1, -1):
            u = self.ct[i]
            if u.is_op(")", "]", "}"):
                depth += 1
            elif u.is_op("(", "[", "{"):
                if depth == 0:
                    if not u.is_op("("):
                        return False
                    before = self.tok(i - 1)
                    return not (before is not None and _is_value_end(before) and not u.space_before)
                depth -= 1
            elif u.kind == "NEWLINE" and u.depth == 0:
                return False
        return False

    def is_direct_index_of_expression(self, k: int, t: Token) -> bool:
        if t.kind in ("STR", "DQSTR"):
            return True
        if t.kind != "OP":
            return False
        if t.text in ("'", ".'"):
            return True
        if t.text == "]":
            return True
        if t.text in (")", "}") and k in self.pairs:
            o = self.pairs[k]
            before = self.tok(o - 1)
            if t.text == ")":
                # @(x)(x + 1) is an anonymous function; s.(name)(2) is a dynamic field
                return not (before is not None and before.is_op("@", "."))
            # "}": c{1}(2) is fine; {1,2}{1} is not
            opener = self.ct[o]
            is_index = before is not None and _is_value_end(before) and (
                not opener.space_before or opener.bracket not in ("[", "{")
            )
            return not is_index
        return False

    def check_op(self, k: int, t: Token, nxt: Token | None) -> None:
        text = t.text
        if text in ("**", ".**") and not (nxt is not None and nxt.is_op("=") and self.adjacent(t, nxt)):
            better = ".^" if text == ".**" else "^"
            self.add(t, "octave-syntax", f"`{text}` doesn't work in MATLAB. Use `{better}` for powers.")
            return
        if text == "!=":
            self.add(t, "octave-syntax", "`!=` doesn't work in MATLAB. Use `~=` for 'not equal'.")
            return
        if text == "!":
            if t.shell:
                if self.student:
                    self.add(t, "unsafe", SHELL_ESCAPE_MESSAGE)
                else:
                    self.add(t, "octave-syntax", "Use `~` for 'not'. In MATLAB, `!` at the start of a line runs a computer command.")
            else:
                self.add(t, "octave-syntax", "`!` doesn't work in MATLAB. Use `~` for 'not'.")
            return

        # compound assignment: x += 1
        if text in _COMPOUND_BASE and nxt is not None and nxt.is_op("=") and self.adjacent(t, nxt):
            self.add(t, "octave-syntax", self.compound_message(k, t), nxt)
            return

        # increment / decrement: x++, x--, ++x
        if text in ("+", "-") and nxt is not None and nxt.is_op(text) and self.adjacent(t, nxt):
            prev = self.tok(k - 1)
            after = self.tok(k + 2)
            sym = text * 2
            if prev is not None and _is_value_end(prev) and not prev.is_kw("end") and _is_terminator(after) and not (
                after is not None and after.line != t.line and after.kind != "NEWLINE"
            ):
                target = prev.text if prev.kind == "NAME" else "x"
                self.add(
                    t,
                    "octave-syntax",
                    f"`{target}{sym}` doesn't work in MATLAB. Write `{target} = {target} {text} 1`.",
                    nxt,
                )
            elif t.stmt_start and after is not None and after.kind == "NAME" and _is_terminator(self.tok(k + 3)):
                target = after.text
                self.add(
                    t,
                    "octave-syntax",
                    f"`{sym}{target}` doesn't change `{target}` in MATLAB. Write `{target} = {target} {text} 1`.",
                    after,
                )

    def compound_message(self, k: int, t: Token) -> str:
        op = t.text
        plain = {"**": "^", ".**": ".^"}.get(op, op)
        generic = f"`{op}=` doesn't work in MATLAB. Write `x = x {plain} 1` instead of `x {op}= 1`."
        # find the statement start
        s = k - 1
        while s > 0 and not self.ct[s].stmt_start:
            s -= 1
        if s < 0 or s >= k:
            return generic
        lhs = _src_slice(self.lines, self.ct[s], self.ct[k - 1])
        e = _stmt_end(self.ct, k + 1)
        if k + 2 >= e:
            return generic
        rhs_toks = self.ct[k + 2 : e]
        rhs = _src_slice(self.lines, rhs_toks[0], rhs_toks[-1])
        if not lhs or not rhs or len(lhs) > 40 or len(rhs) > 40:
            return generic
        if op != "+" and len(rhs_toks) > 1 and any(
            u.kind == "OP" and u.depth == t.depth and u.text not in "()[]{}" for u in rhs_toks
        ):
            rhs = f"({rhs})"
        return f"`{op}=` doesn't work in MATLAB. Write `{lhs} = {lhs} {plain} {rhs}`."

    def check_names(self) -> None:
        plain, dotted = matlab_names()
        ct = self.ct
        if any(t.is_kw("classdef") for t in ct):
            return  # already reported; class files use names this checker can't follow
        for k, t in enumerate(ct):
            if t.kind != "NAME":
                continue
            prev = self.tok(k - 1)
            nxt = self.tok(k + 1)
            if prev is not None and prev.is_op(".", "?"):
                continue  # struct field / metaclass
            if k in self.defs.header:
                continue
            if t.bracket == "(" and nxt is not None and nxt.is_op("=") and t.depth > 0:
                continue  # Name=value argument
            name = t.text
            if name in self.known:
                continue
            if not self.student and name.startswith("mp_"):
                continue

            # Octave-only block keywords
            if name in OCTAVE_END_KEYWORDS:
                self.add(t, "octave-syntax", f"`{name}` only works in Octave. In MATLAB, close the block with `end`.")
                continue
            if name in ("unwind_protect", "unwind_protect_cleanup"):
                self.add(t, "octave-syntax", f"`{name}` only works in Octave. In MATLAB, use `try ... catch ... end`.")
                continue
            if name == "do" and t.stmt_start and _is_terminator(nxt):
                self.add(t, "octave-syntax", "MATLAB has no `do ... until` loop. Use `while true ... if done, break; end ... end`.")
                continue
            if name == "until" and t.stmt_start:
                self.add(t, "octave-syntax", "MATLAB has no `do ... until` loop. Use `while true ... if done, break; end ... end`.")
                continue
            if name == "arguments" and t.stmt_start and (
                nxt is None or nxt.kind == "NEWLINE" or (nxt.is_op("(") and (self.tok(k + 2) or t).text in ("Input", "Output", "Repeating"))
            ):
                self.add(t, "unsupported-feature", "`arguments` blocks aren't supported here (Octave doesn't have them). Check inputs with `if` and `error` instead.")
                continue

            # dotted names: py.foo, containers.Map, matlab.lang.makeValidName
            if nxt is not None and nxt.is_op(".") and self.adjacent(t, nxt):
                if name == "py":
                    self.add(t, "unsupported-feature", "Python (`py.`) isn't available in practice problems.")
                    continue
                if name in dotted:
                    chain = [name]
                    j = k + 1
                    while j + 1 < len(ct) and ct[j].is_op(".") and ct[j + 1].kind == "NAME":
                        chain.append(ct[j + 1].text)
                        j += 2
                    if any(".".join(chain[:m]) in dotted[name] for m in range(2, len(chain) + 1)):
                        continue

            # cellfun('sqrt', ...): Octave calls any function named in the string
            if name in ("cellfun", "arrayfun", "structfun") and nxt is not None and nxt.is_op("("):
                arg = self.tok(k + 2)
                if arg is not None and arg.kind == "STR":
                    fname = arg.text[1:-1].replace("''", "'").strip()
                    if fname.isidentifier() and fname not in self.known:
                        self.check_name_usage(arg, fname, plain)

            self.check_name_usage(t, name, plain)

    def check_name_usage(self, t: Token, name: str, plain: frozenset[str]) -> None:
        """Report a use of ``name`` (not a local variable or function) at token ``t``."""
        if name in self.banned:
            self.add(t, "banned-function", f"This problem doesn't allow `{name}`.")
            if not (self.student and name in UNSAFE):
                return
        if self.student and name in UNSAFE:
            self.add(t, "unsafe", unsafe_message(name))
            return
        if name in UNSUPPORTED_NAMES:
            self.add(t, "unsupported-feature", UNSUPPORTED_NAMES[name])
            return
        if name in OCTAVE_FUNCTIONS:
            self.add(t, "octave-function", octave_function_message(name))
            return
        if name not in plain and not (not self.student and name.startswith("mp_")):
            self.add(
                t,
                "unknown-function",
                f"`{name}` isn't a MATLAB function (it may only exist in Octave). "
                "If it is a real MATLAB function, ask Claude to add it to the list.",
            )

    # ------------------------------------------------------------------ local functions
    def check_local_functions(self) -> None:
        ct = self.ct
        first = next((t for t in ct if t.kind != "NEWLINE"), None)
        if first is None or any(t.is_kw("classdef") for t in ct):
            return
        is_script = not first.is_kw("function")

        opens = closes = funcs = 0
        events: list[tuple[int, str]] = []  # (index, "open" | "func" | "close")
        for k, t in enumerate(ct):
            kind = self.block_event(k, t)
            if kind:
                events.append((k, kind))
                if kind == "func":
                    funcs += 1
                elif kind == "open":
                    opens += 1
                else:
                    closes += 1
        if funcs == 0:
            return
        if closes == opens:
            # functions are not closed with "end"
            if is_script:
                for k, kind in events:
                    if kind == "func":
                        self.add(ct[k], "script-local-functions", "In a MATLAB script, every local function must finish with its own `end`.")
            return
        if closes != opens + funcs:
            return  # unbalanced blocks: a syntax error Octave will report

        kinds = dict(events)
        depth = 0
        seen_function = False
        for k, t in enumerate(ct):
            if depth == 0 and t.stmt_start and t.kind != "NEWLINE" and seen_function and not t.is_kw("function"):
                if is_script:
                    msg = "In MATLAB, local functions must be at the end of a script. Move this code above the first `function`."
                else:
                    msg = "In a MATLAB function file, all code must be inside a function. Move this code into a function."
                self.add(t, "script-local-functions", msg)
                return
            kind = kinds.get(k)
            if kind in ("open", "func"):
                depth += 1
                if kind == "func":
                    seen_function = True
            elif kind == "close":
                depth = max(0, depth - 1)

    def block_event(self, k: int, t: Token) -> str | None:
        nxt = self.tok(k + 1)
        if t.kind == "KEYWORD":
            if t.text == "function":
                return "func"
            if t.text in _BLOCK_OPENERS:
                return "open"
            if t.text == "end" and t.depth == 0:
                return "close"
            return None
        if t.kind == "NAME" and t.text not in self.known:
            if t.text in OCTAVE_END_KEYWORDS:
                return "close"
            if t.stmt_start and t.text == "do" and _is_terminator(nxt):
                return "open"
            if t.stmt_start and t.text == "until":
                return "close"
            if t.stmt_start and t.text == "unwind_protect":
                return "open"
            if t.stmt_start and t.text == "arguments" and (nxt is None or nxt.kind == "NEWLINE" or nxt.is_op("(")):
                return "open"
        return None

    # ------------------------------------------------------------------ function name vs file name
    def check_function_name(self) -> None:
        """Warn when a function file's main function isn't named after the file (MATLAB uses the file name)."""
        stem = self.filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not stem.endswith(".m"):
            return
        stem = stem[:-2]
        if stem in ("", "solution") or not stem.isidentifier():
            return
        first = next((k for k, t in enumerate(self.ct) if t.kind != "NEWLINE"), None)
        if first is None or not self.ct[first].is_kw("function"):
            return
        names = [k for k in self.defs.header if self.ct[k].kind == "NAME"]
        hdr = sorted(k for k in names if k < (self.next_newline(first)))
        eq = next((k for k in range(first, self.next_newline(first)) if self.ct[k].is_op("=") and self.ct[k].depth == 0), None)
        cands = [k for k in hdr if eq is None or k > eq]
        if not cands:
            return
        tok = self.ct[cands[0]]
        if tok.text != stem:
            self.issues.append(
                Issue(
                    tok.line, tok.col, tok.end_line, tok.end_col, "function-name", "warning",
                    f"The function is named `{tok.text}` but the file is `{stem}.m`. In MATLAB they must match: "
                    f"rename the function to `{stem}`.",
                )
            )

    def next_newline(self, k: int) -> int:
        while k < len(self.ct) and self.ct[k].kind != "NEWLINE":
            k += 1
        return k

    # ------------------------------------------------------------------ banned operators
    def check_banned_operators(self) -> None:
        if not self.banned_ops:
            return
        seq = [t for t in self.ct if t.kind not in ("NEWLINE", "CMDWORD")]
        for spelling in self.banned_ops:
            pat_toks, _ = tokenize(spelling.strip())
            pattern = [t for t in pat_toks if t.kind not in ("NEWLINE", "COMMENT")]
            if not pattern:
                continue
            shown = "".join(t.text for t in pattern)
            for start in range(len(seq)):
                end = _match_pattern(seq, start, pattern, 0)
                if end is not None:
                    self.add(seq[start], "banned-operator", f"This problem doesn't allow `{shown}`.", seq[end - 1])


def _num(text: str) -> complex | None:
    t = text.lower().replace("d", "e")
    try:
        if t.endswith(("i", "j")):
            return complex(0, float(t[:-1]))
        if t.startswith(("0x", "0b")):
            return complex(int(t, 0), 0)
        return complex(float(t), 0)
    except ValueError:
        return None


def _same(code_tok: Token, pat_tok: Token) -> bool:
    if pat_tok.kind == "NUMBER" and code_tok.kind == "NUMBER":
        a, b = _num(code_tok.text), _num(pat_tok.text)
        return a is not None and a == b
    return code_tok.text == pat_tok.text and (code_tok.kind == "OP") == (pat_tok.kind == "OP")


def _match_pattern(seq: list[Token], i: int, pattern: list[Token], p: int) -> int | None:
    """Match pattern[p:] at seq[i:]; return the end index or None. A number may be wrapped in ( )."""
    if p == len(pattern):
        return i
    if i >= len(seq):
        return None
    pt = pattern[p]
    if _same(seq[i], pt):
        r = _match_pattern(seq, i + 1, pattern, p + 1)
        if r is not None:
            return r
    if pt.kind == "NUMBER" and seq[i].is_op("(") and i + 2 < len(seq):
        if _same(seq[i + 1], pt) and seq[i + 2].is_op(")"):
            return _match_pattern(seq, i + 3, pattern, p + 1)
    return None


def check(
    code: str,
    *,
    filename: str = "solution.m",
    profile: str = "student",
    banned_functions=(),
    banned_operators=(),
    extra_allowed=(),
) -> list[Issue]:
    """Check MATLAB code; return the issues found (empty list: the code is fine).

    ``profile="student"`` runs every rule. ``profile="authoring"`` (evaluator files) skips the
    unsafe-call rule and allows names starting with ``mp_``. ``extra_allowed`` lists names defined
    elsewhere (e.g. the student's function when checking his scratch script). ``filename`` is only
    used to warn (rule ``function-name``) when a function file's function is named differently.
    """
    if isinstance(banned_functions, str):
        banned_functions = (banned_functions,)
    if isinstance(banned_operators, str):
        banned_operators = (banned_operators,)
    if isinstance(extra_allowed, str):
        extra_allowed = (extra_allowed,)
    return _Checker(code, filename, profile, banned_functions, banned_operators, extra_allowed).run()
